@echo off
setlocal

echo.
echo === MathCraft self-host launcher ===
echo.

REM Locate cloudflared. Try PATH first, then the standard winget install dir.
set "CFLARED="
where cloudflared >nul 2>&1
if not errorlevel 1 (
    set "CFLARED=cloudflared"
) else if exist "%ProgramFiles(x86)%\cloudflared\cloudflared.exe" (
    set "CFLARED=%ProgramFiles(x86)%\cloudflared\cloudflared.exe"
) else if exist "%ProgramFiles%\cloudflared\cloudflared.exe" (
    set "CFLARED=%ProgramFiles%\cloudflared\cloudflared.exe"
)

if "%CFLARED%"=="" (
    echo X cloudflared not found.
    echo   Install it: winget install --id Cloudflare.cloudflared
    echo   Then open a NEW PowerShell window so PATH picks it up.
    exit /b 1
)

if not exist "backend\venv" (
    echo X Backend venv not found. Run setup.bat first.
    exit /b 1
)

echo Using cloudflared: %CFLARED%
echo.
echo Starting backend on http://localhost:8000 ...
start "MathCraft backend" cmd /k "cd backend && call venv\Scripts\activate.bat && uvicorn main:app --host 127.0.0.1 --port 8000"

echo.
echo Waiting 4 seconds for backend to come up...
timeout /t 4 /nobreak >nul

echo.
echo Starting Cloudflare quick tunnel...
echo Look for the line "https://...trycloudflare.com" below — copy that URL,
echo then on the GitHub Pages site click "Connect backend" and paste it.
echo.
echo Press Ctrl+C in this window to stop the tunnel (the backend keeps running
echo in its own window — close that window to stop the backend too).
echo.

"%CFLARED%" tunnel --url http://localhost:8000

endlocal
