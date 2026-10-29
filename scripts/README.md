# Setup and planned runtime commands

From the repository root in PowerShell run:

~~~powershell
py -3.12 --version
node --version
npm.cmd --version
git --version
powershell -NoProfile -File .\scripts\setup-python.ps1
.\.venv\Scripts\python.exe -m pytest tests/test_contract_files.py
~~~

After runtime entrypoints are implemented, use separate project windows:

~~~powershell
powershell -NoProfile -File .\scripts\start-mvp.ps1 -Service collector
powershell -NoProfile -File .\scripts\start-mvp.ps1 -Service plant
powershell -NoProfile -File .\scripts\start-mvp.ps1 -Service api
npm.cmd --prefix fuxa start
~~~

These runtime commands are the agreed interface to be implemented and checked. The launcher refuses to pretend that missing services exist. Collector: localhost 5001; desk: 5000; API/dashboard: 5002; FUXA: 1881; observer: 1502. Report occupied ports; never kill unrelated processes. The private command path is not an observer endpoint and must not be exposed by DoseProof. Save/export FUXA before Ctrl+C in its own window.
