@echo off
chcp 65001 > nul
cd /d "%~dp0"
python naver_api_setup.py
pause
