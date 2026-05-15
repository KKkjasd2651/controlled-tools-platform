# Minimal uvicorn launcher. Invoked by run.bat via PowerShell.
# IMPORTANT: double-click-bat -> cmd -> powershell chain often LACKS the SMB
# session that your desktop PowerShell has. If pre-warm or python self-check
# times out, FALL BACK to launching uvicorn from your own PowerShell window.

$ErrorActionPreference = "Continue"

Set-Location -LiteralPath (Split-Path -Parent $MyInvocation.MyCommand.Path)

$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  Write-Host "[X] venv python not found at $python" -ForegroundColor Red
  Read-Host "Press Enter to close"
  exit 1
}

# Pre-warm SMB session with a 5-second hard timeout so we never hang here.
function Prewarm-SMB($root) {
  Write-Host "[pre-warm] touching SMB share: $root (timeout 5s)"
  $job = Start-Job -ScriptBlock {
    param($p)
    Get-ChildItem -LiteralPath $p -Force -ErrorAction SilentlyContinue | Select-Object -First 1 | Out-Null
    return $true
  } -ArgumentList $root
  if (Wait-Job $job -Timeout 5) {
    Receive-Job $job | Out-Null
    Write-Host "[pre-warm] OK"
  } else {
    Stop-Job $job -ErrorAction SilentlyContinue
    Write-Host "[pre-warm] TIMEOUT (5s). This PowerShell process has no SMB" -ForegroundColor Yellow
    Write-Host "             session for $root." -ForegroundColor Yellow
    Write-Host "             Python self-check below will likely also time out." -ForegroundColor Yellow
    Write-Host "" -ForegroundColor Yellow
    Write-Host "Workaround: open YOUR OWN PowerShell window and run:" -ForegroundColor Cyan
    Write-Host "  cd $PWD" -ForegroundColor Cyan
    Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
    Write-Host "  python -u -m uvicorn app.main:app --host 0.0.0.0 --port 8000" -ForegroundColor Cyan
    Write-Host "" -ForegroundColor Yellow
  }
  Remove-Job $job -Force -ErrorAction SilentlyContinue
}

try {
  $envFile = ".\.env"
  if (Test-Path $envFile) {
    $line = Get-Content $envFile -Encoding UTF8 | Where-Object { $_ -match "^FILE_SERVER_ROOT=" } | Select-Object -First 1
    if ($line) {
      $root = ($line -split "=", 2)[1].Trim()
      if ($root -and $root.StartsWith("\\")) {
        Prewarm-SMB $root
      }
    }
  }
} catch {
  Write-Host "[pre-warm] failed (ignored): $($_.Exception.Message)" -ForegroundColor Yellow
}

& $python -u -m uvicorn app.main:app --host 0.0.0.0 --port 8000
