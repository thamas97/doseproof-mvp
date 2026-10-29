$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 environment creation failed.' }
}
if (Test-Path 'requirements.lock.txt') {
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.lock.txt
} else {
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.in
}
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; save the exact error.' }
& '.\.venv\Scripts\python.exe' -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency compatibility check failed.' }
& '.\.venv\Scripts\python.exe' -m pip freeze | Set-Content -Encoding utf8 requirements.lock.txt
& '.\.venv\Scripts\python.exe' -c "import sys, importlib.metadata as m, sqlite3; from pymodbus.server import ModbusTcpServer; from flask import Flask; print(sys.version); print({p:m.version(p) for p in ['Flask','pymodbus','jsonschema','pytest']}); print('SQLite',sqlite3.sqlite_version)"
if ($LASTEXITCODE -ne 0) { throw 'Import smoke check failed.' }
