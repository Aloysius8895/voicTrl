@echo off
rem Double-click to open the voicTrl sample app at http://127.0.0.1:5310
cd /d "%~dp0"
if not exist node_modules (
  echo Installing packages, first time only...
  call npm install || goto :fail
)
echo Building...
call npm run build || goto :fail
start "" http://127.0.0.1:5310
call npm run render -- --serve
goto :eof

:fail
echo.
echo Something went wrong. Copy the messages above and send them to Claude.
pause
