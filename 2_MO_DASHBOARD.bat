@echo off
chcp 65001 >nul
title Dashboard bao cao van hanh
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set LOKY_MAX_CPU_COUNT=4
set "PY=%USERPROFILE%\anaconda3\envs\analyst\python.exe"
if not exist "%PY%" set "PY=python"
echo Dang mo dashboard tren trinh duyet (http://localhost:8501)...
echo DE NGUYEN cua so nay trong luc dung. Dong cua so = tat dashboard.
"%PY%" -m streamlit run app\streamlit_app.py --server.port 8501
pause
