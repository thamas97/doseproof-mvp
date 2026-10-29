# DoseProof three person MVP runbook

## How to use this runbook

We are preparing a working DoseProof MVP across all eight layers by Tuesday 3 November 2026 for the professor review on Wednesday 4 November. Thabani, Tranos and Emmanuel each commit four hours every day from Thursday 29 October through Tuesday 3 November, including the weekend: 24 hours each and 72 team-hours total.

This runbook explains what each person builds, the input needed from colleagues, how ChatGPT, Codex and Claude support the work, what must be observed and what evidence makes a handoff reviewable. The repository and board are separate from the original six-person project.

Current status is preparation, not a completed MVP. Runtime services are to be implemented, all scenario results begin Not run, and reviewer acceptance remains pending. Starter schema/arithmetic checks are not evidence that treatment simulation, monitoring or protection works.

Start with the shared contract brief and your Day 1 card. Follow the daily brief, use a small branch, demonstrate the result to your reviewer and save actual evidence. Do not mark a task Done because an AI produced code or the calendar day ended.

Board: https://mail-team-bpbflevn.atlassian.net/jira/software/projects/DPM/boards/2

Timeline: https://mail-team-bpbflevn.atlassian.net/jira/software/projects/DPM/boards/2/timeline

Private repository: https://github.com/thamas97/doseproof-mvp

Readiness is judged by working behaviour and evidence. If the first full path is not working by Friday, focus on integration and report the deadline risk; do not hide missing layers behind a polished mock.

## Contents and ownership

1. Scope and architecture
2. Working agreements and capacity
3. Setup and service interfaces
4. Shared data and model meanings
5. Acceptance checks and evidence
6. AI workflow and nine master prompts
7. Eighteen dated member task briefs
8. Troubleshooting and handoffs
9. Tuesday readiness and Wednesday demonstration
10. References and known limitations

| Member | Primary responsibility | Human reviewer |
| --- | --- | --- |
| Tranos | Layer 1 model controller desk sensors FUXA and publishers | Thabani |
| Emmanuel | Layers 2 to 5 collection quality linking health and rules | Tranos |
| Thabani | Layers 6 to 8 SQLite GET API dashboard and integration | Emmanuel |

These are coordination boundaries, not three isolated products. Each member supplies interface feedback, peer review and integrated evidence. Emmanuel requests/observes in the demo; Thabani approves; Tranos operates labelled lab controls. These roles must be configured as actual local lab identities before execution. Donald and Stephen are not required actors in the MVP.

## Scope and architecture

The MVP preserves eight workflow stages, not eight servers. All equipment is simulated on one laptop. The operator desk requests, approves and executes changes through the controller; FUXA reads process snapshots. The modeled pump changes actual delivery; A and B independently sample the same modeled water through separate software adapters.

Copied request/approval/command/response, plant-feedback and sensor events go by HTTP JSON to DoseProof. The collector preserves originals before validation. Only valid normalized records enter ordinary correlation; errors remain visible. Linking and source health support deterministic explained findings saved in SQLite. A read-only evidence API serves the dashboard and on-screen alerts.

DoseProof sends no commands back to the process. Requested setting, approved/accepted setting, command acknowledgement, actual delivery, modeled water and sensor measurement are distinct. One laptop and a shared model still create shared failure modes. No result is a drinking-water safety certificate.

| Layer | Owner | Minimum output |
| --- | --- | --- |
| 1 Simulated water treatment system | Tranos | A resettable model, authenticated request and approval desk, actual delivery, two sensor adapters and a saved read-only FUXA view. |
| 2 Connectors collect event copies | Emmanuel | Original event copies delivered by HTTP POST with retained IDs, timestamps and a bounded retry/outbox path. |
| 3 Validate and normalize | Emmanuel | Valid records normalized with explicit units; original bad inputs and validation reasons retained. |
| 4 Link evidence and check source health | Emmanuel | Action chains linked by explicit IDs; missing or stale valid samples remain visible. |
| 5 Apply rules and explain results | Emmanuel | Deterministic explained PASS, FAIL, PENDING and UNVERIFIED findings with supporting record IDs. |
| 6 SQLite evidence database | Thabani | One local database retains originals, errors, normalized records, links, health and findings through restart. |
| 7 Read only evidence API | Thabani | GET-only evidence, finding and source-health endpoints with bounded queries and no command routes. |
| 8 Dashboard and alerts | Thabani | A live evidence timeline, distinct A/B readings, confidence, urgency, status explanations and on-screen alerts. |

Keep five scenario families: baseline, approved change, labelled lab-unapproved change, stopped pump and missing A. Defer no-flow, ignored-command, reduced-delivery, delayed, stuck and biased-sensor variants as additional runtime demonstrations; preserve their full-project definitions without claiming they passed. Cloud hosting, SMS/email, AI-driven operational verdicts and extra animation are outside this timebox.

## Working agreements and capacity

Use one four-hour card per person per day. The card includes implementation, review and coordination; do not estimate its checklist again as additional hours. Layer epics have no effort estimate.

| Daily activity | Minutes per person | Six-day team hours |
| --- | --- | --- |
| Coordination and blockers | 15 | 4.5 |
| Implementation setup and focused checks | 130 | 39 |
| Human and AI-assisted review | 35 | 10.5 |
| Integration evidence and Jira update | 30 | 9 |
| Troubleshooting reserve | 30 | 9 |
| Total | 240 | 72 |

Board columns: Backlog, Ready, In Progress, Review, Done. Start in Backlog; Ready requires understood inputs and acceptance. Maximum three In Progress with one actively owned card per member; maximum two awaiting Review. Blocked cards stay in their current column, retain a flag and count toward that limit.

After fifteen blocked minutes, record the plan/Jira ID, exact error, missing input, attempted correction, person who can help and next action. Clear review queues before starting more work. A reviewer must check the actual output, not simply repeat an AI opinion.

Done requires the card acceptance to pass, evidence to be retained, reviewer findings to be resolved and human confirmation recorded. Record the real PR/commit and result. Do not auto-close parent epics or unrelated DOS cards. Sunday is the feature freeze; Monday and Tuesday protect correctness, evidence and rehearsal.

Maintain one shared contract revision, one integration branch and one agreed demonstration laptop. Never let two AI tools edit the same working directory concurrently. Use small task branches and pull before integration. Reserve time is part of the budget, not an extra commitment.

## Setup and service interfaces

Use Python 3.12, Flask, PyModbus, SQLite and Node/FUXA. The reviewed starter selects FUXA 1.3.4 and PyModbus 3.16.1; verify compatibility on the actual machines and retain the installed dependency lock. Do not silently upgrade tools to chase warnings.

