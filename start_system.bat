@echo off
setlocal enabledelayedexpansion

title PhishGuard AI - Email Phishing Detection System
cls
echo ===================================================
echo   Starting PhishGuard AI Phishing Detection System
echo ===================================================
echo.

cd /d "%~dp0"
set "BACKEND_DIR=%~dp0backend"

if exist "%BACKEND_DIR%\.venv-1\Scripts\python.exe" (
  set "PYTHON_EXE=%BACKEND_DIR%\.venv-1\Scripts\python.exe"
) else if exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
  set "PYTHON_EXE=%BACKEND_DIR%\venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)

echo [1/3] Starting FastAPI Backend Server on port 8000...
start "PhishGuard Backend" cmd /k "cd /d "%BACKEND_DIR%" && "!PYTHON_EXE!" -m uvicorn app.main:app --reload --port 8000"

timeout /t 3 >nul

echo [2/3] Starting React Vite Frontend Server...
start "PhishGuard Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev -- --host 0.0.0.0"

timeout /t 3 >nul

echo [3/3] Opening Dashboard in default browser...
start http://localhost:5173

echo.
echo ===================================================
echo   System launched successfully!
echo   Frontend: http://localhost:5173
echo   Backend API: http://localhost:8000/docs
echo ===================================================
pause
