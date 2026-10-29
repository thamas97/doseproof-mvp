param([ValidateSet('plant','collector','api')][string]$Service)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$entry = @{ plant='plant\app.py'; collector='monitor\collector_app.py'; api='monitor\api_app.py' }[$Service]
if (-not $entry) { throw 'Choose -Service plant, collector or api. Start FUXA separately.' }
if (-not (Test-Path $entry)) { throw "Not implemented yet: $entry. Follow the assigned DPM task. This starter is not a runnable MVP." }
if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Run the project Python setup first.' }
& '.\.venv\Scripts\python.exe' $entry
