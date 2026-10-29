"""Executed storage behaviour, using labelled fixtures rather than plant evidence."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from monitor.storage import EvidenceStore, open_read_only


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def event():
    return json.loads((ROOT / 'contracts/illustrative-observation.json').read_text())


@pytest.fixture
def database(tmp_path):
    return tmp_path / 'doseproof.db'


def body(event):
    return json.dumps(event).encode('utf-8')


def test_initialization_has_six_empty_categories_and_is_repeatable(database):
    for _ in range(2):
        with EvidenceStore(database):
            pass
    with open_read_only(database) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert tables == {'raw_events', 'validation_errors', 'normalized_events', 'linked_evidence', 'source_health', 'verdicts'}
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 1
        assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
        assert all(conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0] == 0 for t in tables)


@pytest.mark.parametrize('raw', [b'', b'{bad json', b'\x00\xff\xfe', b'  { "a": 1 }\r\n'])
def test_preserves_exact_bytes_and_separate_receipt_time_after_reopen(database, raw):
    with EvidenceStore(database) as store:
        receipt = store.write_raw(raw, content_type='application/json')
        assert receipt.body_sha256 == hashlib.sha256(raw).hexdigest()
        assert receipt.received_at_utc.endswith('Z')
        # Visible to a different connection immediately, before parsing/validation.
        with open_read_only(database) as reader:
            assert reader.execute('SELECT body FROM raw_events').fetchone()[0] == raw
    with EvidenceStore(database) as store:
        assert store.read_raw(receipt.receipt_id) == receipt
        assert store.read_raw('missing') is None


def test_committed_receipt_survives_writer_process_exit(database):
    code = "from monitor.storage import EvidenceStore; import sys; s=EvidenceStore(sys.argv[1]); print(s.write_raw(b'copied-bytes').receipt_id, flush=True)"
    result = subprocess.run([sys.executable, '-c', code, str(database)], cwd=ROOT, capture_output=True, text=True, check=True)
    with EvidenceStore(database) as store:
        assert store.read_raw(result.stdout.strip()).body == b'copied-bytes'


def test_error_is_linked_and_survives_reopen_without_discarding_raw(database):
    with EvidenceStore(database) as store:
        receipt = store.write_raw(b'not json')
        error_id = store.write_validation_error(receipt.receipt_id, code='invalid_json', message='Test fixture deliberately is not JSON')
        with pytest.raises(sqlite3.IntegrityError):
            store.write_validation_error('missing', code='bad', message='Orphan is refused')
    with open_read_only(database) as conn:
        row = conn.execute('SELECT * FROM validation_errors WHERE error_id=?', (error_id,)).fetchone()
        assert row['receipt_id'] == receipt.receipt_id
        assert conn.execute('SELECT count(*) FROM validation_errors').fetchone()[0] == 1
        assert conn.execute('SELECT body FROM raw_events').fetchone()[0] == b'not json'


def test_normalization_keeps_identity_times_and_null_change_id(database, event):
    with EvidenceStore(database) as store:
        receipt = store.write_raw(body(event))
        result = store.write_normalized(receipt.receipt_id, event)
        assert result.outcome == 'created'
    with EvidenceStore(database) as store:
        assert store.read_normalized(result.normalized_id) == event
        assert store.read_raw(receipt.receipt_id).normalized_id == result.normalized_id
        assert store.read_raw(receipt.receipt_id).received_at_utc != event['source_timestamp_utc']
        assert store.read_normalized('missing') is None


def test_retries_have_separate_receipts_but_one_logical_event(database, event):
    with EvidenceStore(database) as store:
        receipts = [store.write_raw(body(event)), store.write_raw(json.dumps(event, indent=2, sort_keys=True).encode())]
        first, retry = [store.write_normalized(r.receipt_id, event) for r in receipts]
        assert (first.outcome, retry.outcome) == ('created', 'duplicate')
        assert first.normalized_id == retry.normalized_id
        assert receipts[0].receipt_id != receipts[1].receipt_id
    with open_read_only(database) as conn:
        assert conn.execute('SELECT count(*) FROM raw_events').fetchone()[0] == 2
        assert conn.execute('SELECT count(*) FROM normalized_events').fetchone()[0] == 1
        assert {r[0] for r in conn.execute('SELECT normalized_id FROM raw_events')} == {first.normalized_id}


def test_conflicting_reused_identity_is_retained_and_not_overwritten(database, event):
    with EvidenceStore(database) as store:
        first_raw = store.write_raw(body(event))
        first = store.write_normalized(first_raw.receipt_id, event)
        conflicting = json.loads(json.dumps(event))
        conflicting['payload']['value'] += 0.4
        conflict_raw = store.write_raw(body(conflicting))
        result = store.write_normalized(conflict_raw.receipt_id, conflicting)
        assert result.outcome == 'conflict'
        assert result.normalized_id is None
        assert store.read_normalized(first.normalized_id) == event
        assert store.read_raw(conflict_raw.receipt_id).normalized_id is None
    with open_read_only(database) as conn:
        assert conn.execute('SELECT count(*) FROM normalized_events').fetchone()[0] == 1
        row = conn.execute('SELECT * FROM validation_errors WHERE error_id=?', (result.error_id,)).fetchone()
        assert row['code'] == 'event_identity_conflict'
        assert row['receipt_id'] == conflict_raw.receipt_id


@pytest.mark.parametrize('identity_field', ['run_id', 'source_id'])
def test_same_event_id_can_be_distinct_in_different_producer_or_run(database, event, identity_field):
    with EvidenceStore(database) as store:
        first = store.write_normalized(store.write_raw(body(event)).receipt_id, event)
        other = dict(event, **{identity_field: 'sensor-b' if identity_field == 'source_id' else 'different-run'})
        second = store.write_normalized(store.write_raw(body(other)).receipt_id, other)
        assert second.outcome == 'created'
        assert first.normalized_id != second.normalized_id


def test_failure_in_derived_transaction_does_not_rollback_receipt(database, event):
    with EvidenceStore(database) as store:
        receipt = store.write_raw(body(event))
        store._conn.execute("CREATE TRIGGER test_failure BEFORE INSERT ON normalized_events BEGIN SELECT RAISE(ABORT, 'injected test failure'); END")
        with pytest.raises(sqlite3.IntegrityError, match='injected test failure'):
            store.write_normalized(receipt.receipt_id, event)
        assert store.read_raw(receipt.receipt_id).body == body(event)
        assert store.read_raw(receipt.receipt_id).normalized_id is None
        assert store._conn.execute('SELECT count(*) FROM normalized_events').fetchone()[0] == 0


def test_cannot_forge_source_record_during_normalization(database, event):
    with EvidenceStore(database) as store:
        receipt = store.write_raw(body(event))
        altered = dict(event, source_timestamp_utc='2099-01-01T00:00:00Z')
        with pytest.raises(ValueError, match='match the retained'):
            store.write_normalized(receipt.receipt_id, altered)
        with pytest.raises(KeyError):
            store.write_normalized('missing', event)
        assert store.read_raw(receipt.receipt_id).body == body(event)


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}'])
def test_ambiguous_or_nonfinite_json_is_never_registered(database, raw):
    with EvidenceStore(database) as store:
        receipt = store.write_raw(raw)
        with pytest.raises(ValueError):
            store.write_normalized(receipt.receipt_id, {})
        assert store.read_raw(receipt.receipt_id).body == raw


def test_read_only_connection_rejects_writes_and_does_not_create_missing_database(database):
    with pytest.raises(sqlite3.OperationalError):
        open_read_only(database)
    assert not database.exists()
    with EvidenceStore(database):
        pass
    with open_read_only(database) as conn:
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            conn.execute("INSERT INTO raw_events VALUES ('x','x',X'00','x',NULL,NULL)")


def test_original_and_normalized_records_cannot_be_rewritten_or_deleted(database, event):
    with EvidenceStore(database) as store:
        receipt = store.write_raw(body(event))
        store.write_normalized(receipt.receipt_id, event)
        for sql in ["UPDATE raw_events SET body=X'00'", 'DELETE FROM raw_events',
                    "UPDATE normalized_events SET event_id='other'", 'DELETE FROM normalized_events',
                    'UPDATE raw_events SET normalized_id=NULL']:
            with pytest.raises(sqlite3.IntegrityError):
                with store._conn:
                    store._conn.execute(sql)


def test_foreign_keys_apply_to_all_derived_categories(database):
    with EvidenceStore(database) as store:
        for sql in [
            "INSERT INTO linked_evidence VALUES ('x','run',NULL,'missing','time','{}')",
            "INSERT INTO source_health VALUES ('x','run','sensor-a','time','missing','{}')",
            "INSERT INTO verdicts VALUES ('x','run','rule','PASS','test','missing','time','{}')",
        ]:
            with pytest.raises(sqlite3.IntegrityError):
                with store._conn:
                    store._conn.execute(sql)


@pytest.mark.parametrize('unversioned', [False, True])
def test_refuses_unrecognized_databases_without_modifying_them(database, unversioned):
    with sqlite3.connect(database) as conn:
        conn.execute('CREATE TABLE existing_data (value TEXT)')
        conn.execute("INSERT INTO existing_data VALUES ('keep')")
        if not unversioned:
            conn.execute('PRAGMA user_version=99')
    with pytest.raises(RuntimeError):
        EvidenceStore(database)
    with sqlite3.connect(database) as conn:
        assert conn.execute('SELECT value FROM existing_data').fetchone()[0] == 'keep'
        assert conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 1


def test_writer_requires_original_bytes(database):
    with EvidenceStore(database) as store:
        with pytest.raises(TypeError):
            store.write_raw('{"reserialized":true}')


def test_refuses_unrelated_database_even_if_schema_version_is_one(database):
    with sqlite3.connect(database) as conn:
        conn.execute('PRAGMA user_version=1')
    with pytest.raises(RuntimeError, match='not identified'):
        EvidenceStore(database)


def test_fixture_check_exports_actual_bytes_and_explicit_pending_integration(tmp_path):
    output = tmp_path / 'fixture-proof'
    subprocess.run([sys.executable, '-m', 'monitor.check_storage', '--output', str(output)], cwd=ROOT, check=True, capture_output=True)
    report = json.loads((output / 'storage-check.json').read_text())
    assert report['evidence_kind'] == 'fixture_storage_check_not_plant_execution'
    assert report['plant_collector_integration'] == 'Not run'
    assert report['record_counts']['verdicts'] == 0
    import base64
    record = json.loads((output / 'source-records.jsonl').read_text())
    assert base64.b64decode(record['original_body_base64']) == (ROOT / 'contracts/illustrative-observation.json').read_bytes()
    # A second invocation must not replace earlier evidence.
    repeated = subprocess.run([sys.executable, '-m', 'monitor.check_storage', '--output', str(output)], cwd=ROOT, capture_output=True)
    assert repeated.returncode != 0


def test_failed_migration_does_not_leave_partial_schema(database, monkeypatch):
    read_text = Path.read_text

    def broken_migration(path, *args, **kwargs):
        if path.name == '001_evidence.sql':
            return 'CREATE TABLE partial (value TEXT);\nINVALID SQL;\n'
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', broken_migration)
    with pytest.raises(sqlite3.OperationalError):
        EvidenceStore(database)
    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 0
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 0
        assert conn.execute('PRAGMA application_id').fetchone()[0] == 0
