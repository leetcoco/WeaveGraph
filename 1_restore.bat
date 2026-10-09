@echo off
echo 正在恢复2293张国画数据...
echo 请确保已激活Python环境（如Anaconda Prompt中运行）
echo 按任意键继续...
pause >nul
python restore_2293.py
echo.
echo 恢复完成！请运行 2_runserver.bat 启动网站。
pause >nul