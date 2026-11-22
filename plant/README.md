# Implementation responsibility

Tranos owns the operator desk, private command/controller path, plant model, separate sensors and source publishers. `python plant/app.py` now runs the plant, read-only observer and named desk. The event publisher uses a durable JSONL cursor and retries against the separate collector. See [the integrated path guide](../docs/integrated-evidence-path.md); configure local passwords privately before using the desk. The evidence dashboard has no treatment controls.

## Capture the change scenarios

1. As Tranos, select **Reset to new paused run**. The desk shows a new run ID at step 0. Earlier evidence remains on disk. The observer marks both sensors unavailable until the first tick of the new run.
2. For AC-01, Emmanuel requests 20 mg/s, Thabani approves, and Tranos executes. Confirm the acknowledgement at step 0. Tranos resumes the simulation and lets at least eight steps finish.
3. For AC-02, start the loopback plant with `$env:MVP_LAB_MODE = '1'`. Reset to a fresh paused run. Tranos enters 20 mg/s and a reason under **Lab only · Unapproved change**, then resumes. The run records a lab action, a labelled command with null request and approval IDs, and an acknowledgement. Restore normal mode by removing the environment variable and restarting the plant.
4. Export each run using `python scripts/export-check.py --run-id <run-id> --check-id AC-01` (use `AC-02` for the lab run). The export preserves original bytes and drafts the action trail and first eight observation steps. Add actual screenshots and human findings separately.

For AC-03, run an approved 20 mg/s change through 64 simulation steps. With loopback lab mode enabled, select **Lab: stop pump**. The accepted setting stays at 20 mg/s and delivery falls to zero. For AC-04, reset, resume, allow both sensors to report, then select **Lab: suppress Sensor A**. The observer keeps A's last real value (never zero) and its age counts up; A quality is good for ages 1–2, uncertain (stale) from age 3 and unavailable from age 10, matching the evidence API freshness policy. After ten steps the original A sample remains identifiable and B and the plant continue. Reset clears either fault. Use the evidence dashboard's **Change and fault evidence** panel to inspect the corresponding findings and original receipts.

The expected modeled residual is 1.00 mg/L through step 4, then 1.10, 1.18, 1.244 and 1.2952 mg/L at steps 5–8 in both cases. The action records distinguish approval from the labelled lab change.

## Restart, reset and the observer boundary (DPM-21)

**Restart.** Stop only the MVP windows with Ctrl+C (plant, collector, API, FUXA); never end unrelated processes to free a port. Start them again with the same commands. FUXA restarts from its saved project in `fuxa/state`, so do not reinstall it or re-import the project. A restarted plant starts a new run ID at step 0; earlier run folders are kept unchanged and their unsent copies are replayed to the collector.

**Reset.** **Reset to new paused run** gives a new run ID at step 0 and keeps earlier records byte for byte. It restores the teaching baseline (15 mg/s, residual 1.00, pump running), refills the four-step delivery delay, restarts both sensor seeds, clears faults, acknowledgements and open desk requests.

**Repeatability.** The same actions in two fresh runs produce the same values at every simulation step. Run IDs, event IDs, command IDs and real UTC times differ by design. `tests/test_plant_restart_boundary.py` compares two runs record by record.

**Observer boundary.** With the plant running, capture actual refused-write evidence:

```powershell
.\.venv\Scripts\python.exe scripts\observer-write-probe.py
```

It attempts single (FC6), multiple (FC16) and read/write (FC23) writes on the observer only and reports each as REFUSED, with the feed registers unchanged. The private controller on 1503 is a separate endpoint that accepts only desk-registered commands.

**Limitation.** The plant, observer, controller and DoseProof run on one laptop under one Windows account. Write refusal stops network writes through Modbus, but it is not isolation: a malicious process under the same account could read the desk password file, call the controller's port or alter local files. A real deployment would separate hosts, accounts and networks.

## Independent startup and the demonstration package (DPM-24)

Another member starts the plant on their own laptop by following [STARTUP-CHECKLIST.md](STARTUP-CHECKLIST.md) without verbal help, records the commit, environment and actual result of each step, and writes the finding. A run by the author on a clean copy is a rehearsal, not independent startup.

For the package, list the original source-record files of the chosen runs with their SHA-256 fingerprints:

```powershell
.\.venv\Scripts\python.exe -m plant.evidence_manifest --run <run_id> --out C:\dp\dpm24-proof\source-record-manifest.json
```

The manifest only reads files. Re-running it later and comparing fingerprints shows whether an evidence file changed. `fuxa/doseproof-observer-project.json` is the reviewed FUXA export: Observer on 127.0.0.1:1502, device 1, 1000 ms polling and 13 holding-register tags named as in the contract.
