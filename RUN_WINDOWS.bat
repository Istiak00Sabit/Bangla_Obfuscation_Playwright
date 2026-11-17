@echo off
setlocal
cd /d "%~dp0"
if not exist "urls.txt" copy /y "urls.example.txt" "urls.txt" >nul
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
echo.
echo 1 = Login in the tool's separate browser
echo 2 = Collect using the separate browser
echo 3 = Synthetic offline demo
echo 4 = Collect using your already logged-in Google Chrome
set /p "choice=Enter 1, 2, 3 or 4: "
if "%choice%"=="4" goto :attach
if "%choice%"=="1" goto :installbrowser
if "%choice%"=="2" goto :installbrowser
if "%choice%"=="3" goto :installbrowser
echo Invalid choice.
goto :finished
:installbrowser
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto :failed
if "%choice%"=="1" ".venv\Scripts\python.exe" collector.py login
if "%choice%"=="2" ".venv\Scripts\python.exe" collector.py collect --urls urls.txt --manual
if "%choice%"=="3" ".venv\Scripts\python.exe" collector.py demo
goto :finished
:attach
echo In your normal Google Chrome open chrome://inspect/#remote-debugging
echo Enable remote debugging, keep Chrome open, then approve its prompt if shown.
pause
".venv\Scripts\python.exe" collector.py collect --urls urls.txt --attach-chrome
:finished
pause
exit /b
:failed
echo Setup failed. Install Python 3.10 or newer and check the error above.
pause
exit /b 1
