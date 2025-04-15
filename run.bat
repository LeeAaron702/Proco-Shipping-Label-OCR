@echo off
:: Change to the folder this script lives in
cd /d "%~dp0"

:: --- Load spreadsheet URL from .env ---
setlocal enabledelayedexpansion
set "SPREADSHEET_URL="
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if "%%A"=="SPREADSHEET_URL" set "SPREADSHEET_URL=%%B"
)
if defined SPREADSHEET_URL (
    start "" "!SPREADSHEET_URL!"
) else (
    echo Warning: SPREADSHEET_URL not found in .env
)

:: --- Pull latest changes from GitHub ---
echo Checking for updates...
git pull origin main
echo Update complete.
echo.

:: --- Setup virtual environment ---
if not exist "env\Scripts\activate.bat" (
    echo Virtual environment not found.
    echo Creating virtual environment...
    python -m venv env
)

call env\Scripts\activate

:: --- Install dependencies if needed ---
pip show google-auth >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

:: --- Launch the app ---
echo Running Smart Label OCR...
python main.py

pause
