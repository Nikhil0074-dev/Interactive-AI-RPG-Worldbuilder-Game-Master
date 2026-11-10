# Windows PowerShell: run backend (8000) and frontend (3000) together. Press Ctrl+C to stop both.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$back = Start-Process -PassThru -NoNewWindow -WorkingDirectory backend -FilePath ".venv\Scripts\python.exe" `
  -ArgumentList "-m","uvicorn","app.main:create_app","--factory","--port","8000","--env-file","..\.env"
try { Push-Location frontend; npm run dev } finally { Pop-Location; if ($back -and -not $back.HasExited) { Stop-Process -Id $back.Id } }
