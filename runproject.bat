@echo off
setlocal
cd /d "%~dp0"

rem Backend: http://127.0.0.1:8000   Frontend (UI): http://localhost:5173
rem No --reload on purpose: a reload would kill a running transcription or render job.

set BACKEND_UP=0
set FRONTEND_UP=0
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul && set BACKEND_UP=1
netstat -ano | findstr /R /C:":5173 .*LISTENING" >nul && set FRONTEND_UP=1

if "%BACKEND_UP%"=="1" (
  echo [ok] port 8000 is already in use - assuming the backend is running
) else if not exist "UI\backend\main.py" (
  echo [skip] UI\backend\main.py not found
) else if not exist ".venv\Scripts\python.exe" (
  echo [error] .venv\Scripts\python.exe not found - the Python environment is missing
) else (
  start "Backend" cmd /k ".venv\Scripts\python.exe -m uvicorn UI.backend.main:app --host 127.0.0.1 --port 8000"
)

echo.
echo Waiting for the backend...
for /l %%i in (1,1,40) do (
  curl -s -f http://127.0.0.1:8000/health >nul 2>&1 && goto backend_ready
  "%SystemRoot%\System32\timeout.exe" /t 1 /nobreak >nul
)
echo [warn] the backend did not answer within 40 seconds - check the Backend window

:backend_ready

if not exist "UI\frontend\package.json" goto no_frontend

if "%FRONTEND_UP%"=="1" (
  echo [ok] port 5173 is already in use - assuming the UI is running.
) else if not exist "UI\frontend\node_modules" (
  echo [info] UI\frontend\node_modules is missing - installing dependencies...
  call npm --prefix "%~dp0UI\frontend" install
  start "Frontend" /D "%~dp0UI\frontend" cmd /k "npm run dev"
) else (
  start "Frontend" /D "%~dp0UI\frontend" cmd /k "npm run dev"
)

echo.
echo Waiting for the UI...
for /l %%i in (1,1,40) do (
  curl -s -f http://localhost:5173 >nul 2>&1 && goto ui_ready
  "%SystemRoot%\System32\timeout.exe" /t 1 /nobreak >nul
)
echo [warn] the UI did not answer within 40 seconds - check the Frontend window

:ui_ready
echo.
echo Backend: http://localhost:8000   UI: http://localhost:5173
start "" http://localhost:5173
goto done

:no_frontend
echo.
echo [ok] Backend API is active at: http://127.0.0.1:8000
echo [info] Frontend UI is currently removed - backend-only mode.
echo [docs] Opening Swagger API documentation: http://127.0.0.1:8000/docs
start "" http://127.0.0.1:8000/docs

:done
echo.
pause
