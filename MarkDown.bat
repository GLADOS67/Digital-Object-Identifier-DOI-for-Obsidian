@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

set "current_dir=%~dp0"
set "current_dir=%current_dir:~0,-1%"
python "**path to your repository**\MarkDown.py" --path "%current_dir%"


timeout /t 30