Clone the private repository after accepting access. Tranos account is tranosmau; Emmanuel invitation is deferred until Thabani arranges it. Until then, do not share another member credentials. Use a reviewed archive or paired session for agreed work if repository access is unavailable.

Run these from a short local repository folder in PowerShell:

~~~powershell
py -3.12 --version
node --version
npm.cmd --version
git --version
powershell -NoProfile -File .\scripts\setup-python.ps1
.\.venv\Scripts\python.exe -m pytest tests/test_contract_files.py
npm.cmd --prefix fuxa ci
~~~

The setup helper creates a project virtual environment, installs the lock or development inputs, runs pip check, records a lock and verifies key imports. The two starter tests check contract format and teaching arithmetic only. Record actual versions and failures. Tranos must configure the FUXA loopback settings described in fuxa/README.md before startup.

After the assigned runtime entrypoints exist, start separate project windows in this order:

~~~powershell
powershell -NoProfile -File .\scripts\start-mvp.ps1 -Service collector
powershell -NoProfile -File .\scripts\start-mvp.ps1 -Service plant
powershell -NoProfile -File .\scripts\start-mvp.ps1 -Service api
npm.cmd --prefix fuxa start
~~~

These are planned runtime interfaces to implement and verify. The supplied launcher stops with an honest error when an entrypoint is missing.

| Service | Local interface | Responsibility |
| --- | --- | --- |
| Operator desk | 127.0.0.1 port 5000 | Tranos named request approval and execution |
| Collector | 127.0.0.1 port 5001 POST /intake/events | Emmanuel intake and single writer processing |
| Evidence API and dashboard | 127.0.0.1 port 5002 GET only | Thabani read-only SQLite connection |
| FUXA | 127.0.0.1 port 1881 | Tranos process display |
| Observer Modbus | 127.0.0.1 port 1502 device 1 | Read-only snapshots and rejected writes |

The operator-side private command path is distinct from the observer and excluded from DoseProof configuration. Decide and test its access control as part of Tranos control implementation. A loopback address alone is not production isolation.

For FUXA use holding registers and 1000 ms polling. Check protocol address zero against UI address one using independent readback; apply scaling once. Save Project and export JSON after configuration. Shut down with Ctrl+C only in this project service windows. Never kill an unrelated process to free a port.

## Shared data and model meanings

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
- Plant feedback includes equipment_id, flow_l_s, pump_running, actual_delivery_mg_s and modeled_residual_mg_l.
- Sensor observations include equipment_id, value in mg/L and quality good/uncertain/bad; retain null change_id for ordinary observations.
- Lab actions identify actor_id, equipment_id, action and reason. The lab-unapproved path is local, disabled by default and auditable.

Actions share explicit change IDs where appropriate. Sensors sample modeled water separately; proximity in time does not assign a change ID. Missing samples are represented by absence plus source health, not invented zeros. Original event/sample time and emission time remain distinct.

## Connections and storage

Publish copied events to POST http://127.0.0.1:5001/intake/events. The collector retains original request bytes and a unique receipt ID/time before parsing. A duplicate source event has one logical normalized identity, with receipt attempts auditable; a conflicting reuse of an event ID is an error.

Use doseproof.db with raw_events, validation_errors, normalized_events, linked_evidence, source_health and verdicts. Store links to original raw receipt IDs. Raw attempts are preserved; uniqueness is applied to logical normalized identity, not by discarding receipt evidence. The collector is the sole database writer; other processing modules run within that write path or its single worker. The API opens SQLite in read-only mode.

Evidence API at localhost 5002 provides GET /api/health, /api/events, /api/findings and /api/sources plus the dashboard page. Queries accept run_id and bounded limit; event queries may filter source_id/change_id. Reject invalid filters clearly. No treatment control or evidence mutation route exists on this listener. Collector POST is a separate interface, not a public dashboard API.

## Model and verdicts

Keep the baseline JSON. Positive-flow target residual = max(0, actual_delivery_mg_s / flow_l_s - demand_mg_l). At 15 mg/s and 10 L/s, the target is 1.00 mg/L; at 20 mg/s it is 1.50 mg/L. A command before step 1 leaves residual unchanged through steps 1 to 4; steps 5 to 8 are 1.10, 1.18, 1.244 and 1.2952 mg/L without noise. These are calculated expectations, not captured observations.

Pause freezes simulation advancement while real UTC time continues. Reset restores baseline/seeds and clears queues/faults, creates a new run ID and preserves past evidence. No flow or stopped pump gives zero delivery; never divide by zero and do not invent an unspecified no-flow residual response.

PASS means a named check has consistent sufficient evidence; FAIL means supported discrepancy; PENDING means an expected response is inside its declared waiting window; UNVERIFIED means essential evidence is missing or unreliable. Baseline consistency PASS is not historical approval. Urgency and confidence are separate. A baseline observation does not imply a drinking-water safety certificate.

For the MVP, mark a sensor stale after three consecutive expected one-second steps without a valid sample, using original sample age; by the end of a ten-step missing-A check show it unavailable. Declare the response deadline in each rule/check; use the 64-step settling check where a settled 1.50 mg/L state is required. Source-health gaps prevent an unjustified PASS. All threshold choices require recorded team review.

## Observer register interface

Local observer endpoint: port 1502, device 1, UInt16 Holding Registers; protocol addresses 0 to 12. In order: sensor A, sensor B, flow, requested feed, accepted feed, actual delivery, pump state, ack counter, A quality, B quality, A age, B age, tick counter. First six values scale by 100; pump 0/1; quality 0 good, 1 uncertain, 2 bad, 3 unavailable. Ages saturate at 65535; counters wrap modulo 65536 and must not be used alone as unique event IDs. Retain the last value for unavailable samples with quality/age clearly indicating it.

The observer rejects all network writes, including mixed read/write function requests. Internal snapshot updates remain possible. A private command endpoint must be separate, restricted to the operator-side design and excluded from DoseProof configuration. This native local prototype does not claim protection against a malicious process with full access to the same Windows account.

## Acceptance checks and evidence

All checks below start Not run. Use a fresh reset/run for each scenario and restore normal lab settings afterward. These MVP check IDs are local to this repository; they do not rename or accept the original DOS-4 definitions.

Save evidence/<run_id>/checks/<check_id>/source-records.jsonl, screen.png and result.md. The first is a clearly labelled original-record export; the screenshot must be captured from execution; result.md records settings/seeds, commit, action, expectations, actual observations, record IDs, result, reviewer and cleanup. A reference is not a pass until its evidence exists.

Model arithmetic tolerance is 0.000001 mg/L at matching steps. Normal raw sensor values allow 0.01 mg/L noise relative to the corresponding modeled state. For quantized displays allow one 0.01-unit increment relative to the source value and apply scaling once. Do not compare samples from different times as if simultaneous.

