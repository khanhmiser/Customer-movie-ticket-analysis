@echo off
chcp 65001 >nul
title Dat lich chay bao cao tu dong
echo Tao lich: may tinh nay se TU CHAY bao cao luc 08:00 sang thu Hai hang tuan
echo (nap du lieu moi, kiem tra chat luong, tao Excel, gui email cho tung phong ban).
echo.
choice /m "Tiep tuc"
if errorlevel 2 exit /b 0
schtasks /Create /F /SC WEEKLY /D MON /ST 08:00 /TN "BaoCaoVanHanhTuan" /TR "\"%~dp0scripts\chay_tu_dong.bat\""
echo.
echo Xong. Kiem tra trong Task Scheduler, muc "BaoCaoVanHanhTuan".
echo Muon huy lich: schtasks /Delete /TN "BaoCaoVanHanhTuan" /F
pause
