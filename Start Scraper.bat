@echo off
echo ========================================================
echo         SCHOLAR SCRAPER - DASHBOARD LAUNCHER
echo ========================================================
echo.

echo [1/3] Checking for and closing any old ghost servers...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000') do taskkill /F /PID %%a >nul 2>&1

echo [2/3] Starting the Flask server...
cd "Code File"
:: Start the server in a new minimized command prompt window so it doesn't block
start "Scholar Scraper Server" /MIN "..\.venv\Scripts\python.exe" app.py

echo [3/3] Waiting for server to initialize...
timeout /t 3 /nobreak >nul

echo Opening dashboard in your default browser...
start http://127.0.0.1:5000

echo.
echo Done! You can close this black window. The server will keep running in the minimized window.
timeout /t 3 >nul
