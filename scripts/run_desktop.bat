@echo off
setlocal
rem Use UTF-8 for the desktop app and every Python process it starts.
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8:replace"
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "PYTHON=D:\Python312\python.exe"
if not exist "%PYTHON%" (
  echo Khong tim thay Python tai %PYTHON%.
  echo Sua bien PYTHON trong file BAT cho dung duong dan Python 3.12.
  pause
  exit /b 1
)
"%PYTHON%" "%ROOT%\app-desktop\main.py"
if errorlevel 1 pause
endlocal
