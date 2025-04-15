@echo off
:: Change directory to where this script lives
cd /d "%~dp0"

:: Pull the latest code from GitHub
echo Pulling latest changes from GitHub...
git pull origin main

echo.
echo Update complete. You can now run the app.
pause