@echo off
rem ContentForge 一键启动控制台（在项目根双击/运行即可）
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY="F:\Anaconda3\envs\contentforge\python.exe"
if not exist %PY% (
  echo [ERROR] 找不到 conda 环境 python: %PY%
  echo 请先运行: conda create -n contentforge python=3.12 -y
  pause
  exit /b 1
)
echo Starting ContentForge console at http://127.0.0.1:8017 ...
%PY% -m uvicorn forge.server.app:app --host 127.0.0.1 --port 8017
pause
