#requires -Version 5
# 直接在 PowerShell 里启动受控文件工具平台
# 用法 (PowerShell 窗口):
#   cd C:\Users\longkang.lin\Desktop\受控工具平台
#   .\start.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$VenvUvicorn = Join-Path $Backend ".venv\Scripts\uvicorn.exe"

Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host " Controlled File Platform - Launcher (PowerShell)" -ForegroundColor Cyan
Write-Host "=============================================================`n" -ForegroundColor Cyan

Set-Location $Backend

# [1] python
Write-Host "[1/6] Python ..."
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $pythonExe) {
  Write-Host "  [X] python not in PATH; install Python 3.10+ and tick 'Add to PATH'" -ForegroundColor Red
  Read-Host "Press Enter to exit"; exit 1
}
& python --version

# [2] venv
Write-Host "`n[2/6] Virtual environment ..."
if (-not (Test-Path $VenvPython)) {
  Write-Host "  Creating venv ..."
  & python -m venv .venv
}
Write-Host "  [OK] venv ready"

# [3] deps
Write-Host "`n[3/6] Dependencies ..."
if (Test-Path $VenvUvicorn) {
  Write-Host "  [OK] deps cached"
} else {
  Write-Host "  Installing via Tsinghua mirror ..."
  & $VenvPython -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
  & $VenvPython -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
}

# [4] .env
Write-Host "`n[4/6] .env ..."
if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "  .env copied from .env.example"
}
Get-Content ".env" -Encoding UTF8 | Select-String -Pattern "^(FILE_SERVER_ROOT|DML_FILENAME|CONTROLLED_DIR|MOCK_EXTERNAL|APP_PORT|REQUIRE_WRITABLE_FS)=" | ForEach-Object { "  " + $_.Line }

# [5] DML template
Write-Host "`n[5/6] DML template ..."
if (-not (Test-Path "templates\DML_template.xlsx")) {
  Write-Host "  [X] missing backend\templates\DML_template.xlsx" -ForegroundColor Red
  Read-Host "Press Enter to exit"; exit 1
}
Write-Host "  [OK] templates\DML_template.xlsx"

# [6] port 8000
Write-Host "`n[6/6] Port 8000 ..."
$busy = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($busy) {
  Write-Host "  [!] occupied by PID(s):" -ForegroundColor Yellow
  $busy | Select-Object LocalAddress, OwningProcess | Format-Table -AutoSize | Out-String | Write-Host
  Write-Host "  Stop it via:  Stop-Process -Id <PID> -Force"
  Read-Host "Press Enter to exit"; exit 1
}
Write-Host "  [OK] free"

Write-Host "`n=============================================================" -ForegroundColor Green
Write-Host " Starting uvicorn  http://localhost:8000/ui/" -ForegroundColor Green
Write-Host " Ctrl+C to stop" -ForegroundColor Green
Write-Host "=============================================================`n" -ForegroundColor Green

try {
  & $VenvPython -m uvicorn app.main:app --host 0.0.0.0 --port 8000
} catch {
  Write-Host "uvicorn exited with error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== Server stopped. Press Enter to close. ===" -ForegroundColor Cyan
Read-Host | Out-Null
