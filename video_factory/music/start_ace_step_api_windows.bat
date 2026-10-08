@echo off
setlocal
set "ACE_DIR=%USERPROFILE%\VideoFactoryTools\ACE-Step-1.5"
if not exist "%ACE_DIR%" (
  echo ACE-Step 1.5 is not installed.
  echo Run install_ace_step_windows.ps1 first.
  pause
  exit /b 1
)
cd /d "%ACE_DIR%"
echo Starting ACE-Step API on http://127.0.0.1:8001
uv run acestep-api
pause
