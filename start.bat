@echo off
REM Launches RockForge locally (no Docker) in a single window.
REM Steps: git pull, install/update the dependencies when pyproject.toml changed,
REM Redis + the Celery worker in the background (logs in .\logs\), the API in
REM the foreground here, and the page opened in Chrome. Ctrl+C (or closing the
REM tab) stops the API; the background processes are then stopped too.
REM Requires: Python 3.11 and a Redis server. On Windows the simplest is
REM Memurai (https://www.memurai.com/) — installed as a service it is
REM auto-detected here; otherwise any 'redis-server' on PATH works.

setlocal enabledelayedexpansion
cd /d "%~dp0"
if not exist logs mkdir logs
set "PORT=8000"

if /i "%~1"=="--atualizado" goto :prepare
echo A atualizar o codigo (git pull)...
where git >nul 2>&1
if errorlevel 1 (
  echo AVISO: git nao encontrado. Vai ser usada a versao local.
  goto :prepare
)
git pull --ff-only
if errorlevel 1 (
  echo AVISO: git pull falhou. Vai ser usada a versao local.
  goto :prepare
)
REM cmd reads this file while running it: restart with the version just pulled.
call "%~f0" --atualizado
exit /b

:prepare

REM Use the project's virtualenv when present (children inherit the PATH).
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat

REM The ML stack requires Python 3.11 (tensorflow wheel ceiling). Prefer an
REM explicit 3.11 via the py launcher when the default python is another
REM version (no virtualenv needed).
set "PY=python"
py -3.11 -c "" >nul 2>&1
if not errorlevel 1 set "PY=py -3.11"
REM No py launcher (or it does not list 3.11): try where python.org and winget
REM put a 3.11, per user and for all users.
set "PY311="
if exist "%ProgramFiles%\Python311\python.exe" set "PY311=%ProgramFiles%\Python311\python.exe"
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY311=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if "%PY%"=="python" if defined PY311 set PY="%PY311%"
%PY% --version >nul 2>&1
if errorlevel 1 (
  echo ERRO: Python nao encontrado. Instala o Python 3.11 ^(python.org^).
  pause
  endlocal
  exit /b 1
)
REM Without the py launcher's 3.11 the default python may be 3.12/3.13, which
REM pip refuses with a bare "requires a different Python": say what to do.
%PY% -c "import sys; sys.exit(sys.version_info[:2] != (3, 11))" >nul 2>&1
if errorlevel 1 (
  echo ERRO: o RockForge precisa do Python 3.11, e o Python encontrado e outro:
  %PY% --version
  echo Instala o Python 3.11 ^(pode ficar ao lado do que ja tens^):
  echo     winget install Python.Python.3.11
  echo ou descarrega-o de python.org. Depois fecha esta janela e corre o start.bat de novo.
  pause
  endlocal
  exit /b 1
)

REM --- Dependencies: only when pyproject.toml changed since the last install ---
REM (a full check of the ML stack takes a while; a copy of the installed
REM pyproject.toml in logs\ says whether anything changed).
fc /b pyproject.toml logs\pyproject.installed >nul 2>&1
if errorlevel 1 (
  echo A instalar/atualizar as dependencias ^(pode demorar na primeira vez^)...
  %PY% -m pip install --disable-pip-version-check --no-warn-script-location -q -e ".[ml,lyrics,psarc,youtube]"
  if errorlevel 1 (
    echo ERRO: nao foi possivel instalar as dependencias - ve as mensagens acima.
    pause
    endlocal
    exit /b 1
  )
  copy /y pyproject.toml logs\pyproject.installed >nul
)

netstat -an | find ":%PORT% " | find "LISTENING" >nul
if not errorlevel 1 (
  echo ERRO: a porta %PORT% ja esta em uso - o RockForge ja esta a correr noutra janela?
  pause
  endlocal
  exit /b 1
)

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
echo Redis e Worker a correr minimizados. A iniciar a API...
echo O browser abre automaticamente; fechar o separador para tudo (apos alguns segundos).
echo.

REM Open the page once the API is accepting connections: polls the port (up to
REM ~30s) in the background, hidden, and exits on its own. In Chrome when it is
REM installed (as the PDF-to-GP5 launcher does), else the default browser.
set "BROWSER="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "BROWSER=%LocalAppData%\Google\Chrome\Application\chrome.exe"
set "OPEN=Start-Process 'http://localhost:%PORT%'"
if defined BROWSER set "OPEN=Start-Process '!BROWSER!' 'http://localhost:%PORT%'"
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 60;$i++){try{(New-Object Net.Sockets.TcpClient('localhost',%PORT%)).Close();!OPEN!;break}catch{Start-Sleep -Milliseconds 500}}"

REM The web UI pings /heartbeat while its tab is open; once those pings stop
REM (tab closed) for this many seconds the API exits, and the cleanup below
REM (worker/Redis) then runs too. Set only here — disabled by default
REM (e.g. docker-compose), where closing one user's tab must not affect others.
set "ROCKFORGE_IDLE_SHUTDOWN_S=15"

REM No --reload: this is the user-facing launcher, and --reload's parent/child
REM reloader would fight the idle-shutdown SIGTERM (the tab-close auto-stop).
REM A single uvicorn process exits cleanly, so the cleanup below always runs.
%PY% -m uvicorn rockforge.interfaces.api.app:app --port %PORT%

echo.
echo A parar Redis e o worker...
REM Primary: kill the windows we launched (and their process trees, so the
REM worker's ML subprocesses go too). A reused Memurai service has no such
REM window and is left running.
taskkill /fi "WindowTitle eq RockForge-Redis*" /t /f >nul 2>&1
taskkill /fi "WindowTitle eq RockForge-Worker*" /t /f >nul 2>&1
REM Fallback: if the window title didn't match (some Windows setups), kill the
REM Celery worker by its command line so it never lingers after the tab closes.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*rockforge.interfaces.worker.celery_app*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
endlocal
