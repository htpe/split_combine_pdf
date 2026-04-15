@echo off
echo.
echo ====================================================
echo  PDF Split & Combine - Application Startup
echo ====================================================
echo.
echo [1/3] Checking Python installation...
python --version
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

echo [2/3] Checking dependencies...
pip show PyQt6 >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt --prefer-binary
)

echo [3/3] Launching application...
python main.py

pause
