@echo off
chcp 65001 > nul
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python을 찾을 수 없습니다.
  pause
  exit /b 1
)
echo [1/4] API 보안 설정 확인...
python secret_bootstrap.py
if errorlevel 1 goto :fail
echo [2/4] Python 패키지 확인...
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo [3/4] URL 자동소싱용 Chromium 확인...
python -m playwright install chromium
if errorlevel 1 (
  echo Chromium 설치를 완료하지 못했습니다. 일반 URL 수집은 동작하지만 동적 오픈마켓 수집률이 낮아질 수 있습니다.
)
echo [4/4] B2B SaaS 실행...
start "" http://127.0.0.1:8000/web/
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
exit /b 0
:fail
echo 실행 준비에 실패했습니다.
pause
exit /b 1