### AC-00 Baseline consistency
Fresh baseline; observe ten steps with 10 L/s flow, 15 mg/s delivery and 1.00 mg/L modeled residual. A and B have separate identities and noise within 0.01 mg/L. Initialization is not approval history.

Owner and reviewer: Tranos / Thabani. Result: Not run. Review: Pending.

### AC-01 Approved change
Fresh baseline; Emmanuel requests 20 mg/s and Thabani approves its matching scope. Command before step 1: residual unchanged through 1 to 4; steps 5 to 8 expected 1.10, 1.18, 1.244, 1.2952 mg/L without noise. Separate acknowledgement, delivery and samples.

Owner and reviewer: Tranos / Thabani. Result: Not run. Review: Pending.

### AC-02 Labelled lab unapproved change
Fresh baseline; Tranos enables the explicit local lab path and applies 20 mg/s without an approval. Preserve actor, attempted action, acknowledgement and actual effect. Normal authorization remains enforced outside the lab path.

Owner and reviewer: Emmanuel / Tranos. Result: Not run. Review: Pending.

### AC-03 Stopped pump
Fresh approved 20 mg/s run; advance 64 steps and check residual within 0.000001 mg/L of 1.50. Stop pump. Accepted feed remains 20; delivery becomes zero; water follows the delayed model.

Owner and reviewer: Emmanuel / Tranos. Result: Not run. Review: Pending.

### AC-04 Missing Sensor A
Fresh run; suppress A for ten steps. No new A samples; B and plant continue. Retained A value ages and is unavailable by the window end. No fresh zero or synthetic sample is created.

Owner and reviewer: Emmanuel / Tranos. Result: Not run. Review: Pending.

### AC-05 Malformed and invalid input
Retain malformed JSON and wrong-unit/identity inputs with actual validation errors; do not normalize or correlate them as trusted records.

Owner and reviewer: Emmanuel / Tranos. Result: Not run. Review: Pending.

### AC-06 Duplicate and conflicting event identity
Replay identical event: receipt attempts are auditable but one logical normalized event/finding. Reused event identity with different content is an explicit error.

Owner and reviewer: Emmanuel / Tranos. Result: Not run. Review: Pending.

### AC-07 Retry and restart integrity
Interrupt intake then restore it; local outbox retries preserve producer IDs/times. Restart storage/API and retrieve prior originals and findings. Check database integrity and references.

Owner and reviewer: Thabani / Emmanuel. Result: Not run. Review: Pending.

### AC-08 Passive boundary
Attempt single, multi and mixed register writes on observer and confirm refusal with unchanged plant state. POST/PUT/PATCH/DELETE against evidence API must be refused. Inspect code/config for usable command credentials or routes.

Owner and reviewer: Thabani / Emmanuel. Result: Not run. Review: Pending.

### AC-09 Reset and repeatability
Reset clears model queues/faults, restores seeds/baseline and starts a new run without deleting prior evidence. Repeated actions match by simulation step; UTC times and unique IDs may differ.

Owner and reviewer: Tranos / Thabani. Result: Not run. Review: Pending.

### AC-10 Independent startup and presentation
Another member follows setup/start instructions from the reviewed candidate, displays actual saved evidence, explains each result and records limitations.

Owner and reviewer: Thabani / Emmanuel. Result: Not run. Review: Pending.

When evidence is missing, keep the gap visible. FAIL means a supported discrepancy, not merely a missing file. The same-host and shared-model limitations belong in the result notes. Preserve original UTC sample time even when emission is delayed; receipt time is a third timestamp. No sensor inherits a change ID simply because it was observed after a command.

## AI workflow and prompt pack

Use all three tools deliberately within the daily budget. ChatGPT explains the task and expected checks; Codex edits and runs focused code; Claude in the browser reviews selected changes and actual output. Human reviewers own acceptance. No AI tool makes operational treatment decisions.

Create one ChatGPT project if available and provide the shared MVP brief, contract revision and current task. In Claude, upload or paste only the relevant task, selected diff and actual test output; it does not automatically see your private repository or another chat. If Claude is unavailable, record that gap and use the human reviewer without claiming AI review occurred.

Before every coding session provide the actual Jira key, branch, allowed paths, predecessor outputs, expected checks and evidence destination. Attach fresh failures rather than repeatedly asking for general rewrites. Do not paste credentials, authentication tokens or unrelated personal files.

After Codex finishes, ask for the actual command output, changed files, remaining failures and evidence paths. Compare that with the repository. Give Claude this real review packet and ask it to distinguish demonstrated defects from untested concerns. Resolve findings with the human reviewer before merging.

The next three sections contain nine copyable master prompts. Add the specific daily brief that follows. Prompt text is instruction for the tool you choose to use, not a claim that any tool has already run.

## Tranos master prompts

### ChatGPT
Read the shared MVP brief, contract v0.1, your daily Jira card and the latest review findings. This is an educational simulation, not drinking-water operating guidance. Preserve requested/accepted feed, acknowledgement, actual delivery and sensor observations as different meanings. Do not fabricate events, approval, tests or screenshots. Do not alter another member owned module or a shared contract without agreement. Do not put secrets in the prompt or a commit. Report what you actually inspected and ran. I am Tranos, responsible for plant and FUXA. Explain today task in beginner language. Identify required inputs from colleagues, break the implementation into four steps within 130 minutes, explain the expected observable result, and list three mistakes I should check. Ask only about missing decisions that the supplied brief does not resolve. Do not invent existing code or a completed result.

### Codex
Read the shared MVP brief, contract v0.1, your daily Jira card and the latest review findings. This is an educational simulation, not drinking-water operating guidance. Preserve requested/accepted feed, acknowledgement, actual delivery and sensor observations as different meanings. Do not fabricate events, approval, tests or screenshots. Do not alter another member owned module or a shared contract without agreement. Do not put secrets in the prompt or a commit. Report what you actually inspected and ran. I am implementing plant and FUXA. Inspect the current repository and actual Jira task before editing. Work on a branch named with the real DPM issue key. Limit changes to plant, fuxa and plant-specific tests. Implement the smallest complete task, add meaningful behavioural checks, run them and show observed output. If the task needs an unimplemented interface, report that dependency; do not hide it behind a production-looking mock. At handoff list files changed, checks run, actual results, evidence paths and remaining issues. Never mark the Jira task Done or claim human approval for me.

### Claude
Read the shared MVP brief, contract v0.1, your daily Jira card and the latest review findings. This is an educational simulation, not drinking-water operating guidance. Preserve requested/accepted feed, acknowledgement, actual delivery and sensor observations as different meanings. Do not fabricate events, approval, tests or screenshots. Do not alter another member owned module or a shared contract without agreement. Do not put secrets in the prompt or a commit. Report what you actually inspected and ran. Independently review the attached task, selected diff, contract and actual test output for plant and FUXA. You are reviewing in the browser, not editing this repository. Identify concrete correctness/evidence gaps, distinguish an observed defect from an untested concern, and suggest a reproduction or focused check for each. Do not infer files or test results that were not supplied. End with questions for Thabani, the human reviewer; do not create an acceptance sign-off.

