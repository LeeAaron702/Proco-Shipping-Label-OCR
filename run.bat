@echo off
:: Change to the folder where this script lives
cd /d "%~dp0"

:: === Load .env manually (look for SPREADSHEET_URL line)
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

:: === Virtual Environment Setup
if not exist "env\Scripts\activate.bat" (
    echo Virtual environment not found.
    echo Creating virtual environment...
    python -m venv env
)

call env\Scripts\activate

pip show google-auth >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo Running Smart Label OCR...
python main.py

pause
