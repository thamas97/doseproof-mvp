# DPM-11 — durable receipt storage and collector handoff

Owner: Thabani. Human reviewer: Emmanuel. Source confirmation: Tranos.

This branch implements local SQLite storage. It does not implement the plant,
HTTP collector, full validator, rule engine, evidence API or dashboard. The
shared envelope, register map, teaching values and saved scenarios are unchanged.
The storage interface below is a proposal for review, not recorded team agreement.

## What works

`EvidenceStore('doseproof.db')` initializes migration 001 in one transaction.
Opening it again preserves data. `user_version=1` and the DPM1 application ID
identify the database; unknown versions and nonempty unversioned files are refused.
The parent directory must already exist. Foreign keys are enabled on each
connection, writes use SQLite transactions and `synchronous=FULL`, and the writer
has a five-second lock timeout. Use one collector writer thread; do not share the
connection across threads or instantiate a new writer for every HTTP request.

The six categories are:

| Table | Purpose now |
| --- | --- |
| `raw_events` | Every received byte sequence, unique receipt ID, real receipt UTC time, SHA-256 and optional content type. |
| `validation_errors` | Actual caller-reported errors, plus identity conflicts, linked to an existing raw receipt. |
| `normalized_events` | One unchanged validated source envelope per logical identity, with original source/emission timestamps. |
| `linked_evidence` | Empty schema for later correlation; no chains have been inferred. |
| `source_health` | Empty schema for later health records; no source is declared healthy. |
| `verdicts` | Empty schema for later explained results; no PASS/FAIL has been manufactured. |

Raw receipt fields cannot be rewritten or deleted through ordinary SQL. Only the
derived `normalized_id` association may be populated once. Normalized records are
also immutable. These guards and hashes are prototype integrity measures, not
cryptographic proof against an administrator who can edit this laptop/database.

## Emmanuel: use this order in the collector

```python
from monitor.storage import EvidenceStore

# Keep this store in the one collector writer thread and close it at shutdown.
store = EvidenceStore('doseproof.db')
receipt = store.write_raw(original_request_bytes, content_type='application/json')
# Returning from write_raw means its own transaction committed. Do this BEFORE
# decoding JSON or checking fields. Do not reserialize a parsed dictionary here.
saved = store.read_raw(receipt.receipt_id)
assert saved.body == original_request_bytes

# Then perform DPM-10/DPM-13 validation. These functions do not supply that logic.
# On an actual validation failure:
# store.write_validation_error(receipt.receipt_id,
#     code='invalid_unit', message='Expected mg/L; received <actual unit>')
# On success, supply the unchanged validated envelope:
# result = store.write_normalized(receipt.receipt_id, validated_event)
# Only use result.normalized_id downstream for created/duplicate, not conflict.
store.close()
```

If validation or a derived transaction fails, the raw transaction remains.
If `write_raw` fails, do not acknowledge durable acceptance: surface the error
and let the source retain/retry its event. A transport success is not an approval,
plant acknowledgement, delivery measurement or assurance verdict.

| Operation | Return / failure meaning |
| --- | --- |
| `write_raw(bytes, content_type=...)` | `RawReceipt` after commit. Rejects decoded text instead of pretending it is the original bytes. |
| `read_raw(receipt_id)` | Receipt including exact `bytes`, or `None` when missing. |
| `write_validation_error(receipt_id, code=..., message=..., stage='validation')` | Persisted error ID; foreign keys refuse orphan receipt IDs. |
| `write_normalized(receipt_id, validated_event)` | `NormalizedWrite(outcome, normalized_id, error_id)`. Outcomes: `created`, `duplicate`, `conflict`. |
| `read_normalized(normalized_id)` | Decoded stored source envelope or `None`. |
| `open_read_only(path)` | Existing database connection using SQLite `mode=ro` and `query_only=ON`. Close it explicitly; no evidence API listener is implemented here. |

### Identity proposal requiring Emmanuel/Tranos review

Use `(run_id, source_id, event_id)` as the logical identity. Each retry still has
its own raw receipt and real collection time. Identical source JSON, ignoring key
order and whitespace, links those receipts to the same normalized row. A reused
identity with different content records `event_identity_conflict`, keeps the new
raw receipt unlinked, and leaves the earlier normalized row unchanged. Do not
silently generate a fresh source ID/event ID to conceal that conflict.

`write_normalized` checks that the supplied envelope matches the retained JSON,
refuses ambiguous duplicate JSON keys/non-finite numbers, and guards the storage
identity fields. It is **not** the full schema/semantic validator. Emmanuel must
check schema version, allowed sources/types, UTC, units, quality, finite values
and cross-field meanings before calling it. This initial interface does not
convert payload units or replace source timestamps. Any future transformation
needs a separately reviewed representation that preserves provenance.

Sensor `change_id=None` remains null. Receipt time never replaces sample time.
Derived tables retain foreign-key anchors; later linking/health/rule logic must
verify all supporting identities and run boundaries before populating them.

## Reproduce the checks

From the repository root after the normal Python setup:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m monitor.check_storage --output evidence\YOUR-NEW-CHECK\checks\storage
```

Choose a new output directory each time: the command refuses to overwrite an
existing check. It copies the existing **illustrative fixture**, commits its exact
bytes, validates the envelope, closes/reopens storage and compares the result.
It writes a base64-labelled original-byte export (`source-records.jsonl`), actual
SQLite results (`storage-check.json`), `result.md` and a local `doseproof.db`.
These generated files remain ignored by Git. There is no fabricated screenshot.
The check cannot be presented as a genuine plant/collector capture.

## Actual verification on 29 October 2026

- Python 3.12.10; SQLite 3.49.1, using the existing isolated verification environment.
- `python -m pytest tests -q`: **28 passed** (26 storage checks including parameterized cases; two original starter checks).
- `python -m pip check`: **No broken requirements found**.
- `python -m monitor.check_storage --output evidence\dpm11-fixture-2026-10-29\checks\storage`: exact-byte and source-envelope readback passed; `integrity_check=ok`; no foreign-key errors.
- The fixture run contained one raw and one normalized record, with zero errors,
  linked chains, health records or verdicts. Its source IDs explicitly say
  `illustrative-run-not-captured` / `illustrative-event-not-captured`.
- Tests also exercised separate writer-process exit, malformed/binary receipts,
  retries, conflicts, derived-transaction rollback, orphan refusal, original-record
  mutation rejection, read-only write rejection, unknown-database protection and
  rollback of a failed schema migration without leaving partial tables.

## Review and remaining acceptance

1. Emmanuel: inspect storage behaviour, agree or amend the interface/identity
   proposal and wire it into the DPM-10 collector. Record actual review findings.
2. Tranos: supply one actual produced lab source envelope and confirm its meaning.
3. Together: copy that genuine record through the real collector, restart storage
   and retrieve the same original bytes, producer IDs and source timestamp, with
   the collector's distinct receipt timestamp. Retain actual proof and resolve findings.

**Full source/collector integration: Not run. Shared contract agreement: Pending.
Emmanuel acceptance and Tranos confirmation: Pending. DPM-11 is not Done.**