## Emmanuel master prompts

### ChatGPT
Read the shared MVP brief, contract v0.1, your daily Jira card and the latest review findings. This is an educational simulation, not drinking-water operating guidance. Preserve requested/accepted feed, acknowledgement, actual delivery and sensor observations as different meanings. Do not fabricate events, approval, tests or screenshots. Do not alter another member owned module or a shared contract without agreement. Do not put secrets in the prompt or a commit. Report what you actually inspected and ran. I am Emmanuel, responsible for copied evidence processing. Explain today task in beginner language. Identify required inputs from colleagues, break the implementation into four steps within 130 minutes, explain the expected observable result, and list three mistakes I should check. Ask only about missing decisions that the supplied brief does not resolve. Do not invent existing code or a completed result.

### Codex
Read the shared MVP brief, contract v0.1, your daily Jira card and the latest review findings. This is an educational simulation, not drinking-water operating guidance. Preserve requested/accepted feed, acknowledgement, actual delivery and sensor observations as different meanings. Do not fabricate events, approval, tests or screenshots. Do not alter another member owned module or a shared contract without agreement. Do not put secrets in the prompt or a commit. Report what you actually inspected and ran. I am implementing copied evidence processing. Inspect the current repository and actual Jira task before editing. Work on a branch named with the real DPM issue key. Limit changes to monitor collection, validation, linking, health and rules modules and their tests. Implement the smallest complete task, add meaningful behavioural checks, run them and show observed output. If the task needs an unimplemented interface, report that dependency; do not hide it behind a production-looking mock. At handoff list files changed, checks run, actual results, evidence paths and remaining issues. Never mark the Jira task Done or claim human approval for me.

### Claude
Read the shared MVP brief, contract v0.1, your daily Jira card and the latest review findings. This is an educational simulation, not drinking-water operating guidance. Preserve requested/accepted feed, acknowledgement, actual delivery and sensor observations as different meanings. Do not fabricate events, approval, tests or screenshots. Do not alter another member owned module or a shared contract without agreement. Do not put secrets in the prompt or a commit. Report what you actually inspected and ran. Independently review the attached task, selected diff, contract and actual test output for copied evidence processing. You are reviewing in the browser, not editing this repository. Identify concrete correctness/evidence gaps, distinguish an observed defect from an untested concern, and suggest a reproduction or focused check for each. Do not infer files or test results that were not supplied. End with questions for Tranos, the human reviewer; do not create an acceptance sign-off.

## Thabani master prompts

### ChatGPT
Read the shared MVP brief, contract v0.1, your daily Jira card and the latest review findings. This is an educational simulation, not drinking-water operating guidance. Preserve requested/accepted feed, acknowledgement, actual delivery and sensor observations as different meanings. Do not fabricate events, approval, tests or screenshots. Do not alter another member owned module or a shared contract without agreement. Do not put secrets in the prompt or a commit. Report what you actually inspected and ran. I am Thabani, responsible for persistence and presentation. Explain today task in beginner language. Identify required inputs from colleagues, break the implementation into four steps within 130 minutes, explain the expected observable result, and list three mistakes I should check. Ask only about missing decisions that the supplied brief does not resolve. Do not invent existing code or a completed result.

### Codex
Read the shared MVP brief, contract v0.1, your daily Jira card and the latest review findings. This is an educational simulation, not drinking-water operating guidance. Preserve requested/accepted feed, acknowledgement, actual delivery and sensor observations as different meanings. Do not fabricate events, approval, tests or screenshots. Do not alter another member owned module or a shared contract without agreement. Do not put secrets in the prompt or a commit. Report what you actually inspected and ran. I am implementing persistence and presentation. Inspect the current repository and actual Jira task before editing. Work on a branch named with the real DPM issue key. Limit changes to monitor storage and API modules, dashboard, setup scripts and integration tests. Implement the smallest complete task, add meaningful behavioural checks, run them and show observed output. If the task needs an unimplemented interface, report that dependency; do not hide it behind a production-looking mock. At handoff list files changed, checks run, actual results, evidence paths and remaining issues. Never mark the Jira task Done or claim human approval for me.

### Claude
Read the shared MVP brief, contract v0.1, your daily Jira card and the latest review findings. This is an educational simulation, not drinking-water operating guidance. Preserve requested/accepted feed, acknowledgement, actual delivery and sensor observations as different meanings. Do not fabricate events, approval, tests or screenshots. Do not alter another member owned module or a shared contract without agreement. Do not put secrets in the prompt or a commit. Report what you actually inspected and ran. Independently review the attached task, selected diff, contract and actual test output for persistence and presentation. You are reviewing in the browser, not editing this repository. Identify concrete correctness/evidence gaps, distinguish an observed defect from an untested concern, and suggest a reproduction or focused check for each. Do not infer files or test results that were not supplied. End with questions for Emmanuel, the human reviewer; do not create an acceptance sign-off.

## Day 1 Tranos Build the baseline plant and first FUXA connection

Date: Thursday 29 October 2026. Jira: DPM-9. Owner: Tranos. Human reviewer: Thabani. Total allowance: four hours including review and reserve.

Primary layer: 1. Dependencies: Shared MVP brief and Day 1 contract review. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-9.

### Inputs and allowed changes
Shared contract v0.1, baseline settings and the observer register map. Work only within plant, fuxa and plant-specific tests. Agree shared interface changes before editing.

### Implementation checklist
1. Create a Python 3.12 virtual environment and verify PyModbus imports. Start from the reviewed starter pattern; record the actual versions. (40 minutes)
2. Implement one-second model ticks, 10 L/s flow, 15 mg/s healthy delivery, 0.50 mg/L demand and separate seeded A/B measurement adapters. (35 minutes)
3. Expose the 13 observer snapshot registers on localhost port 1502. Configure FUXA device 1, one-second polling and scaling once. (35 minutes)
4. Publish baseline feedback and A/B observation copies; retain producer IDs/times. Keep initialization distinct from historical approval. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_plant_baseline.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Version record, source JSONL excerpt, independent register readback and an actual FUXA screenshot. Handoff to Emmanuel for collection and Thabani for storage. Acceptance: A and B have different source identities and sample the modeled water; scaled values agree with source records. FUXA configuration is saved.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 1 Emmanuel Collect source copies and validate the first envelope

Date: Thursday 29 October 2026. Jira: DPM-10. Owner: Emmanuel. Human reviewer: Tranos. Total allowance: four hours including review and reserve.

