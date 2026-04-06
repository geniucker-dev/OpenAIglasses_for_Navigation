@echo off
REM AI Glass System - Windows 快速安装脚本 (uv版)

echo ==========================================
echo   AI Glass System - 自动安装脚本 (uv)
echo ==========================================
echo.

REM 检查 uv
echo 正在检查 uv...
uv --version >nul 2>&1
if errorlevel 1 (
    echo [警告] uv 未安装，正在安装...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo [成功] uv 已安装
) else (
    echo [成功] uv 已安装
    uv --version
)

REM 检查 CUDA
echo.
echo 正在检查 GPU...
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo [警告] 未检测到 NVIDIA GPU，将使用 CPU 模式
) else (
    echo [成功] 检测到 NVIDIA GPU
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
)

REM 安装 Python 依赖
echo.
echo 正在安装 Python 依赖...
uv sync
echo [成功] Python 依赖已安装

REM 创建 .env 文件
echo.
if not exist .env (
    echo 正在创建 .env 配置文件...
    type nul > .env
    echo REM DASHSCOPE_API_KEY=your_api_key_here >> .env
    echo [成功] .env 文件已创建
    echo [提示] 请编辑 .env 文件，填入您的 DASHSCOPE_API_KEY
) else (
    echo [跳过] .env 文件已存在
)

REM 创建必要的目录
echo.
echo 正在创建目录结构...
if not exist recordings mkdir recordings
if not exist model mkdir model
if not exist music mkdir music
if not exist voice mkdir voice
echo [成功] 目录结构已创建

REM 检查模型文件
echo.
echo 正在检查模型文件...
set MISSING=0
if exist model\yolo-seg.pt (echo [成功] yolo-seg.pt) else (echo [缺失] yolo-seg.pt & set MISSING=1)
if exist model\yoloe-11l-seg.pt (echo [成功] yoloe-11l-seg.pt) else (echo [缺失] yoloe-11l-seg.pt & set MISSING=1)
if exist model\shoppingbest5.pt (echo [成功] shoppingbest5.pt) else (echo [缺失] shoppingbest5.pt & set MISSING=1)
if exist model\trafficlight.pt (echo [成功] trafficlight.pt) else (echo [缺失] trafficlight.pt & set MISSING=1)
if exist model\hand_landmarker.task (echo [成功] hand_landmarker.task) else (echo [缺失] hand_landmarker.task & set MISSING=1)

if %MISSING%==1 (
    echo.
    echo [警告] 部分模型文件缺失
    echo 请从以下地址下载并放入 model\ 目录:
    echo https://www.modelscope.cn/models/archifancy/AIGlasses_for_navigation
)

REM 完成
echo.
echo ==========================================
echo [成功] 安装完成!
echo ==========================================
echo.
echo 下一步:
echo 1. 编辑 .env 文件，填入您的 API 密钥:
echo    notepad .env
echo.
echo 2. 确保所有模型文件已放入 model\ 目录
echo.
echo 3. 启动系统:
echo    uv run python app_main.py
echo.
echo 4. 访问 http://localhost:8081
echo.

pause
