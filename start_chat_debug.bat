@echo off
chcp 65001 >nul
title Flowey LLM 对话调试台
cd /d "%~dp0"
set PY=C:\Users\zxl14\.workbuddy\binaries\python\versions\3.13.12\python.exe
if not exist "%PY%" set PY=python

echo [1/2] 检查密钥连通性...
"%PY%" flowey_chat_debug.py --check
if errorlevel 1 (
    echo.
    echo 密钥不可用，请检查 secrets.local.json
    pause
    exit /b 1
)

echo.
echo [2/2] 进入对话调试（/quit 退出）
"%PY%" flowey_chat_debug.py
pause
