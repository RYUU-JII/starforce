param(
  [int]$Port = 8000,
  [string]$BindHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

$venvActivate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
  . $venvActivate
} else {
  Write-Host "Warning: .venv not found. Using current Python environment." -ForegroundColor Yellow
}

python -m uvicorn app.main:app --reload --host $BindHost --port $Port
