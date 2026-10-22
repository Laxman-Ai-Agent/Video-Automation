@echo off
setlocal
cd /d "%~dp0"

rem Starts the backend (8000) and the UI (5173) through runproject.bat, which also opens the UI in the browser.
call "%~dp0runproject.bat"
