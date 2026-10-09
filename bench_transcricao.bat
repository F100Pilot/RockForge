@echo off
REM Banco de ensaio da transcricao (EXPERIMENTAL, fase 0).
REM Duplo clique: instala o que falta (so na 1a vez), corre nas musicas com
REM pistas marcadas como sincronizadas e abre o relatorio.
REM Na linha de comandos tambem aceita: instalar | list | run ... | score ...
REM So LE os projetos; escreve em <pasta de trabalho>\transcription_bench.
setlocal
cd /d "%~dp0"
set "PY=python"
py -3.11 -c "" >nul 2>&1
if not errorlevel 1 set "PY=py -3.11"
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" if "%PY%"=="python" set PY="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if exist "%ProgramFiles%\Python311\python.exe" if "%PY%"=="python" set PY="%ProgramFiles%\Python311\python.exe"
if /i "%~1"=="instalar" goto instalar
if "%~1"=="" goto tudo
%PY% -m rockforge.experimental.transcription %*
endlocal
exit /b %errorlevel%

:tudo
if not exist logs mkdir logs
if not exist logs\bench.installed (
  echo A instalar os transcritores ^(so desta vez, demora alguns minutos^)...
  call :pip
  if errorlevel 1 (
    echo.
    echo ERRO na instalacao. Copia o texto acima e envia-o.
    pause
    endlocal
    exit /b 1
  )
  echo ok> logs\bench.installed
)
echo.
echo A correr os transcritores nas musicas com pistas marcadas como sincronizadas.
echo Pode demorar varios minutos por musica. Nao feches esta janela.
echo.
%PY% -m rockforge.experimental.transcription run --only-synced --open
echo.
pause
endlocal
exit /b 0

:instalar
call :pip
endlocal
exit /b %errorlevel%

:pip
REM As versoes ficam presas ao que o RockForge usa (torch<2.5, numpy<2): sem
REM isto o pip atualizava o torch e partia o Demucs e o WhisperX.
%PY% -m pip install "hf-midi-transcription @ git+https://github.com/xavriley/hf_midi_transcription" "mt3-infer @ git+https://github.com/openmirlab/mt3-infer.git" "torch<2.5" "torchaudio<2.5" "torchvision<0.20" "numpy<2"
exit /b %errorlevel%
