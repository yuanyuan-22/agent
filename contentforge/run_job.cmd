@echo off
rem 用法: run_job.cmd <BVID 或链接>
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY="F:\Anaconda3\envs\contentforge\python.exe"
%PY% -m scripts.run_job --bvid %1
pause
