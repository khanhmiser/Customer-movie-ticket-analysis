@echo off
rem Chay bao cao tuan khong can thao tac: nap du lieu moi -> kiem tra chat luong -> bao cao -> gui email.
rem Dung chung cho file bam dup va cho lich tu chay (Task Scheduler). Ket qua ghi vao reports\logs\.
chcp 65001 >nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set LOKY_MAX_CPU_COUNT=4

set "PY=%USERPROFILE%\anaconda3\envs\analyst\python.exe"
if not exist "%PY%" set "PY=python"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set TS=%%i
if not exist "reports\logs" mkdir "reports\logs"
set "LOG=reports\logs\run_%TS%.log"

"%PY%" -m src.pipeline --ingest --send-email > "%LOG%" 2>&1
set CODE=%ERRORLEVEL%
type "%LOG%" | findstr /v /i "warning"
exit /b %CODE%
