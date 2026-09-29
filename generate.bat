@echo off
rem Double-click (or run) to convert every new/changed file in input\ to mp3 in output\.
rem Extra arguments are passed through, e.g.  generate.bat --voice bm_george --speed 0.95
cd /d "%~dp0"
".venv\Scripts\python.exe" generate.py %*
pause
