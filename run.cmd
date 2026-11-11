@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "TRAFFIC_PY=%LOCALAPPDATA%\TrafficImpactLab\venv\Scripts\python.exe"
if not exist "%TRAFFIC_PY%" (
  echo Python environment missing. Run setup.cmd first.
  pause
  exit /b 1
)
"%TRAFFIC_PY%" -m streamlit run "%~dp0app.py" --server.headless false --server.address 127.0.0.1 --server.port 8502
pause

