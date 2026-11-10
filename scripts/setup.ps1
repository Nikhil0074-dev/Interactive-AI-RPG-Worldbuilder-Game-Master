# Windows PowerShell: install backend + frontend dependencies.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m venv backend\.venv
& backend\.venv\Scripts\pip.exe install -r backend\requirements.txt
Push-Location frontend; npm ci; Pop-Location
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Write-Host "Setup complete. Run scripts\dev.ps1"
