@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
title Flood Voice Agent - Ready

echo ==========================================
echo  Chennai Flood Voice Agent (DeepSeek + LiveKit)
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
set /p START=Start the voice agent now? [y/N]: 
if /I "%START%"=="y" goto start
if /I "%START%"=="n" goto cancel
if "%START%"=="" goto cancel
echo Please type Y or N.
goto prompt

:start
echo.
echo Starting the voice agent...
echo STATUS: the agent speaks first, then listens. Speak into the mic.
echo   Try: "Give me directions"
echo   Try: "Am I safe?"
echo   Press Ctrl+C or close this window to stop.
echo.
".venv\Scripts\python.exe" -m voice.family_agent console
echo.
echo [Voice agent stopped]
pause
exit /b 0

:cancel
echo.
echo Demo not started. This window will stay open.
pause
exit /b 0
