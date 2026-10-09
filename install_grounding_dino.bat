@echo off
echo ========================================
echo Grounding DINO 安装脚本
echo ========================================
echo.

echo [1/3] 检查Python版本...
python --version
if errorlevel 1 (
    echo 错误: 请先安装Python 3.8+
    pause
    exit /b 1
)

echo.
echo [2/3] 安装Grounding DINO依赖...
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install transformers -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo [3/3] 检查安装...
python -c "import torch; import transformers; print('✓ 安装成功!')"

echo.
echo ========================================
echo 安装完成!
echo.
echo 模型说明:
echo - 模型大小: ~700MB (比Qwen的15GB小20倍!)
echo - 首次使用会自动下载
echo - 支持CPU运行，无需GPU
echo.
echo 接下来:
echo 1. 运行: python manage.py runserver
echo 2. 访问: http://127.0.0.1:8000/artifacts/{slug}/network/
echo 3. 点击"开始分析"按钮
echo ========================================
pause
