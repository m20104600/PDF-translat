@echo off
echo Starting Custom PDF Backend (app.main_new)...
echo Use the Official WebUI via start.bat if you want a complete GUI experience.
echo.
python -m uvicorn app.main_new:app --reload --port 8000
pause
