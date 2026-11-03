# DPM-10 / DPM-13 / DPM-14 — first connected evidence path

This integration branch assembles the pending plant/desk PRs #2/#3 and storage
PR #1 without merging them into main. Their human reviews and shared contract
decisions remain pending. Current owners/reviewers remain unchanged.

## Start on Windows

From this branch's repository root, run the normal Python setup once. Then open
three project terminals and start one service in each:

```powershell
.\.venv\Scripts\python.exe -m monitor.collector_app
.\.venv\Scripts\python.exe -m monitor.api_app
.\.venv\Scripts\python.exe plant\app.py
```

Open **http://127.0.0.1:5002** for evidence. The separate operator desk is on
port 5000, read-only Modbus observer on 1502 and private operator controller on
1503. Configure each person's own desk password privately using the inherited
`python -m plant.desk_users set <name>` instructions. No accounts or passwords
are created by this milestone. Start FUXA separately if needed; the evidence
dashboard does not require FUXA.

Collector and API bind loopback explicitly. `MVP_DATABASE` selects a database
path (default: repository-root `doseproof.db`); use the same path in both
terminals. `MVP_COLLECTOR_PORT` and `MVP_API_PORT` select ports. Change the plant's
collector port too if necessary. The existing PowerShell service launcher works
with the new entrypoints. Never kill another service to free a port.

## Follow one event

1. The real plant model advances one tick per second. Separate sensor adapters
   sample its water state; the model/sensors produce original event IDs and times.
2. The publisher fsyncs each JSONL record locally, then copies it by HTTP. It
   bypasses outbound proxy settings for these local connections. Failed deliveries
   retry with a delay increasing from 0.25 to at most 5 seconds. A cursor advances
   only after the collector returns a durable receipt. Older run outboxes are
   replayed on plant startup with their original producer IDs/timestamps.
3. The collector serializes writes and commits exact request bytes before
   parsing, content-type checks or validation. Bad input receives HTTP 422 plus
   an error/receipt ID. Identity conflict receives 409; both retain originals.
   Persistence failure receives 503 and triggers retry. The 1 MiB transport
   limit returns an explicit 413 with `retained=false`; it is not evidence accepted.
4. The validator checks the unchanged v0.1 envelope, allowed source/type pairs,
   nonblank identities, explicit UTC, sample-before-emission order, finite
   nonnegative values and event-specific fields. Unsupported sensor units and
   qualities are rejected. Dates may be historical for replay. An emission more
   than five seconds ahead of receipt UTC is rejected (reviewable clock-tolerance
   proposal). Expired or missing approvals are not silently invented; approval
   assurance is a separate future check.
5. Normalization retains the original validated envelope in canonical JSON,
   with unchanged units, source timestamps and nullable change ID. No implicit
   ppm conversion or sensor-to-command assignment occurs. Repeated identities
   keep separate raw receipts but one normalized event; conflicting content
   cannot replace existing evidence.
6. A narrow initial correlation joins plant-model, sensor-a and sensor-b by
   **run ID and simulation step**. It checks configured equipment identities,
   good quality and A/B agreement with modeled water within ±0.01 mg/L. Complete
   supported agreement gives PASS; disagreement gives FAIL; ambiguous/conflicting
   observations or poor quality give UNVERIFIED. Every result stores reasons and
   supporting raw receipt IDs. Incomplete sets produce no PASS. A later identity
   conflict invalidates that step's earlier supported result.
7. The API reads only saved SQLite evidence. The dashboard polls these GET
   endpoints, displays source/sample/receipt times and links to original bytes.
   Receipt is not an assurance result, and a historical consistency PASS is not
   proof of approval, fresh monitoring or water safety.

The publisher records collector receipts/rejections in an adjacent delivery log.
HTTP 422/409 with a retained receipt is terminal for that unchanged event; it is
not retried forever. Correct a producer problem with a new traceable event, not
by overwriting a source identity. A crash after receipt but before cursor save
may replay one event safely. Spool/cursor files must not be edited or truncated.
The single-host local disk remains a shared failure point.

## Read-only evidence API

| GET endpoint | Saved evidence / bounds |
| --- | --- |
| `/api/health` | Database readable and counts. Does not claim plant health. |
| `/api/runs` | Latest captured run IDs. Optional limit. |
| `/api/events` | Valid saved envelopes, normalized/receipt IDs and receipt time; run/source/change filters. |
| `/api/findings` | Saved explained sensor/model consistency findings, supporting IDs and scope. |
| `/api/sources` | Latest measured source records and original-sample age for the selected run. |
| `/api/receipts/<id>` | Exact original body in labelled base64, hash, content type, receipt time and linked errors. |
| `/api/errors` | Retained validation/identity errors across runs; invalid input may have no trustworthy run ID. |

List limits default to 50 and must be 1–200. Unknown, repeated or invalid query
parameters are refused. Without a run filter, queries select the latest captured
run; run selection in the dashboard prevents mixing historical runs. POST, PUT,
PATCH, DELETE and OPTIONS on the evidence listener are refused. It has no plant
imports, control routes or usable command credentials. A missing database returns
503 and is never created by the reader.

Source freshness uses original UTC sample time: stale at three seconds,
unavailable at ten. Bad/uncertain quality and future clock skew are shown
explicitly. Retained values stay visible with their age; no fresh zero is
invented. These are the runbook's proposed teaching thresholds, still awaiting
team agreement. Incomplete/missing sets do not receive fabricated verdicts.
Current source-health warnings are separate from historical check results.

## Reproduce and capture

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts\verify-evidence-path.py --output evidence\YOUR-NEW-CHECK --serve-seconds 300
```

The capture helper launches the actual plant process, separate HTTP collector/API
listeners, waits for real generated events, interrupts/restarts collection,
observes replay, retrieves exact bytes and probes invalid input and API write
refusal. It uses unused loopback ports and prints the actual dashboard URL.
Only its own child process/listeners are stopped on completion. The optional
five-minute window allows a person to inspect and capture the actual dashboard.
No process screenshot or approval history is generated.

Generated logs, source records, SQLite file and `trace.json` stay in ignored local
evidence folders. Use new output folders to preserve previous runs. Record actual
reviewer findings and a screenshot from the live page when the browser is available.

## Remaining work

This is the baseline vertical slice. It does not implement full authorization-chain
assurance, delayed-response deadlines/PENDING transitions, stopped-pump or missing-A
scenario controls, production source authentication, tamper-proof storage, remote
deployment or external notifications. Those task definitions remain pending.
The operator model supports approved changes, but this milestone's automated
assurance does not claim that it has validated the approval chain.

Human reviewers: Emmanuel for storage/API/dashboard meanings, Tranos for
collector/source integration, Thabani for plant/integration review. No AI output,
test success or assembly of PR commits substitutes for their acceptance.
