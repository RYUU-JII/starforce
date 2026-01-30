@echo off
setlocal

set "HOST=127.0.0.1"
set "PORT=8000"

if not "%~1"=="" set "PORT=%~1"

set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"

%PY% -m uvicorn main:app --reload --host %HOST% --port %PORT%

