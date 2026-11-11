@echo off
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\TrafficImpactLab\portfolio-venv\Scripts\python.exe" (
  "%LOCALAPPDATA%\TrafficImpactLab\portfolio-venv\Scripts\python.exe" launch_gallery.py --open
) else (
  py -3 launch_gallery.py --open
)
pause
