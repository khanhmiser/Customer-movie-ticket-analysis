@echo off
chcp 65001 >nul
title Bao cao van hanh tuan
echo ============================================================
echo   BAO CAO VAN HANH TUAN - dang chay, vui long doi 1-2 phut...
echo ============================================================
call "%~dp0scripts\chay_tu_dong.bat"
if errorlevel 1 (
    echo.
    echo [LOI] Du lieu moi KHONG dat kiem tra chat luong - CHUA tao bao cao.
    echo       File loi da duoc chuyen vao thu muc data\quarantine.
    echo       Hay gui file nay cho bo phan du lieu kiem tra lai.
    start "" "%~dp0data\quarantine"
    pause
    exit /b 1
)
echo.
echo [XONG] Da tao bao cao. Dang mo file Excel moi nhat...
echo        Email cho tung phong ban: da gui (neu da cau hinh) hoac luu ban xem truoc trong thu muc outbox.
start "" "%~dp0reports\BAO_CAO_MOI_NHAT.xlsx"
pause
