# Team decisions

Shared MVP contract revision 0.1: prepared, team agreement pending.
Teaching settings and thresholds: review pending.
All runtime acceptance: Not run.
Human review and actual command/source boundaries must be recorded here; no agreement has been invented.

Membership: Tranos GitHub account tranosmau is approved for invitation. Emmanuel GitHub invitation is explicitly deferred by Thabani.

## DPM-11 implementation proposal — 29 October 2026

Prepared for Emmanuel's review, not agreed: local `EvidenceStore` interface and
migration 001 described in [the storage handoff](dpm-11-storage.md). Proposed
logical identity is `(run_id, source_id, event_id)`; every attempt remains a
separate immutable raw receipt. Initially normalized envelopes preserve source
JSON unchanged; no unit conversion/source-time replacement is introduced.
Payload transformation requires a reviewed extension. Existing event/register
contracts and baseline settings are unchanged. Storage tests/fixture readback
have executed; genuine source capture, collector integration, Tranos confirmation
and Emmanuel acceptance remain pending.

## Integrated evidence-path proposal — 31 October 2026

The new integration branch assembles pending PRs #1–#3 and implements the local
collector and read-only evidence desk. See [the integration guide](integrated-evidence-path.md).
The unchanged source envelope is preserved. Additive GET endpoints for runs,
original receipts and validation errors expose traceability. Five-second future
clock tolerance and the narrow same-step sensor/model rule are proposed for team
review; no approval or production-safety conclusion is implied. Parent tasks and
full MVP scenario acceptance remain pending until actual evidence and human review.
