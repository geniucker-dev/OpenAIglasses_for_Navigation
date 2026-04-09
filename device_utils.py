# device_utils.py
"""
统一的设备选择工具，支持 CUDA > MPS > CPU 自动 fallback

使用方法:
    from device_utils import get_device, DEVICE, IS_CUDA, IS_MPS

    # 获取设备字符串
    device = get_device()  # 返回 "cuda:0", "mps", 或 "cpu"

    # 或直接使用全局变量
    model.to(DEVICE)
"""

import os
import logging
import torch
from threading import Semaphore
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def get_device() -> str:
    """
    自动选择最佳可用设备，优先级：CUDA > MPS > CPU

    环境变量 AIGLASS_DEVICE 可强制指定设备:
        - "cuda" / "cuda:0" / "cuda:1" 等 -> 使用指定 CUDA 设备
        - "mps" -> 使用 MPS (Apple Silicon)
        - "cpu" -> 使用 CPU

    Returns:
        str: 设备字符串 ("cuda:0", "mps", 或 "cpu")
    """
    # 1. 检查环境变量是否强制指定
    env_device = os.getenv("AIGLASS_DEVICE", "").lower()

    if env_device:
        # 用户强制指定设备
        if env_device.startswith("cuda"):
            if torch.cuda.is_available():
                # 解析设备索引
                if ":" in env_device:
                    try:
                        idx = int(env_device.split(":")[1])
                        if idx < torch.cuda.device_count():
                            logger.info(f"[DEVICE] 使用环境变量指定的设备: cuda:{idx}")
                            return f"cuda:{idx}"
                    except ValueError:
                        pass
                logger.info(f"[DEVICE] 使用环境变量指定的设备: cuda:0")
                return "cuda:0"
            else:
                logger.warning(
                    f"[DEVICE] AIGLASS_DEVICE={env_device} 但 CUDA 不可用，尝试 fallback"
                )

        elif env_device == "mps":
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                logger.info(f"[DEVICE] 使用环境变量指定的设备: mps")
                return "mps"
            else:
                logger.warning(
                    f"[DEVICE] AIGLASS_DEVICE=mps 但 MPS 不可用，尝试 fallback"
                )

        elif env_device == "cpu":
            logger.info(f"[DEVICE] 使用环境变量指定的设备: cpu")
            return "cpu"

    # 2. 自动选择：CUDA > MPS > CPU
    if torch.cuda.is_available():
        device = "cuda:0"
        device_name = torch.cuda.get_device_name(0)
        logger.info(f"[DEVICE] 自动选择 CUDA: {device_name}")
        return device

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        if hasattr(torch.backends.mps, "is_built") and torch.backends.mps.is_built():
            logger.info(f"[DEVICE] 自动选择 MPS (Apple Silicon)")
            return "mps"

    logger.info(f"[DEVICE] 自动选择 CPU")
    return "cpu"


def get_device_type(device: str) -> str:
    """
    从设备字符串提取设备类型

    Args:
        device: 设备字符串如 "cuda:0", "mps", "cpu"

    Returns:
        str: "cuda", "mps", 或 "cpu"
    """
    if device.startswith("cuda"):
        return "cuda"
    return device


# ============ 全局设备配置（模块加载时初始化） ============

DEVICE = get_device()
DEVICE_TYPE = get_device_type(DEVICE)
IS_CUDA = DEVICE_TYPE == "cuda"
IS_MPS = DEVICE_TYPE == "mps"
IS_CPU = DEVICE_TYPE == "cpu"

# ROCm (AMD) 也走 "cuda" 设备类型，但 MIOpen 的 autotuning 比 cuDNN 慢几个数量级
# 需要区分 NVIDIA 和 AMD 来决定是否开 benchmark
IS_ROCM = IS_CUDA and hasattr(torch.version, "hip") and torch.version.hip is not None

# AMP (自动混合精度) 配置
AMP_POLICY = os.getenv("AIGLASS_AMP", "auto").lower()


