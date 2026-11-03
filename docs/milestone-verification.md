# Actual verification — connected baseline evidence path

Executed 31 October 2026. Human acceptance remains pending.

## Automated checks

Python 3.12.10, SQLite 3.49.1 and the repository's existing dependency lock.
`python -m pytest tests -q` completed with **84 passed in 10.63 seconds**.
This includes the inherited 22 plant/desk/starter cases, 26 storage cases and
36 new intake/API/rule/publisher cases. No cases were skipped in this final run.
Local networking required execution permission; the earlier restricted run's
socket-denial failures are not reported as passes.

The checks cover actual generated model observations, preserved original bytes,
UTC/unit/identity/quality failures, same-run/step separation, missing sources,
bad quality, sensor disagreement, later identity conflicts, rejected API writes,
query bounds, SQLite restart and rollback, lost-response deduplication, retained
invalid events and publisher restart replay.

The retry test exposed an unclosed HTTP error response that could stall shutdown.
The sender now closes error responses before retrying; all three loopback delivery
checks and the complete suite passed after that correction.

## Genuine local process capture

Command (using the verified Python environment):

```powershell
python scripts\verify-evidence-path.py --output evidence\milestone-2026-10-31 --api-port 25002 --serve-seconds 600
```

- Implementation commit: `bea931e5e746e0bfbd36ff8c1131b8d46b504f75`.
- Actual run: `run-20261031T125051Z-594461`.
- Capture time: `2026-10-31T12:50:56.354762+00:00`.
- Actual plant process generated 15 recorded source events at the capture boundary.
- The collector was stopped for 2.5 seconds, restarted against the same database,
  and the plant publisher delivered its retained backlog.
- Retrieved wire bytes matched the corresponding source outbox record exactly.
- Example original sample time: `2026-10-31T12:50:55.489Z`; distinct collector
  receipt time: `2026-10-31T12:50:56.051975Z`.
- The latest saved same-step sensor/model check at step 5 was PASS, with three
  supporting receipt IDs. Its scope explicitly excludes approval and water safety.
- A deliberately malformed negative probe returned 422 and its exact bytes were
  retrieved from storage. This probe is labelled separately from genuine source events.
- An actual POST to `/api/events` returned 405.

The private local capture contains `source-records.jsonl`, `trace.json`,
`result.md`, `plant.log` and `doseproof.db` under the ignored evidence folder.
The original producer run outbox/delivery log is also retained locally. No generated
capture files, passwords or databases are committed. Re-run the helper in a new
folder to produce independent evidence; its ports/IDs/timestamps will differ.

## Verification limits

The dashboard HTML/assets are served successfully and its GET APIs were exercised.
JavaScript syntax is checked separately. The available browser/desktop automation
helper could not initialize (kernel asset-path error), including after a reset.
**No browser visual inspection or process screenshot is claimed.** The local
preview was requested in Codex for manual inspection; its serving window is temporary.

No approval history, team agreement, reviewer sign-off or fault result is invented.
Approval-chain assurance, full equipment/monitoring scenarios and response-deadline
handling remain future work. This report proves the connected baseline data path,
not acceptance of the complete eight-layer MVP or the inherited open PRs.
