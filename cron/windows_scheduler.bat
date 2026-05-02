@echo off
REM ==========================================================================
REM ManufacturingHub — Windows Task Scheduler Script
REM ==========================================================================
REM
REM This batch file runs all daily cron jobs for the ManufacturingHub app.
REM Schedule this in Windows Task Scheduler (see setup_tasks.bat below).
REM
REM BEFORE RUNNING:
REM   1. Update APP_DIR to your project path
REM   2. Update VENV_DIR to your virtual environment path
REM ==========================================================================

SET APP_DIR=C:\Users\KIIT\Desktop\manufacturinghub
SET VENV_DIR=C:\Users\KIIT\Desktop\manufacturinghub\.projectenv
SET FLASK_APP=run.py
SET FLASK_ENV=development
SET LOG_DIR=%APP_DIR%\logs

REM Create logs directory if it doesn't exist
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [%date% %time%] === ManufacturingHub Daily Cron Start === >> "%LOG_DIR%\daily_cron.log"

REM --- US-6: Low Stock Check ---
echo [%date% %time%] Running low-stock check... >> "%LOG_DIR%\daily_cron.log"
cd /d "%APP_DIR%"
call "%VENV_DIR%\Scripts\flask.exe" notify low-stock >> "%LOG_DIR%\daily_cron.log" 2>&1

REM --- US-7: Maintenance Due Check ---
echo [%date% %time%] Running maintenance-due check... >> "%LOG_DIR%\daily_cron.log"
call "%VENV_DIR%\Scripts\flask.exe" notify maintenance-due >> "%LOG_DIR%\daily_cron.log" 2>&1

REM --- US-7: Auto-update Machine Status ---
echo [%date% %time%] Running machine status update... >> "%LOG_DIR%\daily_cron.log"
call "%VENV_DIR%\Scripts\flask.exe" notify update-machine-status >> "%LOG_DIR%\daily_cron.log" 2>&1

REM --- US-8: Process Notification Queue ---
echo [%date% %time%] Processing notification queue... >> "%LOG_DIR%\daily_cron.log"
call "%VENV_DIR%\Scripts\flask.exe" notify process-queue >> "%LOG_DIR%\daily_cron.log" 2>&1

echo [%date% %time%] === ManufacturingHub Daily Cron Complete === >> "%LOG_DIR%\daily_cron.log"
echo. >> "%LOG_DIR%\daily_cron.log"
