@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo Starting Auto Shorts... (press Ctrl+C to stop)
timeout /t 4 >nul
start "" http://127.0.0.1:5000
python app.py
