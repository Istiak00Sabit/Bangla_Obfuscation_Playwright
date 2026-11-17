@echo off
setlocal
cd /d "%~dp0"
git pull --ff-only
if errorlevel 1 goto :failed
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :failed
)
echo.
echo Updated. Start RUN_WINDOWS.bat when ready.
pause
exit /b 0
:failed
echo Update stopped. Review the error above; your local data has not been reset.
pause
exit /b 1
