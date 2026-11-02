@echo off
cd /d "%~dp0"
title Phat Hanh Ban Moi (Build & Auto-Release)
cls
echo ========================================================
echo    DONG GOI EXE VA PHAT HANH BAN MOI CHO NGUOI DUNG
echo ========================================================
echo.
set /p ver="Nhap phien ban moi (vi du 1.0.1 hoac an Enter de tu tang): "
set /p note="Nhap ghi chu cap nhat (hoac an Enter): "
echo.
if "%ver%"=="" (
    python release.py
) else (
    python release.py %ver% "%note%"
)
echo.
pause