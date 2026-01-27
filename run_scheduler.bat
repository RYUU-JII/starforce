@echo off
chcp 65001 > nul
title 스타포스 크롤러 - 스케줄러

echo ================================================
echo   넥슨 나우 스타포스 크롤러 - 스케줄러 모드
echo   1시간마다 자동 크롤링 + 패치 자동 감지
echo ================================================
echo.

cd /d "%~dp0"
call .venv\Scripts\activate.bat 2>nul

python -m crawler.main --schedule

pause
