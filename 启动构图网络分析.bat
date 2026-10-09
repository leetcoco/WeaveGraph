@echo off
chcp 65001 >nul
echo ========================================
echo    基于复杂网络的中国山水画构图分析
echo ========================================
echo.

echo [1/3] 检查Django服务器状态...
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo ✓ Django服务器已在运行
) else (
    echo ✗ Django服务器未运行，正在启动...
    start /B python manage.py runserver 0.0.0.0:8000
    timeout /t 3 /nobreak >nul
    echo ✓ Django服务器已启动
)

echo.
echo [2/3] 打开浏览器...
start http://127.0.0.1:8000/network-analysis/

echo.
echo [3/3] 系统已就绪！
echo.
echo ========================================
echo 功能说明：
echo - 构图中心性分析（度、介数、紧密、特征向量）
echo - 视觉流路径分析
echo - 色彩社群检测
echo - 构图稳定性评价（0-100分）
echo ========================================
echo.
echo 访问地址：
echo - 文物列表：http://127.0.0.1:8000/network-analysis/
echo - 首页：http://127.0.0.1:8000/
echo.
echo 按任意键关闭此窗口（服务器将继续运行）...
pause >nul
