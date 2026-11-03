# Implementation responsibility

Tranos owns the operator desk, private command/controller path, plant model, separate sensors and source publishers. `python plant/app.py` now runs the plant, read-only observer and named desk. The event publisher uses a durable JSONL cursor and retries against the separate collector. See [the integrated path guide](../docs/integrated-evidence-path.md); configure local passwords privately before using the desk. The evidence dashboard has no treatment controls.

## Capture the change scenarios

1. As Tranos, select **Reset to new paused run**. The desk shows a new run ID at step 0. Earlier evidence remains on disk. The observer marks both sensors unavailable until the first tick of the new run.
2. For AC-01, Emmanuel requests 20 mg/s, Thabani approves, and Tranos executes. Confirm the acknowledgement at step 0. Tranos resumes the simulation and lets at least eight steps finish.
3. For AC-02, start the loopback plant with `$env:MVP_LAB_MODE = '1'`. Reset to a fresh paused run. Tranos enters 20 mg/s and a reason under **Lab only · Unapproved change**, then resumes. The run records a lab action, a labelled command with null request and approval IDs, and an acknowledgement. Restore normal mode by removing the environment variable and restarting the plant.
4. Export each run using `python scripts/export-check.py --run-id <run-id> --check-id AC-01` (use `AC-02` for the lab run). The export preserves original bytes and drafts the action trail and first eight observation steps. Add actual screenshots and human findings separately.

The expected modeled residual is 1.00 mg/L through step 4, then 1.10, 1.18, 1.244 and 1.2952 mg/L at steps 5–8 in both cases. The action records distinguish approval from the labelled lab change.
