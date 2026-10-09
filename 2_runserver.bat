@echo off
echo 启动ColorNetVis网站...
echo 请确保已激活Python环境（如Anaconda Prompt中运行）
echo 按任意键继续...
pause >nul
python manage.py runserver
pause >nul