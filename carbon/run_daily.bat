@echo off
rem Daily run for Windows Task Scheduler (README: schtasks /create ... /tr <path>\run_daily.bat).
rem Moves to this file's folder, runs the full pipeline, appends output and errors to logs.txt.
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo ===== %date% %time% ===== >> logs.txt
python main.py run >> logs.txt 2>&1
exit /b %errorlevel%
