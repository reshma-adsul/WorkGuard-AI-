@echo off
title WorkGuard AI v2.0
color 0A
cls
echo.
echo  ╔══════════════════════════════════════╗
echo  ║   WorkGuard AI — Starting...         ║
echo  ║   AI-Powered Security Monitor v2.0   ║
echo  ╚══════════════════════════════════════╝
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Python not found! Install from python.org
    pause
    exit
)

echo  Starting WorkGuard AI...
echo.
python main.py

echo.
echo  Session ended. Check activity_logs folder for your report.
pause
