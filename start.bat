@echo off
echo ============================================================
echo  Agentic RAG - Start All Services
echo ============================================================
echo.

set PYTHON=D:\Dev\envs\lang\python.exe
set LIGHTRAG=D:\Dev\envs\lang\Scripts\lightrag-server.exe

echo [0/3] Clearing any leftover processes on ports 8000 9621 5173 5174 5175...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 :9621 :5173 :5174 :5175" 2^>nul') do (
    if not "%%p"=="0" (
        taskkill /PID %%p /F >nul 2>&1
    )
)
timeout /t 1 /nobreak >nul
echo Done.

if not exist "%PYTHON%" (
    echo [ERROR] Python not found: %PYTHON%
    pause
    exit /b 1
)

if not exist "%LIGHTRAG%" (
    echo [ERROR] lightrag-server not found: %LIGHTRAG%
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] node not found. Make sure Node.js is installed.
    pause
    exit /b 1
)

echo [1/3] Starting LightRAG Server (port 9621)...
start "LightRAG" cmd /k "cd /d D:\hackthon\lightrag && "%LIGHTRAG%""

timeout /t 6 /nobreak >nul

echo [2/3] Starting Backend (port 8000)...
start "Backend" cmd /k "cd /d D:\hackthon\backend && %PYTHON% -m uvicorn app.main:app --reload --port 8000"

timeout /t 3 /nobreak >nul

echo [3/3] Starting Frontend (port 5173)...
start "Frontend" cmd /k "cd /d D:\hackthon\frontend && npm run dev"

echo.
echo ============================================================
echo  All services started. Wait ~10s for them to be ready.
echo  LightRAG : http://localhost:9621/health
echo  Backend  : http://localhost:8000/health
echo  Frontend : http://localhost:5173
echo ============================================================
echo.
pause
