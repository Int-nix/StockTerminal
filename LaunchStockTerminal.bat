@echo off
set "LAUNCHER=%~dp0StockTerminalLauncher.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%LAUNCHER%"
