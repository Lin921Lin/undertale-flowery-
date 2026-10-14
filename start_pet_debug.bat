@echo off
rem Flowey desktop pet - debug launcher (keeps console for traceback)
cd /d "%~dp0"
"C:\Users\zxl14\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "%~dp0flowey_pet.py"
echo.
echo [pet exited] press any key to close
pause >nul
