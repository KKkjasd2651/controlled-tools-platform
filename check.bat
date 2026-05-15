@echo off

set "ROOT=%~dp0"

echo ============================================================
echo  Controlled File Platform - Environment Check (read-only)
echo ============================================================
echo.

echo --- Python ---
where python 2>nul
if errorlevel 1 echo   [X] python not in PATH
python --version 2>nul
echo.

echo --- Project root ---
echo   %ROOT%
echo.

echo --- Virtual environment ---
if exist "%ROOT%backend\.venv\Scripts\python.exe" (
  echo   [OK] backend\.venv exists
  "%ROOT%backend\.venv\Scripts\python.exe" --version
  if exist "%ROOT%backend\.venv\Scripts\uvicorn.exe" (
    echo   [OK] uvicorn installed
  ) else (
    echo   [!] uvicorn not installed; first run.bat will pip install
  )
) else (
  echo   [!] backend\.venv missing; first run.bat will create it
)
echo.

echo --- .env config ---
if exist "%ROOT%backend\.env" (
  findstr /B "FILE_SERVER_ROOT DML_FILENAME CONTROLLED_DIR MOCK_EXTERNAL APP_PORT REQUIRE_WRITABLE_FS" "%ROOT%backend\.env"
) else (
  echo   [!] backend\.env missing; run.bat will copy from .env.example
)
echo.

echo --- DML template ---
if exist "%ROOT%backend\templates\DML_template.xlsx" (
  echo   [OK] backend\templates\DML_template.xlsx
) else (
  echo   [X] template missing
)
echo.

echo --- Port 8000 ---
netstat -ano | findstr ":8000 " | findstr "LISTENING"
if errorlevel 1 (
  echo   [OK] port 8000 free
) else (
  echo   [!] occupied; kill with: taskkill /F /PID ^<PID at end of above line^>
)
echo.

echo ============================================================
echo  Check complete. Press any key to close.
echo ============================================================
pause >nul
