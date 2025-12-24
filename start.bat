@echo off
setlocal
echo Starting PDF Translator...

:: Switch to backend directory
cd /d "%~dp0backend"

:: Set UI Language and Python Path
set PDF2ZH_UI_LANG=zh
set PYTHONPATH=.

:: Start application (Default to New Web UI)
python -m pdf2zh_next.main --gui

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Application failed to start. 
    echo Please ensure Python and dependencies are installed.
    pause
)
endlocal
