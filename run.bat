@echo off
cd /d "%~dp0"
title Bot Discord - Bao Gia Cho Queen City
cls
echo ========================================================
echo    BOT DISCORD BAO GIA THI TRUONG QUEEN CITY
echo ========================================================
echo.
if exist "market_bot.exe" (
    echo [*] Dang chay ban EXE doc lap (khong can Python)...
    market_bot.exe
) else (
    echo [*] Dang chay bang Python...
    python -u bot.py
)
echo.
echo [!] Bot da dung lai.
pause