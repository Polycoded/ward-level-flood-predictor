@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
set PYTHONUTF8=1
title Flood Voice Agent - Browser Ready

echo ==========================================
echo  Chennai Flood Voice Agent (browser)
echo ==========================================
echo.

if not exist ".env" (
  echo [ERROR] .env missing. Copy .env.example to .env and fill the keys.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv missing. Run: uv sync --extra voice
  pause
  exit /b 1
)

echo [1/2] Checking voice dependencies...
".venv\Scripts\python.exe" -c "import voice.family_agent" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Dependencies missing. Run: uv sync --extra voice
  pause
  exit /b 1
)

echo [2/2] Loading the spoken alert into the TTS cache...
".venv\Scripts\python.exe" -m voice.prewarm >nul 2>&1

echo.
echo ==========================================
echo  READY - everything is loaded.
echo.
echo  Press Y then Enter to start the demo.
echo  Press N then Enter to cancel.
echo ==========================================
echo.

:prompt
set "START="
set /p START=Start the browser demo now? [y/N]: 
if /I "%START%"=="y" goto start
if /I "%START%"=="n" goto cancel
if "%START%"=="" goto cancel
echo Please type Y or N.
goto prompt

:start
echo.
echo Starting the agent worker in a new window...
start "Flood Voice Worker" cmd /k ".venv\Scripts\python.exe -m voice.family_agent dev"

echo Waiting for the worker to register...
timeout /t 8 /nobreak >nul

echo Creating the demo room and join link...
".venv\Scripts\python.exe" -m voice.demo --ward-name "Ward 14" --risk-level high --rainfall 120 --duration 6 --language en --room "flood-alert-demo" > "%TEMP%\flood_demo.txt"

for /f "tokens=*" %%L in ('findstr /b "https://meet.livekit.io" "%TEMP%\flood_demo.txt"') do set "URL=%%L"

if defined URL (
  echo Opening the browser...
  start "" "!URL!"
) else (
  echo Could not create the join link. Output:
  type "%TEMP%\flood_demo.txt"
)

echo.
echo Click Join in the browser and allow the microphone.
echo Close the worker window to stop the agent.
pause
exit /b 0

:cancel
echo.
echo Demo not started. This window will stay open.
pause
exit /b 0
