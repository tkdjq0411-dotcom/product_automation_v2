@echo off
chcp 65001 > nul
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python을 찾을 수 없습니다.
  pause
  exit /b 1
)
python -m pip install -r requirements.txt >nul 2>nul
start "" http://127.0.0.1:8000/web/
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
