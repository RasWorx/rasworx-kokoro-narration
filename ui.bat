@echo off
rem Double-click to open the Kokoro narration window (no console window stays open).
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" ui.py