Primary layer: 2. Dependencies: Shared MVP brief and Day 1 contract review. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-10.

### Inputs and allowed changes
Shared event envelope, Tranos source examples and Thabani raw-write function signature. Work only within monitor collection, validation, linking, health and rules modules and their tests. Agree shared interface changes before editing.

### Implementation checklist
1. Agree required envelope fields with both colleagues. Mark fixtures as illustrative and keep them separate from captured runs. (40 minutes)
2. Build the localhost collector route POST /intake/events. Preserve request bytes and collector receipt time before JSON/schema processing. (35 minutes)
3. Validate required identities, schema version, UTC times and event-specific value/unit/quality fields. Record errors without silently filling missing evidence. (35 minutes)
4. Call the agreed SQLite writer, test valid and malformed inputs, and return a receipt that does not imply a PASS verdict. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_intake.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Collector checks, one actual received source record and linked raw/error IDs. Handoff to Thabani for persistence and Tranos for publisher feedback. Acceptance: Original producer identity/time survive intake; malformed input is retained with a validation error and never enters ordinary correlation.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 1 Thabani Prepare shared contracts and durable raw storage

Date: Thursday 29 October 2026. Jira: DPM-11. Owner: Thabani. Human reviewer: Emmanuel. Total allowance: four hours including review and reserve.

Primary layer: 6. Dependencies: Shared MVP brief and Day 1 contract review. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-11.

### Inputs and allowed changes
Approved MVP scope, new repository/board and the source baseline. Work only within monitor storage and API modules, dashboard, setup scripts and integration tests. Agree shared interface changes before editing.

### Implementation checklist
1. Review the repository/board links and confirm shared contract ownership. Keep setup changes inside the MVP workspace. (40 minutes)
2. Create doseproof.db with the six agreed record categories. Keep raw bytes and receipt metadata distinct from derived fields. (35 minutes)
3. Provide a transactional write_raw operation and a read-by-ID operation for Emmanuel. Enable foreign keys and unique event identity handling. (35 minutes)
4. Persist one genuine copied source record, restart the storage connection and retrieve the same bytes and producer identifiers. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_storage.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Schema migration, storage checks and a raw-record retrieval excerpt after reconnect. Handoff to Emmanuel for collector integration and Tranos for source-record confirmation. Acceptance: Raw records are durable before derived processing; reviewer can retrieve the original and see actual source time versus receipt time.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 2 Tranos Add named request approval and command response

Date: Friday 30 October 2026. Jira: DPM-12. Owner: Tranos. Human reviewer: Thabani. Total allowance: four hours including review and reserve.

Primary layer: 1. Dependencies: DPM-9, DPM-10, DPM-11. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-12.

### Inputs and allowed changes
Baseline plant, actor/approval contract and private operator-side command design. Work only within plant, fuxa and plant-specific tests. Agree shared interface changes before editing.

### Implementation checklist
1. Implement local named-user login without committed passwords. Configure Emmanuel as requester, Thabani as approver and Tranos as lab operator. (40 minutes)
2. Enforce a different requester and approver; match request ID, target, equipment, chemical, validity window and requested value before execution. (35 minutes)
3. Execute an approved change through the operator-side Modbus path. Record request, approval, command and acknowledgement separately. (35 minutes)
4. Update accepted feed, actual delivery and observer tags separately; emit the corresponding source records for the first complete data path. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_desk_authorization.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Actual named action records, ack/feedback records and FUXA view after a setting change. Handoff to Emmanuel for chain linking and Thabani for the timeline. Acceptance: Self-approval is refused. An acknowledgement does not automatically assert delivery or an immediate sensor change.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 2 Emmanuel Normalize link and explain the baseline path

Date: Friday 30 October 2026. Jira: DPM-13. Owner: Emmanuel. Human reviewer: Tranos. Total allowance: four hours including review and reserve.

Primary layer: 3. Dependencies: DPM-10, DPM-11, DPM-9. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-13.

### Inputs and allowed changes
Persisted intake, agreed event types and baseline/model expectations. Work only within monitor collection, validation, linking, health and rules modules and their tests. Agree shared interface changes before editing.

### Implementation checklist
1. Normalize only valid events into the agreed units while retaining their raw IDs. Reject impossible values and unsupported units explicitly. (40 minutes)
2. Build initial run/source/equipment indexes and action-chain matching. Sensor observations retain null change_id unless a source explicitly supplies a valid association. (35 minutes)
3. Track each source last valid sample time and expose an initial baseline consistency rule with a clear explanation and evidence IDs. (35 minutes)
4. Send a genuine baseline run through all stages; ensure baseline consistency PASS does not claim an approval history. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_normalization_health.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Normalized records, one linked evidence example and an explained baseline finding. Handoff to Thabani for API/dashboard and Tranos for source checks. Acceptance: One actual source event can be traced from original bytes through normalized evidence and a saved finding. Unknown essentials remain UNVERIFIED.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 2 Thabani Expose saved evidence and the first complete dashboard path

Date: Friday 30 October 2026. Jira: DPM-14. Owner: Thabani. Human reviewer: Emmanuel. Total allowance: four hours including review and reserve.

Primary layer: 7. Dependencies: DPM-11, DPM-10, DPM-9. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-14.

### Inputs and allowed changes
SQLite writer/read functions and Emmanuel normalized/finding examples. Work only within monitor storage and API modules, dashboard, setup scripts and integration tests. Agree shared interface changes before editing.

### Implementation checklist
1. Implement GET /api/events, /api/findings and /api/sources plus GET /api/health. Use a separate SQLite read-only connection. (40 minutes)
2. Serve the dashboard page and fetch saved records with bounded polling; keep the collector POST route on a separate listener. (35 minutes)
3. Show source identity, sample time, receipt time, value/unit/quality and the latest explained finding. Label empty and unavailable states. (35 minutes)
4. Demonstrate a generated reading through layers 1 to 8 and save the complete trace; remove any fixture-only success indication. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_read_api.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Actual end-to-end trace, GET responses and a dashboard screenshot tied to the same run. Handoff to Emmanuel for data-meaning review and Tranos for the live demonstration. Acceptance: Dashboard data comes from the evidence API/database rather than plant memory or hard-coded examples; no public API mutation route exists.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 3 Tranos Exercise approved and labelled lab unapproved changes

Date: Saturday 31 October 2026. Jira: DPM-15. Owner: Tranos. Human reviewer: Thabani. Total allowance: four hours including review and reserve.

Primary layer: 1. Dependencies: DPM-12, DPM-13, DPM-14. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-15.

### Inputs and allowed changes
Working desk/controller path and a fresh baseline run. Work only within plant, fuxa and plant-specific tests. Agree shared interface changes before editing.

