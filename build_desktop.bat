@echo off
REM Package the app into dist\FastDailyJourneyWriter\ (Windows .exe).
REM First time only:  .venv\Scripts\pip install -r requirements-dev.txt
setlocal
cd /d "%~dp0"
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean platforms\desktop\journal.spec
if errorlevel 1 (
    echo.
    echo Build failed. If PyInstaller is missing:
    echo     .venv\Scripts\pip install -r requirements-dev.txt
    exit /b 1
)
echo.
echo Done. The app is in dist\FastDailyJourneyWriter\
