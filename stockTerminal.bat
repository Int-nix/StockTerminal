@echo off
title StockTerminal Launcher

echo ========================================
echo            STOCKTERMINAL
echo ========================================
echo.
echo Starting StockTerminal...
echo.

wsl.exe -d Ubuntu -- bash -c "cd /mnt/c/Users/owena/desktop/stockterminal && /home/owena/.stockterminal-venv/bin/python main.py"

if errorlevel 1 (
    echo.
    echo ========================================
    echo   STOCKTERMINAL FAILED TO LAUNCH
    echo ========================================
    echo.
    pause
)