### Implementation checklist
1. Reset to a new run. Request 20 mg/s as Emmanuel and approve the matching request as Thabani using separate configured identities. (40 minutes)
2. Record the applied command before step 1; verify unchanged modeled residual at steps 1 to 4 and first adjustment at step 5. (35 minutes)
3. Add a disabled-by-default local lab mode for an explicitly logged unapproved change. Preserve Tranos identity and the actual effect without fabricating approval. (35 minutes)
4. Provide both action traces and their delayed sensor records to Emmanuel. Restore normal lab controls afterward. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_change_timing_lab.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: AC-01 and AC-02 scenario records, screenshots and observed timing values. Handoff to Emmanuel for approval/rule checks and Thabani for the evidence timeline. Acceptance: Approved and lab-unapproved actions remain distinguishable in the original evidence. The normal workflow still enforces authorization.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 3 Emmanuel Complete action chains and approval response rules

Date: Saturday 31 October 2026. Jira: DPM-16. Owner: Emmanuel. Human reviewer: Tranos. Total allowance: four hours including review and reserve.

Primary layer: 4. Dependencies: DPM-13, DPM-12, DPM-14. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-16.

### Inputs and allowed changes
Approved/lab-unapproved source records and agreed waiting-window semantics. Work only within monitor collection, validation, linking, health and rules modules and their tests. Agree shared interface changes before editing.

### Implementation checklist
1. Match explicit run/change/request/approval identifiers and approval scope. Flag cross-run or mismatched approvals rather than joining by time alone. (40 minutes)
2. Implement PENDING while a response is within its declared window, FAIL for supported discrepancies, and UNVERIFIED for missing/unreliable essentials. (35 minutes)
3. Implement the approved-change and explicit lab-unapproved rules; do not treat a collector receipt or missing record alone as proof of authorization. (35 minutes)
4. Compare saved findings with actual chain records and confirm sensor samples did not inherit a command change ID merely by following it. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_linking_rules.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Action-chain/rule tests and two actual saved findings with explanations and supporting IDs. Handoff to Thabani for finding presentation and Tranos for control-meaning review. Acceptance: Each explanation identifies what was checked and why the evidence supports its status; urgency and confidence remain separate.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 3 Thabani Show action trails and explained results

Date: Saturday 31 October 2026. Jira: DPM-17. Owner: Thabani. Human reviewer: Emmanuel. Total allowance: four hours including review and reserve.

Primary layer: 8. Dependencies: DPM-14, DPM-13, DPM-12. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-17.

### Inputs and allowed changes
Working GET API, linked chains and provisional rule outputs. Work only within monitor storage and API modules, dashboard, setup scripts and integration tests. Agree shared interface changes before editing.

### Implementation checklist
1. Add an action timeline for request, approval, command, acknowledgement, delivery and sensor observations. (40 minutes)
2. Show status, reason, supporting event links, urgency and evidence confidence as separate fields; distinguish baseline checks from action authorization. (35 minutes)
3. Add a run selector and a change/equipment filter without claiming every observation belongs to a change. (35 minutes)
4. Review both approved and lab-unapproved runs with Emmanuel and correct any misleading labels or stale values. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dashboard_queries.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: API query checks and actual screenshots of both action trails with raw-event links. Handoff to Emmanuel for semantic review and Tranos for scenario validation. Acceptance: A beginner can explain who acted, which approval applies, what the controller acknowledged, what was delivered and what sensors later observed.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 4 Tranos Add stopped pump and missing Sensor A cases

Date: Sunday 01 November 2026. Jira: DPM-18. Owner: Tranos. Human reviewer: Thabani. Total allowance: four hours including review and reserve.

Primary layer: 1. Dependencies: DPM-15, DPM-16, DPM-17. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-18.

### Inputs and allowed changes
Repeatable approved-change run and separate sensor adapters. Work only within plant, fuxa and plant-specific tests. Agree shared interface changes before editing.

### Implementation checklist
1. For a fresh run, establish approved 20 mg/s and settle 64 steps; verify modeled residual is within 0.000001 mg/L of 1.50 before applying a fault. (40 minutes)
2. Stop the pump while accepted feed remains 20 mg/s; show zero actual delivery and the subsequent delayed water response. (35 minutes)
3. For a separate fresh run, suppress A samples for ten steps while B, model ticks and plant feedback continue. (35 minutes)
4. Restore healthy settings after each case. Record source times, original retained A sample and new B samples without inventing A zeros. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_plant_faults.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: AC-03 and AC-04 source records, fault-action trail and actual FUXA/process screenshots. Handoff to Emmanuel for equipment/source-health rules and Thabani for alerts. Acceptance: Setting is not confused with delivery; a retained A value shows age/unavailability while B remains separately identifiable.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 4 Emmanuel Explain equipment faults and unreliable monitoring

Date: Sunday 01 November 2026. Jira: DPM-19. Owner: Emmanuel. Human reviewer: Tranos. Total allowance: four hours including review and reserve.

Primary layer: 5. Dependencies: DPM-16, DPM-15, DPM-17. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-19.

### Inputs and allowed changes
Stopped-pump and missing-A runs, action-chain rules and source health. Work only within monitor collection, validation, linking, health and rules modules and their tests. Agree shared interface changes before editing.

### Implementation checklist
1. Detect disagreement between an accepted healthy command and actual stopped-pump delivery using the matching run/equipment evidence. (40 minutes)
2. Use original sample times to age A; require no new A samples in the ten-step window and continued B/plant evidence. (35 minutes)
3. Generate an explained equipment FAIL and an essential-monitoring UNVERIFIED result; do not convert missing A into a fresh zero or a supported PASS. (35 minutes)
4. Complete automated checks for all five scenario families and publish precise remaining failures before the feature freeze. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fault_rules.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Fault/health tests and actual finding records linked to original evidence. Handoff to Thabani for alert display and Tranos for scenario confirmation. Acceptance: The team can distinguish evidence of an equipment discrepancy from inability to verify a conclusion because monitoring is unreliable.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 4 Thabani Add source health alerts and freeze features

Date: Sunday 01 November 2026. Jira: DPM-20. Owner: Thabani. Human reviewer: Emmanuel. Total allowance: four hours including review and reserve.

Primary layer: 8. Dependencies: DPM-17, DPM-16, DPM-15. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-20.

### Inputs and allowed changes
Five scenario families and their saved evidence/finding shapes. Work only within monitor storage and API modules, dashboard, setup scripts and integration tests. Agree shared interface changes before editing.

