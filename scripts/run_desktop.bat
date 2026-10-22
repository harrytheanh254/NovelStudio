@echo off
setlocal
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
