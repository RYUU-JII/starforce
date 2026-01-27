@echo off
chcp 65001 > nul
title 스타포스 크롤러 - 1회 크롤링

echo ================================================
echo   넥슨 나우 스타포스 크롤러 - 1회 크롤링
echo ================================================
echo.

cd /d "%~dp0"
call .venv\Scripts\activate.bat 2>nul

python -m crawler.main --headless

echo.
echo ================================================
echo   크롤링 완료!
echo ================================================
pause
