@echo off
:: ======================================================================
:: Coiled Spring Scanner — Windows 24/7 Starter
:: ======================================================================

:: 1. SET YOUR TELEGRAM CREDENTIALS HERE
set TELEGRAM_TOKEN=8697291870:AAGbbtb1_GyjkBoBvXWHNK32ca2agJXlfmY
set TELEGRAM_CHAT_ID=6009639966

:: 2. RUN OPTIONS
title Coiled Spring Scanner
echo Starting Coiled Spring Scanner...

:loop
python coiled_spring_scanner.py
echo.
echo [!] Scanner crashed or stopped. Restarting in 10 seconds...
timeout /t 10
goto loop