def _get_amp_dtype():
    """根据设备和配置确定 AMP 数据类型"""
    if AMP_POLICY == "off":
        return None

    if IS_CUDA:
        if AMP_POLICY == "bf16" and torch.cuda.is_bf16_supported():
            return torch.bfloat16
        elif AMP_POLICY in ("fp16", "bf16"):
            # bf16 不支持时降级到 fp16
            return torch.float16
        elif AMP_POLICY == "auto":
            # 自动选择
            if torch.cuda.is_bf16_supported():
                return torch.bfloat16
            return torch.float16
    elif IS_MPS:
        # MPS 支持 float16
        if AMP_POLICY in ("fp16", "auto"):
            return torch.float16

    return None


AMP_DTYPE = _get_amp_dtype()

# GPU 并发限流
GPU_SLOTS = int(os.getenv("AIGLASS_GPU_SLOTS", "2"))
gpu_semaphore = Semaphore(GPU_SLOTS)


@contextmanager
def gpu_infer_slot():
    """
    统一管理：GPU 并发限流 + torch.inference_mode() + AMP autocast

    使用方法:
        with gpu_infer_slot():
            results = model.predict(image)
    """
    with gpu_semaphore:
        if AMP_DTYPE is not None:
            with (
                torch.inference_mode(),
                torch.amp.autocast(device_type=DEVICE_TYPE, dtype=AMP_DTYPE),
            ):
                yield
        else:
            with torch.inference_mode():
                yield


def to_device(model):
    """
    将模型移动到最佳设备

    Args:
        model: PyTorch 模型或 Ultralytics 模型

    Returns:
        model: 移动后的模型
    """
    if hasattr(model, "to"):
        model.to(DEVICE)
    return model


def get_amp_context():
    """
    获取适合当前设备的 AMP autocast context

    使用方法:
        with get_amp_context():
            output = model(input)
    """
    if AMP_DTYPE is not None:
        return torch.amp.autocast(device_type=DEVICE_TYPE, dtype=AMP_DTYPE)
    else:
        from contextlib import nullcontext

        return nullcontext()


# ============ 启动时打印设备信息 ============


def print_device_info():
    """打印当前设备配置信息"""
    logger.info("=" * 60)
    logger.info("[DEVICE] 设备配置:")
    logger.info(f"  - 选定设备: {DEVICE}")
    logger.info(f"  - 设备类型: {DEVICE_TYPE}")
    logger.info(f"  - IS_CUDA: {IS_CUDA}")
    logger.info(f"  - IS_MPS: {IS_MPS}")
    logger.info(f"  - IS_CPU: {IS_CPU}")
    logger.info(f"  - AMP 策略: {AMP_POLICY}")
    logger.info(f"  - AMP 数据类型: {AMP_DTYPE}")
    logger.info(f"  - GPU 并发槽位: {GPU_SLOTS}")

    if IS_CUDA:
        logger.info(f"  - CUDA 设备名: {torch.cuda.get_device_name(0)}")
        logger.info(f"  - CUDA 版本: {torch.version.cuda}")
        logger.info(f"  - cuDNN 版本: {torch.backends.cudnn.version()}")
        logger.info(f"  - GPU 数量: {torch.cuda.device_count()}")
    elif IS_MPS:
        logger.info(f"  - MPS 可用: {torch.backends.mps.is_available()}")
        logger.info(f"  - MPS 已构建: {torch.backends.mps.is_built()}")

    logger.info("=" * 60)


# 模块加载时自动打印（如果配置了日志）
if __name__ != "__main__":
    try:
        print_device_info()
    except Exception as e:
        logger.warning(f"[DEVICE] Failed to print device info: {e}")


# ============ cuDNN 优化 ============

try:
    if IS_CUDA and not IS_ROCM:
        torch.backends.cudnn.benchmark = True
except Exception as e:
    logger.debug(f"[DEVICE] cuDNN benchmark setup failed: {e}")


# ============ 命令行测试 ============

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print_device_info()

    # 测试 tensor 操作
    print("\n[TEST] 创建测试张量...")
    x = torch.randn(3, 3)
    x = x.to(DEVICE)
    print(f"[TEST] 张量设备: {x.device}")
    print(f"[TEST] 张量:\n{x}")
