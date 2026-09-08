Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "    Deep Research AI - Autonomous Agent Server" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

Set-Location -Path "$PSScriptRoot\backend"
$venvPython = "$PSScriptRoot\backend\.venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
} else {
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
}

