@echo off

set "ROOT=%~dp0"
cd /d "%ROOT%backend"

echo ============================================================
echo  Controlled File Platform - Launcher
echo ============================================================
echo.

echo [1/6] Check Python ...
where python >nul 2>&1
if errorlevel 1 (
  echo   [X] python not found in PATH. Install Python 3.10+ and tick "Add to PATH".
  goto :fail
)
python --version
echo.

echo [2/6] Prepare .venv ...
if not exist ".venv\Scripts\python.exe" (
  echo   Creating venv ...
  python -m venv .venv
  if errorlevel 1 (
    echo   [X] venv creation failed
    goto :fail
  )
)
call ".venv\Scripts\activate.bat"
echo   [OK] venv ready
echo.

echo [3/6] Check dependencies ...
if exist ".venv\Scripts\uvicorn.exe" (
  echo   [OK] deps cached, skip pip install
) else (
  echo   Installing deps via Tsinghua mirror ...
  python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
  python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  if errorlevel 1 (
    echo   [X] dependency install failed
    goto :fail
  )
)
echo.

echo [4/6] Check .env ...
if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo   .env copied from .env.example
)
echo   Current config:
findstr /B "FILE_SERVER_ROOT DML_FILENAME CONTROLLED_DIR MOCK_EXTERNAL APP_PORT REQUIRE_WRITABLE_FS" .env
echo.

echo [5/6] Check DML template ...
if not exist "templates\DML_template.xlsx" (
  echo   [X] template missing: backend\templates\DML_template.xlsx
  goto :fail
)
echo   [OK] templates\DML_template.xlsx
echo.

echo [6/6] Check port 8000 ...
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if errorlevel 1 (
  echo   [OK] port 8000 free
) else (
  echo   [!] port 8000 already in use:
  netstat -ano | findstr ":8000 " | findstr "LISTENING"
  echo   Kill it via:  taskkill /F /PID ^<PID at end of the line above^>
  goto :fail
)
echo.

echo ============================================================
echo  Starting uvicorn via PowerShell at http://localhost:8000/ui/
echo  (PowerShell layer pre-warms the SMB session before Python starts)
echo  Press Ctrl+C to stop
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File ".\run_uvicorn.ps1"

echo.
echo ============================================================
echo  uvicorn exited.  Press any key to close this window.
echo ============================================================
pause >nul
goto :eof


:fail
echo.
echo ============================================================
echo  STARTUP FAILED - copy the messages above and send to dev.
echo  Press any key to close.
echo ============================================================
pause >nul
