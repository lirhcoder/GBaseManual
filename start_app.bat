@echo off
echo Starting Web Manual Generator...

:: Check if python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: Start Backend
echo Starting Backend Server (Port 8080)...
start "Web Manual Backend" cmd /k "web-manual serve"

:: Wait a moment for backend to initialize
timeout /t 2 /nobreak >nul

:: Start Frontend
echo Starting Frontend (Vite)...
cd src\web_manual_generator\web_editor
if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install
)
start "Web Manual Frontend" cmd /k "npm run dev"

echo.
echo ===================================================
echo Application started!
echo Backend API: http://127.0.0.1:8080/api/docs
echo Frontend UI: http://localhost:5173
echo ===================================================
echo.
