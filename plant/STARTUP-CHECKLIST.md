# Independent plant startup checklist (DPM-24)

Educational simulation only. A team member **other than Tranos** follows this page on their own Windows laptop. Tranos may watch but must not give verbal fixes. If a step fails, write down the exact error, stop that step and continue where possible: a gap in these instructions is a finding, not a failure of the person.

Record the actual outcome of every step. Do not fill in a result you did not see, and do not stage or edit screenshots.

## Record

| Item | Value |
| --- | --- |
| Person starting the plant | |
| Date and local time | |
| Laptop / Windows version | |
| `git rev-parse HEAD` | |
| `py -3.12 --version` | |
| `node --version` and `npm.cmd --version` | |
| Observer (Tranos or other) | |

## 1. Fresh checkout and setup

Use a new empty folder, for example `C:\dp-check`.

```powershell
git clone https://github.com/thamas97/doseproof-mvp C:\dp-check\doseproof-mvp
cd C:\dp-check\doseproof-mvp
git checkout <candidate branch or commit given by Thabani>
git rev-parse HEAD
powershell -NoProfile -File .\scripts\setup-python.ps1
git restore requirements.lock.txt
npm.cmd --prefix fuxa ci
.\.venv\Scripts\python.exe -m pytest tests -q
```

| Check | Expected | Actual |
| --- | --- | --- |
| Setup script finishes | Python 3.12 and the pinned versions printed | |
| Tests | All pass (number printed) | |

## 2. Your own desk password

```powershell
.\.venv\Scripts\python.exe -m plant.desk_users set <your name>
```

Only a salted hash is saved, in `.env.desk-users.json`, which Git ignores. Never share or send the password.

## 3. FUXA first start (loopback only)

Create `fuxa\state\_appdata\settings.js` **before** the first FUXA start:

```js
// DoseProof MVP: project-local FUXA settings. Loopback only (this PC), port 1881.
const defaults = require('../../node_modules/@frangoteam/fuxa/settings.default.js');
module.exports = Object.assign({}, defaults, { uiHost: '127.0.0.1', uiPort: 1881 });
```

Start it with `npm.cmd --prefix fuxa start`, open `http://127.0.0.1:1881/plugins`, install **modbus-serial**, then in the editor menu choose **Open Project** and select `fuxa\doseproof-observer-project.json`. Save.

| Check | Expected | Actual |
| --- | --- | --- |
| FUXA log | `WebServer is running http://127.0.0.1:1881` (not 0.0.0.0) | |

## 4. Start the MVP (four terminals, repository root, in this order)

| Terminal | Command |
| --- | --- |
| Collector | `powershell -NoProfile -File .\scripts\start-mvp.ps1 -Service collector` |
| Evidence API | `powershell -NoProfile -File .\scripts\start-mvp.ps1 -Service api` |
| Plant | `powershell -NoProfile -File .\scripts\start-mvp.ps1 -Service plant` |
| FUXA | `npm.cmd --prefix fuxa start` |

| Check | Expected | Actual |
| --- | --- | --- |
| Plant log | Observer on 127.0.0.1:1502, controller on 127.0.0.1:1503, desk on 127.0.0.1:5000, one step per second, no "Collector copy not sent" lines | |
| Dashboard `http://127.0.0.1:5002` | plant-model, sensor-a and sensor-b FRESH | |
| FUXA Observer connection | Green; flow 10, feeds 15, pump 1, A and B about 1.00, tick rising | |

## 5. Independent readback and write refusal

```powershell
.\.venv\Scripts\python.exe scripts\observer-readback.py
.\.venv\Scripts\python.exe scripts\observer-write-probe.py
```

| Check | Expected | Actual |
| --- | --- | --- |
| Readback | Raw 1000 / 1500 / 1500 / 1500 scaled to 10.00 / 15.00 / 15.00 / 15.00; matches FUXA | |
| Write probe | Four REFUSED lines, `RESULT: PASS` | |

## 6. Restart from the saved project

Press Ctrl+C in the plant and FUXA terminals only, then start both again with the same commands.

| Check | Expected | Actual |
| --- | --- | --- |
| FUXA after restart | Same Observer connection and 13 tags without re-import; dot green | |
| Dashboard | New run listed; earlier run still selectable | |

## 7. Finding

Write one of the following, with the reason:

- **Passed:** started and verified from these instructions without verbal help.
- **Passed with gaps:** started, but needed the following missing instructions: …
- **Failed:** could not start because: … (exact error)

Finding:

Signed (person who started the plant):
