@echo off
setlocal

echo.
echo === MathCraft self-host launcher ===
echo.

where cloudflared >nul 2>&1
if errorlevel 1 (
    echo X cloudflared is not on PATH.
    echo   Install it from: https://github.com/cloudflare/cloudflared/releases
    echo   Or: winget install --id Cloudflare.cloudflared
    exit /b 1
)

if not exist "backend\venv" (
    echo X Backend venv not found. Run setup.bat first.
    exit /b 1
)

echo Starting backend on http://localhost:8000 ...
start "MathCraft backend" cmd /k "cd backend && call venv\Scripts\activate.bat && uvicorn main:app --host 127.0.0.1 --port 8000"

echo.
echo Waiting 4 seconds for backend to come up...
timeout /t 4 /nobreak >nul

echo.
echo Starting Cloudflare quick tunnel...
echo Look for the line ^"https://...trycloudflare.com^" below — copy that URL,
echo then on the GitHub Pages site click ^"Connect backend^" and paste it.
echo.
echo Press Ctrl+C in this window to stop the tunnel (the backend keeps running
echo in its own window — close that window to stop the backend too).
echo.

cloudflared tunnel --url http://localhost:8000

endlocal