### Implementation checklist
1. Show A/B last-sample time, age, quality and unavailable state alongside plant status. (40 minutes)
2. Add on-screen alerts for new actionable findings and stale/missing essential sources. Keep alerts linked to reasons and evidence. (35 minutes)
3. Verify dashboard refresh does not give old records a new sample time or hide UNVERIFIED/PENDING states. (35 minutes)
4. Walk through all five families with both colleagues and freeze new features; record corrections and any explicitly deferred work. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dashboard_health.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Five-scenario walkthrough checklist, actual dashboard screenshots and freeze notes. Handoff to Emmanuel for source semantics and Tranos for live demonstration. Acceptance: Each displayed result matches a saved finding and its evidence; alerts require no external SMS/email service.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 5 Tranos Verify restart reset repeatability and observer protection

Date: Monday 02 November 2026. Jira: DPM-21. Owner: Tranos. Human reviewer: Thabani. Total allowance: four hours including review and reserve.

Primary layer: 1. Dependencies: DPM-18, DPM-19, DPM-20. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-21.

### Inputs and allowed changes
Integrated candidate, saved FUXA state and observer endpoint design. Work only within plant, fuxa and plant-specific tests. Agree shared interface changes before editing.

### Implementation checklist
1. Stop only MVP services using their own windows. Restart from saved state without reinstalling or replacing FUXA configuration. (40 minutes)
2. Reset to a new run ID while preserving earlier records; clear command queues, delayed samples and faults and restore seeds/baseline. (35 minutes)
3. Repeat the same actions and compare by simulation step; IDs and real UTC times may differ. (35 minutes)
4. Attempt single/multiple register writes on the observer endpoint and confirm rejection with unchanged process state. Keep the private command route separate. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_plant_restart_boundary.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Restart/reset notes, repeated-run comparison and actual refused-write evidence. Handoff to Thabani for integrated acceptance and Emmanuel for source continuity checks. Acceptance: Another member can start the plant; observer writes cannot change its state. Any limitation of same-host isolation is stated explicitly.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 5 Emmanuel Test errors duplicates retries and monitoring gaps

Date: Monday 02 November 2026. Jira: DPM-22. Owner: Emmanuel. Human reviewer: Tranos. Total allowance: four hours including review and reserve.

Primary layer: 3. Dependencies: DPM-19, DPM-18, DPM-20. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-22.

### Inputs and allowed changes
Integrated ingestion path, durable raw storage and source-health checks. Work only within monitor collection, validation, linking, health and rules modules and their tests. Agree shared interface changes before editing.

### Implementation checklist
1. Send one malformed JSON input and one wrong-unit/identity record; retain originals with validation errors and exclude them from correlation. (40 minutes)
2. Retry an identical event and confirm one logical normalized event/finding; flag a reused ID with conflicting content. (35 minutes)
3. Temporarily stop collection, verify local outbox retention, restore collection and check original producer IDs/timestamps survive replay. (35 minutes)
4. Test an evidence gap at a response deadline and confirm the rule produces UNVERIFIED rather than an unjustified PASS. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ingestion_integrity.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Actual integrity-check output, retry/replay evidence and precise remaining defects. Handoff to Thabani for persistence/API acceptance and Tranos for publisher review. Acceptance: Raw attempts and duplicate receipts remain auditable without duplicating logical evidence; errors cannot silently become trusted inputs.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 5 Thabani Check persistence read only boundaries and the candidate

Date: Monday 02 November 2026. Jira: DPM-23. Owner: Thabani. Human reviewer: Emmanuel. Total allowance: four hours including review and reserve.

Primary layer: 7. Dependencies: DPM-20, DPM-19, DPM-18. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-23.

### Inputs and allowed changes
Feature-frozen integrated system and both colleagues integrity checks. Work only within monitor storage and API modules, dashboard, setup scripts and integration tests. Agree shared interface changes before editing.

### Implementation checklist
1. Reopen the database and verify raw, normalized and finding references still resolve; run integrity and foreign-key checks. (40 minutes)
2. Attempt POST/PUT/PATCH/DELETE on the evidence API and verify refusal. Inspect routes, dependencies and configuration for command paths/credentials. (35 minutes)
3. Run the complete scenario suite against one reviewed commit and reconcile displayed findings with stored records. (35 minutes)
4. Correct blocking defects within reserve, prepare the candidate notes and leave unresolved checks explicitly Not run or Fail. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_system_boundary.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Candidate test output, database checks, API refusal evidence and defect list. Handoff to Emmanuel for human review and Tranos for independent startup. Acceptance: The candidate is reproducible and every claimed pass has observed proof; local prototype boundaries are not described as production isolation.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 6 Tranos Perform independent startup and capture plant evidence

Date: Tuesday 03 November 2026. Jira: DPM-24. Owner: Tranos. Human reviewer: Thabani. Total allowance: four hours including review and reserve.

Primary layer: 1. Dependencies: DPM-21, DPM-22, DPM-23. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-24.

### Inputs and allowed changes
Reviewed candidate, setup instructions and saved FUXA export. Work only within plant, fuxa and plant-specific tests. Agree shared interface changes before editing.

### Implementation checklist
1. Have another member follow the written setup/start instructions without verbal repair; record the exact commit and environment. (40 minutes)
2. Capture a working FUXA screen, correctly scaled readback and a restart demonstration from the saved project. (35 minutes)
3. Rerun core plant actions in fresh runs and collect real source records for the demonstration package. (35 minutes)
4. Report limitations and hand the reviewed FUXA export, screenshots and source references to Thabani. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_independent_startup.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Independent-startup finding, actual screenshots, FUXA export and source-record manifest. Handoff to Thabani for final demonstration package and Emmanuel for evidence audit. Acceptance: Evidence is captured from the candidate and can be explained by someone other than its author; no screenshot is generated to simulate success.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 6 Emmanuel Audit findings and prepare evidence explanations

Date: Tuesday 03 November 2026. Jira: DPM-25. Owner: Emmanuel. Human reviewer: Tranos. Total allowance: four hours including review and reserve.

Primary layer: 5. Dependencies: DPM-22, DPM-21, DPM-23. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-25.

### Inputs and allowed changes
Candidate run manifests, raw records, saved findings and screenshots. Work only within monitor collection, validation, linking, health and rules modules and their tests. Agree shared interface changes before editing.

### Implementation checklist
1. For each core scenario, follow displayed supporting IDs back to original source records and note any missing chain segment. (40 minutes)
2. Check units, identities, sample/emission/receipt times, source health, waiting state and final explanation. (35 minutes)
3. Review the acceptance record with Tranos and mark only observed checks with reviewer confirmation; keep gaps visible. (35 minutes)
4. Prepare a short spoken explanation of approved, unapproved, equipment and monitoring outcomes for Wednesday. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_evidence_audit.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Signed reviewer findings where actually received, evidence audit and short scenario notes. Handoff to Thabani for release/readiness decision and Tranos for cross-review. Acceptance: Every claimed outcome has an accessible evidence chain, and monitoring uncertainty is explained without asserting water safety.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Day 6 Thabani Package the MVP and rehearse the professor review

