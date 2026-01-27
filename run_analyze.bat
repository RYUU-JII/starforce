@echo off
chcp 65001 > nul
title 스타포스 크롤러 - 조작 탐지 분석

echo ================================================
echo   스타포스 확률 조작 탐지 분석
echo ================================================
echo.

cd /d "%~dp0"
call .venv\Scripts\activate.bat 2>nul

python -m crawler.main --analyze

echo.
echo ================================================
echo   분석 완료! 리포트는 sessions 폴더에 저장됩니다.
echo ================================================
pause
