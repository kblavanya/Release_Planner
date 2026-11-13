@echo off
echo ==========================================
echo    JIRA Release Planning Tool Launcher
echo ==========================================
echo.

REM Change to the project directory
cd /d "C:\Release_Planning"

REM Check if we're in the right directory
if not exist "app_simple.py" (
    echo ERROR: app_simple.py not found in current directory!
    echo Current directory: %CD%
    echo.
    echo Please make sure you're running this from the Release_Planning folder.
    pause
    exit /b 1
)

echo ✓ Found project files in: %CD%
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python and make sure it's added to your PATH.
    pause
    exit /b 1
)

echo ✓ Python is available
echo.

REM Install/update dependencies
echo Installing/updating dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo WARNING: Failed to install some dependencies
    echo The application might not work properly
    echo.
)

echo.
echo ==========================================
echo    Starting JIRA Release Planning Tool
echo ==========================================
echo.
echo Starting the application...
echo.
echo ******************************************
echo * WATCH FOR: "*** APPLICATION IS READY! ***" *
echo * When you see that message, the app    *
echo * is ready to use!                      *
echo ******************************************
echo.
echo Then open your browser to: http://localhost:5001
echo.
echo Press Ctrl+C in this window to stop the server
echo ==========================================
echo.

REM Start the Flask application
python app_simple.py

echo.
echo ==========================================
echo    Application has stopped
echo ==========================================
echo.
pause
