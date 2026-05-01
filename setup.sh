#!/bin/bash
# AI Glass System - Linux/macOS 快速安装脚本 (uv版)

set -e  # 遇到错误立即退出

echo "=========================================="
echo "  AI Glass System - 自动安装脚本 (uv)"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 uv 是否安装
echo "正在检查 uv..."
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}uv 未安装，正在安装...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo -e "${GREEN}✓ uv 已安装${NC}"
else
    echo -e "${GREEN}✓ uv 已安装${NC}"
fi

# 检查 uv 版本
UV_VERSION=$(uv --version)
echo -e "${GREEN}  版本: $UV_VERSION${NC}"

# 检查 CUDA（可选）
echo ""
echo "正在检查 GPU..."
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}✓ 检测到 NVIDIA GPU${NC}"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${GREEN}✓ macOS 平台，将使用 MPS 加速${NC}"
else
    echo -e "${YELLOW}! 未检测到 NVIDIA GPU，将使用 CPU 模式（速度较慢）${NC}"
fi

# 安装系统依赖（Linux）
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo ""
    echo "正在检查系统依赖..."
    
    # 检测发行版
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    else
        OS="unknown"
    fi
    
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        echo "检测到 Ubuntu/Debian 系统"
        echo "可能需要 sudo 权限来安装系统依赖..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq portaudio19-dev libgl1-mesa-glx libglib2.0-0
        echo -e "${GREEN}✓ 系统依赖已安装${NC}"
    else
        echo -e "${YELLOW}! 未知的 Linux 发行版，请手动安装依赖${NC}"
        echo "  需要: portaudio19-dev, libgl1-mesa-glx, libglib2.0-0"
    fi
fi

# macOS 系统依赖
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo ""
    echo "正在检查 macOS 系统依赖..."
    if ! command -v brew &> /dev/null; then
        echo -e "${YELLOW}! Homebrew 未安装，跳过系统依赖检查${NC}"
    else
        if ! brew list portaudio &> /dev/null; then
            echo "正在安装 portaudio..."
            brew install portaudio
            echo -e "${GREEN}✓ portaudio 已安装${NC}"
        else
            echo -e "${GREEN}✓ portaudio 已安装${NC}"
        fi
    fi
fi

# 安装 Python 依赖
echo ""
echo "正在安装 Python 依赖..."
uv sync
echo -e "${GREEN}✓ Python 依赖已安装${NC}"

# 创建 .env 文件
echo ""
if [ ! -f ".env" ]; then
    echo "正在创建 .env 配置文件..."
    touch .env
    echo "# DASHSCOPE_API_KEY=your_api_key_here" >> .env
    echo -e "${GREEN}✓ .env 文件已创建${NC}"
    echo -e "${YELLOW}请编辑 .env 文件，填入您的 DASHSCOPE_API_KEY${NC}"
else
    echo -e "${YELLOW}.env 文件已存在，跳过${NC}"
fi

# 创建必要的目录
echo ""
echo "正在创建目录结构..."
mkdir -p recordings model music voice
echo -e "${GREEN}✓ 目录结构已创建${NC}"

# 检查模型文件
echo ""
echo "正在检查模型文件..."
MODELS=("yolo-seg.pt" "yoloe-11l-seg.pt" "trafficlight.pt")
NCNN_MODELS=("yolo-seg_ncnn_model" "yoloe-11l-seg_ncnn_model" "trafficlight_ncnn_model")
MISSING_MODELS=()
MISSING_NCNN=()

for model in "${MODELS[@]}"; do
    if [ -f "model/$model" ]; then
        echo -e "${GREEN}✓ $model${NC}"
    else
        echo -e "${RED}✗ $model (缺失，导出 NCNN 需要)${NC}"
        MISSING_MODELS+=("$model")
    fi
done

for model_dir in "${NCNN_MODELS[@]}"; do
    if [ -d "model/$model_dir" ]; then
        echo -e "${GREEN}✓ $model_dir${NC}"
    else
        echo -e "${RED}✗ $model_dir (缺失，运行时必需)${NC}"
        MISSING_NCNN+=("$model_dir")
    fi
done

if [ ${#MISSING_MODELS[@]} -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}警告: 缺少以下 .pt 源模型文件:${NC}"
    for model in "${MISSING_MODELS[@]}"; do
        echo "  - $model"
    done
    echo "请从以下地址下载并放入 model/ 目录:"
    echo "  https://www.modelscope.cn/models/archifancy/AIGlasses_for_navigation"
fi

if [ ${#MISSING_NCNN[@]} -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}警告: 缺少运行时 NCNN 模型目录:${NC}"
    for model_dir in "${MISSING_NCNN[@]}"; do
        echo "  - $model_dir"
    done
    echo "下载 .pt 后执行: uv run python scripts/export_ncnn_models.py"
fi

# 完成
echo ""
echo "=========================================="
echo -e "${GREEN}安装完成!${NC}"
echo "=========================================="
echo ""
echo "下一步:"
echo "1. 编辑 .env 文件，填入您的 API 密钥:"
echo "   nano .env"
echo ""
echo "2. 确保 .pt 源模型已放入 model/ 目录，并导出 NCNN 模型:"
echo "   uv run python scripts/export_ncnn_models.py"
echo ""
echo "3. 启动系统:"
echo "   uv run python app_main.py"
echo ""
echo "4. 访问 http://localhost:8081"
echo ""