Date: Tuesday 03 November 2026. Jira: DPM-26. Owner: Thabani. Human reviewer: Emmanuel. Total allowance: four hours including review and reserve.

Primary layer: 8. Dependencies: DPM-23, DPM-22, DPM-21. Card link: https://mail-team-bpbflevn.atlassian.net/browse/DPM-26.

### Inputs and allowed changes
Reviewed candidate, independent startup results and Emmanuel evidence audit. Work only within monitor storage and API modules, dashboard, setup scripts and integration tests. Agree shared interface changes before editing.

### Implementation checklist
1. Collect the exact commit, dependency locks, FUXA export, configuration instructions and a manifest of actual evidence. (40 minutes)
2. Update Jira with evidence and human review findings; close only cards whose acceptance is actually met. (35 minutes)
3. Rehearse the normal path and the four change/fault families, including a clear explanation of the passive boundary and prototype limitations. (35 minutes)
4. Prepare the final readiness note for 3 November and professor review on 4 November; record unresolved risks instead of hiding them. (20 minutes)

### Use the AI tools for this task
ChatGPT: Use your master prompt to explain the four subtasks, inputs and expected observations before coding.

Codex: Implement only this card on its DPM branch. Create and run the focused check below; report observed results and missing interfaces.

Claude: Review this card, selected diff and actual output with your master prompt. Challenge the acceptance below without inferring unseen evidence.

### Verify and hand off
Create the following focused check module as part of this task, then run it from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/test_end_to_end_evidence.py -q
~~~

Implement this planned check with the task. Missing or failing checks remain Not run or Fail. Manual process and evidence checks are also required.

Required proof: Readiness report, final evidence manifest, demonstration notes and reviewed release reference if accepted. Handoff to All three members for final acceptance and the professor demonstration. Acceptance: The team can restart, explain and demonstrate the candidate and distinguish completed work, proposed behaviour and outstanding defects.

Reserve the remaining 110 minutes: 15 for coordination, 35 for human/AI review, 30 for integration/evidence/Jira and 30 for troubleshooting. Save results under the actual run/check ID, attach PR/commit references to the card and keep reviewer acceptance pending until received. After 15 blocked minutes, report the missing input, exact error and next action.

Runtime result: Not run. Human acceptance: Pending.

## Troubleshooting and handoffs

Use one focused diagnosis before changing architecture. Keep the exact error, task ID, installed versions and last known working commit.

| Symptom | First checks | Handoff |
| --- | --- | --- |
| FUXA blank or disconnected | Confirm controller port/device/address offset, driver, one-second polling and one scaling conversion. Read registers independently. | Tranos |
| Value looks correct but no evidence | Check publisher outbox, collector receipt and raw database row; a displayed PLC setting is not a sensor sample. | Tranos and Emmanuel |
| Collector rejects data | Retrieve retained original bytes and validation errors. Check schema version, IDs, UTC and units. Do not add fabricated defaults. | Emmanuel |
| Duplicate findings | Compare original event identity, receipt identity and normalized uniqueness. Retain attempts without duplicating logical evidence. | Emmanuel and Thabani |
| Old A reading appears fresh | Compare original sample time, emission time and receipt time; inspect age/quality and missing-source logic. | Emmanuel and Thabani |
| SQLite locked | Confirm one writer, short transactions and separate read-only API connection. Report contention rather than deleting the database. | Thabani |
| Import or package error | Confirm the project Python 3.12 virtual environment and lock; run pip check. Record exact failure before changing pins. | Assigned owner and Thabani |
| Port occupied | Report the port and project service state; choose a reviewed alternate configuration only after updating all consumers. Never kill unrelated services. | Thabani |
| Tools suggest different contracts | Stop shared-interface edits, compare both suggestions with contract v0.1, record the team decision and rerun affected checks. | All affected members |

Handoff message: actual Jira key; branch/commit; delivered output; exact checks and observed results; evidence path; reviewer; known failure/dependency; next action. A screenshot alone is insufficient when the acceptance also requires source records and a traceable rule explanation.

If Friday integration is late, join the three owners around one actual failing handoff and repair it before adding variants. After Sunday freeze, accept only corrections needed for the declared MVP. Defer polish explicitly; do not drop evidence integrity, actor separation or passive-boundary checks.

## Tuesday readiness and Wednesday demonstration

Tuesday readiness requires a reviewed candidate, a reproducible startup procedure and actual evidence. Do not tag an accepted release until the team records its decision.

1. State the purpose: DoseProof explains whether copied operational evidence supports a conclusion about a simulated action.
2. Show FUXA and the model with distinct requested/accepted setting, actual delivery and A/B observations.
3. Follow one genuine record through collector, raw SQLite storage, validation, linking, rule, GET API and dashboard.
4. Show an approved request and the separate acknowledgement, delivery and delayed response.
5. Show the labelled lab-unapproved case and explain its evidence, not a fabricated approval.
6. Show stopped-pump delivery and missing-A monitoring uncertainty, with B still producing evidence.
7. Show a refused observer write, a refused evidence API mutation and the retained raw record after restart.
8. State what passed, what failed or was not run, and the same-host/shared-model limitations.

The final package contains the exact commit, dependency locks, FUXA export, setup instructions, actual run/check manifest, screenshots, results and human reviewer findings. Generated evidence stays private and local unless the team intentionally shares it with the professor.

The 4 November meeting is a progress review. If something is unfinished, show actual progress, the specific blocker and the next correction. Never present this runbook or an AI-generated screen as execution evidence.

## References and publication status

Architecture authority: DoseProof System Architecture PDF supplied by Thabani. Earlier repository baseline and contracts: https://github.com/thamas97/doseproof. Existing detailed DOS-1 to DOS-4 proposals remain separate pending inputs and are not imported as accepted results.

Official references:

- ChatGPT project context: https://learn.chatgpt.com/docs/projects
- Codex development workflow: https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex
- Claude review practices: https://code.claude.com/docs/en/best-practices
- Jira dated Kanban timeline: https://support.atlassian.com/jira-software-cloud/docs/enable-child-issue-planning-for-kanban-teams-on-the-roadmap/
- FUXA devices and tags: https://frangoteam.github.io/FUXA/HowTo-Devices-and-Tags/

Member-specific daily cards: https://mail-team-bpbflevn.atlassian.net/jira/software/projects/DPM/boards/2. Timeline: https://mail-team-bpbflevn.atlassian.net/jira/software/projects/DPM/boards/2/timeline. Private repository: https://github.com/thamas97/doseproof-mvp.

This publication prepares the workspaces and instructions. Dependency import/schema checks are preparation evidence only. Runtime acceptance remains Not run until actual execution. Tranos invitation uses confirmed account tranosmau; Emmanuel invitation is intentionally deferred. No original DOS issue or pull request is accepted by this document.
