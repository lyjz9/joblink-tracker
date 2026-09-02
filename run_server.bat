@echo off
setlocal
set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Linc could not find .venv\Scripts\python.exe.
    echo Finish the local setup, then try again.
    exit /b 1
)

"%PYTHON_EXE%" -m scraper.app
