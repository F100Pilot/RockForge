@echo off
REM Launches RockForge locally (no Docker) in a single window.
REM Redis and the Celery worker run in the background (logs in .\logs\);
REM the API runs in the foreground here. Ctrl+C stops the API; the
REM background processes are then stopped too.
REM Requires: pip install -e ".[dev,ml]" and a Redis server. On Windows the
REM simplest is Memurai (https://www.memurai.com/) — installed as a service it
REM is auto-detected here; otherwise any 'redis-server' on PATH works.

setlocal enabledelayedexpansion
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

REM --- Redis: reuse a running instance, else launch a found server binary ---
REM Memurai usually installs as a Windows service already listening on 6379;
REM in that case we reuse it and don't start (or later kill) anything.
set "REDIS_RUNNING="
netstat -an | find ":6379" >nul 2>&1
if not errorlevel 1 set "REDIS_RUNNING=1"

set "REDIS_CMD="
if not defined REDIS_RUNNING (
  for %%C in (memurai redis-server memurai-server) do (
    if not defined REDIS_CMD (
      where %%C >nul 2>&1
      if not errorlevel 1 set "REDIS_CMD=%%C"
    )
  )
)

if defined REDIS_RUNNING (
  echo Redis ja esta a correr na porta 6379 - a reutilizar.
) else if defined REDIS_CMD (
  echo A iniciar Redis ^(!REDIS_CMD!^) em segundo plano ^(logs\redis.log^)...
  start "RockForge-Redis" /min cmd /c "!REDIS_CMD! > logs\redis.log 2>&1"
) else (
  echo.
  echo ============================================================
  echo  ERRO: nenhum servidor Redis encontrado.
  echo.
  echo  Instala o Memurai ^(Redis para Windows^):
  echo      https://www.memurai.com/get-memurai
  echo  ou garante que 'redis-server' esta no PATH.
  echo.
  echo  Sem Redis, a detecao de letras e a geracao de CDLC
  echo  ficam presas em "a aguardar o worker".
  echo ============================================================
  echo.
  pause
  endlocal
  exit /b 1
)

echo A iniciar o worker Celery em segundo plano (logs\worker.log)...
start "RockForge-Worker" /min cmd /c "%PY% -m celery -A rockforge.interfaces.worker.celery_app:celery_app worker --pool=solo --loglevel=info > logs\worker.log 2>&1"

echo.
echo Redis e Worker a correr minimizados. A iniciar a API (Ctrl+C para parar tudo)...
echo Abre http://localhost:8000 quando a API estiver pronta.
echo.

%PY% -m uvicorn rockforge.interfaces.api.app:app --reload

echo.
echo A parar Redis e o worker...
REM Only kills the window we started; a reused Memurai service has no such
REM window and is left running.
taskkill /fi "WindowTitle eq RockForge-Redis*" /t /f >nul 2>&1
taskkill /fi "WindowTitle eq RockForge-Worker*" /t /f >nul 2>&1
endlocal
