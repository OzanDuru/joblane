$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (Test-Path './config.local.ps1') { . './config.local.ps1' }
& './.venv/Scripts/python.exe' 'run.py' 'serve' '--open'
exit $LASTEXITCODE
