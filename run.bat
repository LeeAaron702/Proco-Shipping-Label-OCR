@echo off
:: Change directory to the folder this script is in
cd /d "%~dp0"

:: Check if virtual environment exists
if not exist "env\Scripts\activate.bat" (
    echo Virtual environment not found.
    echo Creating virtual environment...
    python -m venv env
)

:: Activate virtual environment
call env\Scripts\activate

:: Check if dependencies are installed
pip show google-auth >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

:: Run the app
echo Running Smart Label OCR...
python main.py

pause
