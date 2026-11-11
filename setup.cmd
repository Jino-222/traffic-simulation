@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "TRAFFIC_ENV=%LOCALAPPDATA%\TrafficImpactLab\venv"
if not exist "%TRAFFIC_ENV%\Scripts\python.exe" (
  py -3.11 -m venv "%TRAFFIC_ENV%"
  if errorlevel 1 (
    echo Install Python 3.11 from python.org, including the Python launcher.
    pause
    exit /b 1
  )
)
set "TRAFFIC_REQUIREMENTS=%~dp0requirements.txt"
if exist "%~dp0requirements-lock.txt" set "TRAFFIC_REQUIREMENTS=%~dp0requirements-lock.txt"
"%TRAFFIC_ENV%\Scripts\python.exe" -m pip install -r "%TRAFFIC_REQUIREMENTS%"
if errorlevel 1 (
  echo Installation failed. Check the output above.
  pause
  exit /b 1
)
echo Setup complete. Open run.cmd.
pause

