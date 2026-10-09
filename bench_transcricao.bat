@echo off
REM Banco de ensaio da transcricao (EXPERIMENTAL, fase 0).
REM   bench_transcricao.bat instalar      instala os transcritores a testar
REM   bench_transcricao.bat list          projetos que servem de resposta certa
REM   bench_transcricao.bat run           corre e mede (gaps + yourmt3 no estema)
REM   bench_transcricao.bat score FICHEIRO --project ID
REM So LE os projetos; escreve em <pasta de trabalho>\transcription_bench.
setlocal
cd /d "%~dp0"
set "PY=python"
py -3.11 -c "" >nul 2>&1
if not errorlevel 1 set "PY=py -3.11"
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" if "%PY%"=="python" set PY="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if exist "%ProgramFiles%\Python311\python.exe" if "%PY%"=="python" set PY="%ProgramFiles%\Python311\python.exe"
if /i "%~1"=="instalar" goto instalar
%PY% -m rockforge.experimental.transcription %*
endlocal
exit /b %errorlevel%

:instalar
REM As versoes ficam presas ao que o RockForge usa (torch<2.5, numpy<2): sem
REM isto o pip atualizava o torch e partia o Demucs e o WhisperX.
%PY% -m pip install "hf-midi-transcription @ git+https://github.com/xavriley/hf_midi_transcription" "mt3-infer @ git+https://github.com/openmirlab/mt3-infer.git" "torch<2.5" "torchaudio<2.5" "torchvision<0.20" "numpy<2"
endlocal
exit /b %errorlevel%
