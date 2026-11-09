# Plant, operator desk and FUXA view (Layer 1)

Owner: Tranos. Educational simulation only, not drinking-water operating guidance.

This folder runs the operator side of the simulation in one process (`plant/app.py`):

| Part | Address | Purpose |
|---|---|---|
| Teaching model + Sensor A/B | – | one tick per second, values from `contracts/baseline.json` |
| Read-only observer | 127.0.0.1:1502, device 1 | 13 holding registers for FUXA / DoseProof; all network writes refused |
| Private controller | 127.0.0.1:1503, device 1 | operator desk only; **not** for DoseProof configuration |
| Operator desk | http://127.0.0.1:5000 | named sign-in, request / approve / execute, lab controls |

Source records: `evidence/<run_id>/plant-source-records.jsonl` (ignored by Git), also POSTed to the collector on 5001 when it is running.

## 1. One-time setup (Windows, PowerShell, repository root)

Needs Python 3.12 (`py --list` must show 3.12), Node.js and Git.

```powershell
git fetch origin
git checkout DPM-18-stopped-pump-missing-a      # newest branch; contains DPM-9, 12 and 15
powershell -NoProfile -File .\scripts\setup-python.ps1
git restore requirements.lock.txt               # the setup script rewrites it; keep the team copy
npm.cmd --prefix fuxa ci
.\.venv\Scripts\python.exe -m pytest tests -q   # expect: 31 passed
```

### Desk passwords (each person sets their own; never share or commit)

```powershell
.\.venv\Scripts\python.exe -m plant.desk_users set thabani
```

Users and roles: `emmanuel` requester, `thabani` approver, `tranos` lab operator. Minimum 10 characters. Only a salted hash is stored, in `.env.desk-users.json` (ignored by Git). To test alone, you may set temporary passwords for the other two on your own machine; do not send them to anyone.

### FUXA (first time only)

1. Create `fuxa/state/_appdata/settings.js` **before** the first start (keeps FUXA on loopback only):

   ```js
   // DoseProof MVP: project-local FUXA settings. Loopback only (this PC), port 1881.
   const defaults = require('../../node_modules/@frangoteam/fuxa/settings.default.js');
   module.exports = Object.assign({}, defaults, { uiHost: '127.0.0.1', uiPort: 1881 });
   ```

2. `npm.cmd --prefix fuxa start` and check the log says `WebServer is running http://127.0.0.1:1881`.
3. Open `http://127.0.0.1:1881/plugins` and install **modbus-serial**.
4. Open `http://127.0.0.1:1881/editor`, menu, **Open Project**, choose `fuxa/doseproof-observer-project.json` (connection 127.0.0.1:**1502**, device 1, 1000 ms, 13 tags). Click Save.

## 2. Start (three terminals, repository root)

| Terminal | Command |
|---|---|
| FUXA | `npm.cmd --prefix fuxa start` |
| Plant | `powershell -NoProfile -File .\scripts\start-mvp.ps1 -Service plant` |
| Commands | tests, readback, exports |

Expected plant output: `Observer listening on 127.0.0.1:1502`, `Private controller listening on 127.0.0.1:1503`, `Operator desk on http://127.0.0.1:5000`, then one `plant step ...` line per second.

Independent register readback: `.\.venv\Scripts\python.exe scripts\observer-readback.py`

Stop with **Ctrl+C** in each project window only. Never kill unrelated processes to free a port.

## 3. Scenarios

### AC-00 Baseline
Start the plant and watch 10 steps: flow 10.00, delivery 15.00, residual 1.0000, Sensor A and B each within 0.01 of 1.00.

### AC-01 Approved change
1. Desk as **Tranos**: *Reset to new run (paused at step 0)*. Note the run ID.
2. As **Emmanuel**: request 20 mg/s. As **Thabani**: Approve. As **Emmanuel**: Execute. Status is *acknowledged* while still at step 0.
3. As **Tranos**: Resume. Expected residual: steps 1–4 1.0000, then 1.1000, 1.1800, 1.2440, 1.2952. Pause.
4. Export: `.\.venv\Scripts\python.exe scripts\export-check.py <run_id> AC-01`

### AC-02 Labelled lab-unapproved change (lab mode is OFF by default)
1. Stop the plant, then in the plant terminal: `$env:MVP_LAB_MODE = "1"` and start the plant again (log shows `LAB MODE ENABLED`).
2. As **Tranos**: Reset, then use the red **LAB MODE** box: 20 mg/s with a reason. Resume, wait, Pause.
3. Records show `lab_action` (actor tranos, approved false) + `command` with `approval_id: null` + `acknowledgement`. No approval is created.
4. Export: `.\.venv\Scripts\python.exe scripts\export-check.py <run_id> AC-02`
5. **Restore normal controls:** Ctrl+C, `Remove-Item Env:MVP_LAB_MODE`, start again. The desk shows *Lab-unapproved path is disabled*.

### AC-03 Stopped pump (lab fault simulation, operator only)
1. Run AC-01 steps 1–3 (approved 20 mg/s), then let it run at least **64 steps**; residual settles at 1.5000.
2. As **Tranos**, in the orange **LAB FAULT SIMULATION** box: *Stop pump*. Accepted feed stays 20, actual delivery 0, pump 0.
3. Residual stays ~1.50 for 4 more steps (water already dosed), then follows the model down (1.20, 0.96, ...). Pause.
4. Export `AC-03`, then *Restart pump* to restore health (or Reset).

### AC-04 Missing Sensor A
1. As **Tranos**: Reset, Resume, then *Suppress Sensor A*. Wait 10 steps.
2. No new `sensor-a` records; B and plant feedback continue. FUXA keeps A's last real value; A age counts up; A quality 0 good, then 1 uncertain from age 3, then 3 unavailable from age 10. No zero is invented.
3. Pause, export `AC-04`, then *Restore Sensor A*.

Fault actions are recorded as `lab_action` (actor tranos, `simulated_fault: true`, `approved: false`); simulate and restore share one `change_id`. Reset clears all faults.

Exports go to `evidence/<run_id>/checks/<check_id>/` (`source-records.jsonl` + `result-draft.md`). Add your own `screen.png`; Result and Reviewer stay *Not run* / *Pending* until a person completes them.

## Troubleshooting

| Symptom | Check |
|---|---|
| FUXA dot red, log `ECONNREFUSED 127.0.0.1:502` | Port must be **1502**, not the default 502 |
| ModbusTCP missing in FUXA | Install the modbus-serial plugin (step FUXA 3) |
| FUXA values off by one register | UI address = protocol address + 1 (400001 = HR0) |
| Values 100× too big or small | Divisor 100 only on the first six tags, applied once |
| Desk has no *Lab controls* | Sign in as **tranos**; restart the plant after pulling new code |
| `Sign-in failed` | Set that user's password with `plant.desk_users set <name>` |
| `py -3.12` not found | Install Python 3.12 alongside newer versions |

## Known limitations

- Collector (5001) may not be running yet; copies are logged as not sent and the local JSONL is kept.
- Desk request state is in memory; Reset or restart clears the desk list (records stay on disk).
- No login rate limiting. Same-Windows-account processes are not isolated.
- Sensor thresholds (stale at 3 steps, unavailable at 10) follow the runbook MVP values and need recorded team review.
- While Sensor A is suppressed its random generator does not advance, so A values after restore differ from an unfaulted run.
