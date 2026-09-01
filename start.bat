@echo off
title PadDesk
cd /d "%~dp0"
echo PadDesk em http://127.0.0.1:8765
echo Desenvolvido por Victor Emanuel Lobato
echo F12 = liga/desliga mapeamento
echo F11 = para sequencia
echo.

where py >nul 2>&1
if %errorlevel%==0 (
  py -3 app.py
) else (
  python app.py
)
if %errorlevel% neq 0 (
  echo.
  echo Nao foi possivel iniciar. Instale Python 3.10 ou mais novo:
  echo https://www.python.org/downloads/
  echo Na instalacao, marque "Add python.exe to PATH".
)
pause
