# Shared MVP contract brief

Revision 0.1 is the starter interface for team review before implementation. All affected members must record agreement or amendments in docs/decisions.md. The envelope schema is not a complete runtime validator: enforce event-specific semantics, UTC, uniqueness, finite numbers and cross-field checks in implementation.

## Four local application groups

The operator/SCADA side operates the process; controller/model and separate A/B adapters create facts; source publishers send copies; DoseProof checks copies. These are workflow groups on one laptop, not eight servers.

## Event meanings

schema_version is 0.1. Preserve run_id, event_id, source_id, source_seq, event_type, source_timestamp_utc, emitted_at_utc, sim_step and nullable change_id. Collector receipt time is separate metadata, never a replacement source time. Source IDs: operator-desk, controller, plant-model, sensor-a, sensor-b.

Event types: dose_request, dose_approval, command, acknowledgement, plant_feedback, sensor_observation, lab_action and source_heartbeat. payload carries event-specific fields:

- Requests include request_id, actor_id, equipment_id, chemical and requested_feed_mg_s.
- Approvals include approval_id, request_id, approver_id, matching scope/value and expires_at_utc.
- Commands include command_id, request_id, approval_id or null for the explicit lab case, actor_id, equipment_id and requested_feed_mg_s.
- Acknowledgements include command_id, accepted boolean, accepted_feed_mg_s and reason.
- Plant feedback includes equipment_id, flow_l_s, pump_running, actual_delivery_mg_s and modeled_residual_mg_l. New plant runs also include accepted_feed_mg_s for the stopped-pump check. Older records may omit it.
- Sensor observations include equipment_id, value in mg/L and quality good/uncertain/bad; retain null change_id for ordinary observations.
- Lab actions identify actor_id, equipment_id, action and reason. The lab-unapproved path is local, disabled by default and auditable.

Actions share explicit change IDs where appropriate. Sensors sample modeled water separately; proximity in time does not assign a change ID. Missing samples are represented by absence plus source health, not invented zeros. Original event/sample time and emission time remain distinct.

## Connections and storage

Publish copied events to POST http://127.0.0.1:5001/intake/events. The collector retains original request bytes and a unique receipt ID/time before parsing. A duplicate source event has one logical normalized identity, with receipt attempts auditable; a conflicting reuse of an event ID is an error.

Use doseproof.db with raw_events, validation_errors, normalized_events, linked_evidence, source_health and verdicts. Store links to original raw receipt IDs. Raw attempts are preserved; uniqueness is applied to logical normalized identity, not by discarding receipt evidence. The collector is the sole database writer; other processing modules run within that write path or its single worker. The API opens SQLite in read-only mode.

Evidence API at localhost 5002 provides GET /api/health, /api/events, /api/findings and /api/sources plus the dashboard page. Queries accept run_id and bounded limit; event queries may filter source_id/change_id. Reject invalid filters clearly. No treatment control or evidence mutation route exists on this listener. Collector POST is a separate interface, not a public dashboard API.

GET /api/changes reads saved approval/response and labelled fault findings, with action receipts and bounded observation windows. The action deadline is ten seconds for the controller response after command. A missing copy is UNVERIFIED after the collector wait window and can be reevaluated if the original arrives. The stopped-pump check uses the first following plant record. The missing-A check requires ten subsequent plant and B observations without a new A record. These demo thresholds await team review.

## Model and verdicts

Keep the baseline JSON. Positive-flow target residual = max(0, actual_delivery_mg_s / flow_l_s - demand_mg_l). At 15 mg/s and 10 L/s, the target is 1.00 mg/L; at 20 mg/s it is 1.50 mg/L. A command before step 1 leaves residual unchanged through steps 1 to 4; steps 5 to 8 are 1.10, 1.18, 1.244 and 1.2952 mg/L without noise. These are calculated expectations, not captured observations.

Pause freezes simulation advancement while real UTC time continues. Reset restores baseline/seeds and clears queues/faults, creates a new run ID and preserves past evidence. No flow or stopped pump gives zero delivery; never divide by zero and do not invent an unspecified no-flow residual response.

PASS means a named check has consistent sufficient evidence; FAIL means supported discrepancy; PENDING means an expected response is inside its declared waiting window; UNVERIFIED means essential evidence is missing or unreliable. Baseline consistency PASS is not historical approval. Urgency and confidence are separate. A baseline observation does not imply a drinking-water safety certificate.

For the MVP, mark a sensor stale after three consecutive expected one-second steps without a valid sample, using original sample age; by the end of a ten-step missing-A check show it unavailable. Declare the response deadline in each rule/check; use the 64-step settling check where a settled 1.50 mg/L state is required. Source-health gaps prevent an unjustified PASS. All threshold choices require recorded team review.

## Observer register interface

Local observer endpoint: port 1502, device 1, UInt16 Holding Registers; protocol addresses 0 to 12. In order: sensor A, sensor B, flow, requested feed, accepted feed, actual delivery, pump state, ack counter, A quality, B quality, A age, B age, tick counter. First six values scale by 100; pump 0/1; quality 0 good, 1 uncertain, 2 bad, 3 unavailable. Ages saturate at 65535; counters wrap modulo 65536 and must not be used alone as unique event IDs. Retain the last value for unavailable samples with quality/age clearly indicating it.

The observer rejects all network writes, including mixed read/write function requests. Internal snapshot updates remain possible. A private command endpoint must be separate, restricted to the operator-side design and excluded from DoseProof configuration. This native local prototype does not claim protection against a malicious process with full access to the same Windows account.
