@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo ============================================================
echo  memory-agent - start all services (Windows)
echo ============================================================
echo.

rem ---------------------------------------------------------------
rem 1. Locate the Python interpreter
rem    Priority: MEMORYAGENT_PYTHON env var > .venv in repo > PATH
rem ---------------------------------------------------------------
set "PYTHON=%MEMORYAGENT_PYTHON%"
if not defined PYTHON if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not defined PYTHON if exist "%ROOT%\backend\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\backend\.venv\Scripts\python.exe"
if not defined PYTHON for /f "delims=" %%i in ('where python 2^>nul') do if not defined PYTHON set "PYTHON=%%i"

if not defined PYTHON (
    echo [ERROR] Python interpreter not found.
    echo         Activate your virtualenv first, or set MEMORYAGENT_PYTHON
    echo         to the full path of python.exe.
    pause
    exit /b 1
)
echo [info] Python       : %PYTHON%

rem lightrag-server is installed next to the interpreter (Scripts\)
for %%i in ("%PYTHON%") do set "PYDIR=%%~dpi"
set "PYDIR=%PYDIR:~0,-1%"
set "LIGHTRAG="
if exist "%PYDIR%\lightrag-server.exe" set "LIGHTRAG=%PYDIR%\lightrag-server.exe"
if not defined LIGHTRAG if exist "%PYDIR%\..\Scripts\lightrag-server.exe" set "LIGHTRAG=%PYDIR%\..\Scripts\lightrag-server.exe"
if not defined LIGHTRAG set "LIGHTRAG=lightrag-server"
echo [info] lightrag-server: %LIGHTRAG%

rem UTF-8 output, avoids mojibake on GBK consoles
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem ---------------------------------------------------------------
rem 2. Sanity checks
rem ---------------------------------------------------------------
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install it from https://nodejs.org/
    pause
    exit /b 1
)

if not exist "%ROOT%\backend\.env" echo [WARN] backend\.env missing - copy backend\.env.example to backend\.env and fill in your keys
if not exist "%ROOT%\lightrag\.env" echo [WARN] lightrag\.env missing - copy lightrag\.env.example to lightrag\.env and fill in your keys
if not exist "%ROOT%\frontend\node_modules" echo [WARN] frontend\node_modules missing - run: cd frontend ^&^& npm install

rem ---------------------------------------------------------------
rem 3. Free the ports we are about to use
rem ---------------------------------------------------------------
echo [0/3] Freeing ports 8000 9621 5173 5174 5175 ...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 :9621 :5173 :5174 :5175" 2^>nul') do (
    if not "%%p"=="0" taskkill /PID %%p /F >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo       done.

rem ---------------------------------------------------------------
rem 4. Start services
rem ---------------------------------------------------------------
echo [1/3] LightRAG Server  ^(port 9621^)
start "LightRAG" /D "%ROOT%\lightrag" cmd /k ""%LIGHTRAG%""

timeout /t 6 /nobreak >nul

echo [2/3] Backend          ^(port 8000^)
start "Backend" /D "%ROOT%\backend" cmd /k ""%PYTHON%" -m uvicorn app.main:app --reload --port 8000"

timeout /t 3 /nobreak >nul

echo [3/3] Frontend         ^(port 5173^)
start "Frontend" /D "%ROOT%\frontend" cmd /k "npm run dev"

echo.
echo ============================================================
echo  All services launched. Give them ~10s to come up.
echo    LightRAG : http://localhost:9621/health
echo    Backend  : http://localhost:8000/health
echo    Frontend : http://localhost:5173
echo ============================================================
echo.
pause
endlocal
