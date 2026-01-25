@echo off
echo ========================================
echo   Trident Emergency Response System
echo ========================================
echo.

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

echo Python found! Checking virtual environment...
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo Installing/updating dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Starting Trident Emergency System
echo ========================================
echo.
echo The application will start in a few seconds...
echo.
echo Access URLs:
echo   Main App:    http://localhost:5000
echo   Dashboard:   http://localhost:5000/dashboard
echo   Analytics:   http://localhost:5000/analytics
echo.
echo Press Ctrl+C to stop the server
echo.

python app.py

echo.
echo Application stopped.
pause
