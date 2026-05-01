# ncnn_runtime.py
# -*- coding: utf-8 -*-
"""NCNN/Vulkan runtime helpers for visual inference.

视觉推理运行时只允许使用 Ultralytics NCNN 导出目录，不做 PyTorch fallback。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Tuple

import numpy as np

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


def _get_default_ncnn_device() -> str:
    explicit = os.getenv("AIGLASS_NCNN_DEVICE")
    if explicit:
        return explicit

    try:
        import ncnn

        ncnn.create_gpu_instance()
        try:
            index = int(ncnn.get_default_gpu_index())
        finally:
            ncnn.destroy_gpu_instance()
        if index >= 0:
            return f"vulkan:{index}"
    except Exception:
        pass

    return "vulkan:0"


NCNN_DEVICE = _get_default_ncnn_device()
INFER_BACKEND = os.getenv("AIGLASS_INFER_BACKEND", "ncnn").lower()
if INFER_BACKEND != "ncnn":
    raise RuntimeError(f"视觉推理运行时只支持 AIGLASS_INFER_BACKEND=ncnn，当前: {INFER_BACKEND}")

CAMERA_WIDTH = int(os.getenv("AIGLASS_CAMERA_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("AIGLASS_CAMERA_HEIGHT", "480"))
REQUIRE_NCNN = os.getenv("AIGLASS_REQUIRE_NCNN", "1").lower() not in {"0", "false", "no", "off"}


def get_infer_device() -> str:
    return NCNN_DEVICE


def parse_ncnn_imgsz(value: str | None = None) -> Tuple[int, int]:
    raw = (value or os.getenv("AIGLASS_NCNN_IMGSZ", "480,640")).strip().lower()
    if not raw:
        return CAMERA_HEIGHT, CAMERA_WIDTH

    for sep in (",", "x", " "):
        if sep in raw:
            parts = [p for p in raw.replace("x", sep).replace(",", sep).split(sep) if p]
            if len(parts) == 2:
                h, w = int(parts[0]), int(parts[1])
                if h <= 0 or w <= 0:
                    raise ValueError(f"AIGLASS_NCNN_IMGSZ 必须为正数，当前: {raw}")
                return h, w

    single = int(raw)
    if single <= 0:
        raise ValueError(f"AIGLASS_NCNN_IMGSZ 必须为正数，当前: {raw}")
    return single, single


NCNN_IMGSZ = parse_ncnn_imgsz()


def get_ncnn_imgsz() -> Tuple[int, int]:
    return NCNN_IMGSZ


def get_expected_frame_hw() -> Tuple[int, int]:
    return CAMERA_HEIGHT, CAMERA_WIDTH


def assert_runtime_shape_config() -> None:
    expected_hw = get_expected_frame_hw()
    if NCNN_IMGSZ != expected_hw:
        raise RuntimeError(
            f"NCNN imgsz={NCNN_IMGSZ} 与相机帧尺寸 {expected_hw} 不一致。"
            "本项目要求后端不 resize，相机尺寸变化时请同步设置 AIGLASS_NCNN_IMGSZ 并重新导出 NCNN 模型。"
        )


assert_runtime_shape_config()


def assert_ncnn_model_path(path: str, label: str) -> Path:
    model_path = Path(path)
    normalized = str(model_path).rstrip("/")
    if normalized.endswith(".pt"):
        raise RuntimeError(f"{label} 必须使用 NCNN 模型目录，不能使用 .pt: {path}")
    if not model_path.name.endswith("_ncnn_model"):
        raise RuntimeError(f"{label} 必须使用 *_ncnn_model 目录，当前路径: {path}")
    if not model_path.is_dir():
        raise RuntimeError(f"{label} NCNN 模型目录不存在: {path}")

    required_files = ("model.ncnn.param", "model.ncnn.bin")
    missing = [name for name in required_files if not (model_path / name).exists()]
    if missing:
        raise RuntimeError(f"{label} NCNN 模型目录缺少文件 {missing}: {path}")
    return model_path


def assert_frame_shape(frame: np.ndarray, label: str = "camera frame") -> None:
    if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 2:
        raise RuntimeError(f"{label} 无效，无法读取图像尺寸")
    expected_h, expected_w = get_expected_frame_hw()
    actual_h, actual_w = frame.shape[:2]
    if (actual_h, actual_w) != (expected_h, expected_w):
        raise RuntimeError(
            f"{label} 尺寸为 {(actual_h, actual_w)}，但 NCNN 运行配置期望 "
            f"{(expected_h, expected_w)}。请保持 ESP32 帧尺寸一致，或按新尺寸重新导出 NCNN 模型。"
        )


def predict_kwargs(**extra: Any) -> dict[str, Any]:
    kwargs = {
        "device": get_infer_device(),
        "imgsz": get_ncnn_imgsz(),
        "verbose": False,
    }
    kwargs.update(extra)
    return kwargs


def tensor_like_to_numpy(value: Any) -> np.ndarray:
    """Convert Ultralytics tensor/array outputs to numpy without importing torch."""
    obj = value
    if hasattr(obj, "detach"):
        obj = obj.detach()
    if hasattr(obj, "float") and str(getattr(obj, "dtype", "")).lower() in {
        "torch.bfloat16",
        "torch.float16",
        "bfloat16",
        "float16",
    }:
        obj = obj.float()
    if hasattr(obj, "cpu"):
        obj = obj.cpu()
    if hasattr(obj, "numpy"):
        return obj.numpy()
    return np.asarray(obj)


def tensor_like_scalar(value: Any) -> float:
    obj = value
    if hasattr(obj, "item"):
        return float(obj.item())
    arr = tensor_like_to_numpy(obj)
    return float(arr.reshape(-1)[0])
