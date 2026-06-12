@echo off
REM Launches RockForge locally (no Docker) in a single window.
REM Redis and the Celery worker run in the background (logs in .\logs\);
REM the API runs in the foreground here. Ctrl+C stops the API; the
REM background processes are then stopped too.
REM Requires: pip install -e ".[dev,ml]" and redis-server on PATH
REM (e.g. Memurai or WSL redis-server).

setlocal
cd /d "%~dp0"
if not exist logs mkdir logs

REM Use the project's virtualenv when present (children inherit the PATH).
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat

REM The ML stack requires Python 3.11 (tensorflow wheel ceiling). Prefer an
REM explicit 3.11 via the py launcher when the default python is another
REM version (no virtualenv needed).
set "PY=python"
py -3.11 -c "" >nul 2>&1
if not errorlevel 1 set "PY=py -3.11"

echo A iniciar Redis em segundo plano (logs\redis.log)...
start "RockForge-Redis" /min cmd /c "redis-server > logs\redis.log 2>&1"

echo A iniciar o worker Celery em segundo plano (logs\worker.log)...
start "RockForge-Worker" /min cmd /c "%PY% -m celery -A rockforge.interfaces.worker.celery_app:celery_app worker --pool=solo --loglevel=info > logs\worker.log 2>&1"

echo.
echo Redis e Worker a correr minimizados. A iniciar a API (Ctrl+C para parar tudo)...
echo Abre http://localhost:8000 quando a API estiver pronta.
echo.

%PY% -m uvicorn rockforge.interfaces.api.app:app --reload

echo.
echo A parar Redis e o worker...
taskkill /fi "WindowTitle eq RockForge-Redis*" /t /f >nul 2>&1
taskkill /fi "WindowTitle eq RockForge-Worker*" /t /f >nul 2>&1
endlocal
