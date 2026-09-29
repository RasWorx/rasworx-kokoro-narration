@echo off
rem Installs Kokoro narration into THIS folder (the folder that holds setup.bat).
rem Creates .venv here, installs the CUDA 12.8 build of torch and requirements.txt,
rem and puts a "Kokoro narration" shortcut on your desktop.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
echo.
pause
