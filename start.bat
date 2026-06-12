@echo off
REM Launches RockForge locally (no Docker): Redis, API and Celery worker
REM each in their own window. Requires: pip install -e ".[dev,ml]" and
REM redis-server available on PATH (e.g. Memurai or WSL redis-server).

setlocal
cd /d "%~dp0"

start "RockForge - Redis" cmd /k redis-server
start "RockForge - API" cmd /k uvicorn rockforge.interfaces.api.app:app --reload
start "RockForge - Worker" cmd /k celery -A rockforge.interfaces.worker.celery_app:celery_app worker --pool=solo --loglevel=info

echo RockForge a arrancar em 3 janelas separadas (Redis, API, Worker).
echo Abre http://localhost:8000 quando a API estiver pronta.
endlocal
