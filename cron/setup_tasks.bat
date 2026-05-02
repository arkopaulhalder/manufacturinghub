@echo off
REM ==========================================================================
REM ManufacturingHub — Register Windows Task Scheduler Tasks
REM ==========================================================================
REM
REM Run this script AS ADMINISTRATOR to create scheduled tasks.
REM It registers the daily cron job to run at 6:00 AM every day.
REM
REM To view tasks:   schtasks /query /tn "ManufacturingHub*"
REM To delete tasks: schtasks /delete /tn "ManufacturingHub_DailyCron" /f
REM ==========================================================================

SET SCRIPT_PATH=C:\Users\KIIT\Desktop\manufacturinghub\cron\windows_scheduler.bat

echo.
echo === ManufacturingHub Task Scheduler Setup ===
echo.

REM --- Daily cron at 6:00 AM ---
echo Creating daily cron task (runs at 6:00 AM daily)...
schtasks /create ^
    /tn "ManufacturingHub_DailyCron" ^
    /tr "\"%SCRIPT_PATH%\"" ^
    /sc daily ^
    /st 06:00 ^
    /rl HIGHEST ^
    /f

if %errorlevel% equ 0 (
    echo [OK] Daily cron task created successfully.
) else (
    echo [ERROR] Failed to create daily cron task. Run as Administrator.
)

echo.
echo === Setup Complete ===
echo.
echo To verify:   schtasks /query /tn "ManufacturingHub_DailyCron"
echo To run now:  schtasks /run /tn "ManufacturingHub_DailyCron"
echo To delete:   schtasks /delete /tn "ManufacturingHub_DailyCron" /f
echo.
pause
