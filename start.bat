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

echo A iniciar Redis em segundo plano (logs\redis.log)...
start "RockForge-Redis" /min cmd /c "redis-server > logs\redis.log 2>&1"

echo A iniciar o worker Celery em segundo plano (logs\worker.log)...
start "RockForge-Worker" /min cmd /c "celery -A rockforge.interfaces.worker.celery_app:celery_app worker --pool=solo --loglevel=info > logs\worker.log 2>&1"

echo.
echo Redis e Worker a correr minimizados. A iniciar a API (Ctrl+C para parar tudo)...
echo Abre http://localhost:8000 quando a API estiver pronta.
echo.

uvicorn rockforge.interfaces.api.app:app --reload

echo.
echo A parar Redis e o worker...
taskkill /fi "WindowTitle eq RockForge-Redis*" /t /f >nul 2>&1
taskkill /fi "WindowTitle eq RockForge-Worker*" /t /f >nul 2>&1
endlocal
