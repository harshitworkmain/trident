@echo off
REM Local run on Windows: API + web console on http://localhost:8000
REM   start_app.bat          API only
REM   start_app.bat --demo   API + virtual wearables streaming real recordings
cd /d "%~dp0\..\.."

if not exist src\frontend\web\dist\index.html (
  echo Building the web console...
  pushd src\frontend\web && call npm ci && call npm run build && popd
)

if "%1"=="--demo" (
  start "TRIDENT API" python -m uvicorn src.backend.app.main:app --host 127.0.0.1 --port 8000
  timeout /t 5 /nobreak >nul
  python -m src.backend.app.tools.simulate --api http://localhost:8000 --speed 1 --with-sos
) else (
  python -m uvicorn src.backend.app.main:app --host 127.0.0.1 --port 8000
)
