@echo off
REM Test script for Windows local testing

echo ============================================
echo SOL Market Data Tool - Windows Test
echo ============================================
echo.

REM Test Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

echo Python is installed
echo.

REM Run test script
echo Running installation test...
python test_installation.py

echo.
echo ============================================
echo To start collecting data:
echo   python collector_standalone.py
echo.
echo This will work even without Redis installed
echo (uses simulation mode for testing)
echo ============================================

pause