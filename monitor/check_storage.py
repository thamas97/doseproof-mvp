"""Repeatable DPM-11 fixture check, never claimed as plant/collector acceptance."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sqlite3

from jsonschema import Draft202012Validator, FormatChecker

from monitor.storage import EvidenceStore, open_read_only


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New local evidence directory (must not already exist)')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / 'doseproof.db'
    source = ROOT / 'contracts/illustrative-observation.json'
    original = source.read_bytes()
    # The exact file bytes are copied and committed before schema validation.
    with EvidenceStore(path) as store:
        receipt = store.write_raw(original, content_type='application/json')
        event = json.loads(original)
        schema = json.loads((ROOT / 'contracts/event-envelope.schema.json').read_text())
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(event)
        normalized = store.write_normalized(receipt.receipt_id, event)
    with EvidenceStore(path) as reopened:
        restored = reopened.read_raw(receipt.receipt_id)
        restored_event = reopened.read_normalized(normalized.normalized_id)
        assert restored.body == original
        assert restored.body_sha256 == hashlib.sha256(original).hexdigest()
        assert restored_event == event
    with open_read_only(path) as reader:
        integrity = reader.execute('PRAGMA integrity_check').fetchone()[0]
        foreign_keys = [list(row) for row in reader.execute('PRAGMA foreign_key_check')]
        counts = {table: reader.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in
                  ('raw_events', 'normalized_events', 'validation_errors', 'linked_evidence', 'source_health', 'verdicts')}
    assert integrity == 'ok' and not foreign_keys
    export = {
        'evidence_kind': 'fixture_storage_check_not_plant_execution',
        'fixture_path': 'contracts/illustrative-observation.json',
        'receipt_id': receipt.receipt_id,
        'received_at_utc': receipt.received_at_utc,
        'source_timestamp_utc': event['source_timestamp_utc'],
        'emitted_at_utc': event['emitted_at_utc'],
        'run_id': event['run_id'], 'source_id': event['source_id'], 'event_id': event['event_id'],
        'change_id': event['change_id'],
        'body_encoding': 'base64', 'original_body_base64': base64.b64encode(original).decode('ascii'),
        'body_sha256': receipt.body_sha256,
    }
    (args.output / 'source-records.jsonl').write_text(json.dumps(export) + '\n', encoding='utf-8')
    summary = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'evidence_kind': export['evidence_kind'],
        'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version,
        'byte_identical_after_reconnect': True, 'source_envelope_unchanged': True,
        'integrity_check': integrity, 'foreign_key_errors': foreign_keys, 'record_counts': counts,
        'plant_collector_integration': 'Not run', 'emmanuel_review': 'Pending',
        'tranos_source_confirmation': 'Pending', 'shared_contract_agreement': 'Pending',
    }
    (args.output / 'storage-check.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    (args.output / 'result.md').write_text(
        '# DPM-11 fixture storage check\n\n'
        'Input: the existing illustrative fixture, copied as bytes. This is not a genuine plant event.\n\n'
        'Observed: exact original bytes and source envelope survived closing and reopening the store; '
        'SQLite integrity and foreign-key checks passed. See storage-check.json and the labelled base64 export.\n\n'
        'No process screenshot was captured: there is no running plant/collector in this check. '
        'Genuine source capture, contract agreement, Emmanuel acceptance and Tranos source confirmation remain pending.\n',
        encoding='utf-8',
    )
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
