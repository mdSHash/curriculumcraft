@echo off
echo.
echo  MathCraft — Setup Script
echo ==========================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo X Python 3 is required. Install from https://python.org
    exit /b 1
)
echo √ Python found

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo X Node.js is required. Install from https://nodejs.org
    exit /b 1
)
echo √ Node.js found
echo.

REM Backend setup
echo Setting up backend...
cd backend

if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet

if not exist ".env" (
    copy .env.example .env >nul
    echo   Created .env from template
)

if not exist "data\uploads" mkdir data\uploads
if not exist "data\workbooks" mkdir data\workbooks
if not exist "data\faiss_indices" mkdir data\faiss_indices

cd ..
echo √ Backend ready
echo.

REM Frontend setup
echo Setting up frontend...
cd frontend
call npm install --silent
cd ..
echo √ Frontend ready
echo.

echo ==========================
echo Setup complete!
echo.
echo To start the app:
echo   Terminal 1: cd backend ^&^& venv\Scripts\activate ^&^& uvicorn main:app --reload --port 8000
echo   Terminal 2: cd frontend ^&^& npm run dev
echo.
echo Then open http://localhost:5173
pause
