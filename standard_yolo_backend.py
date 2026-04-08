from __future__ import annotations

import logging
import os
from pathlib import Path
from functools import lru_cache
from typing import Any

from ultralytics import YOLO

from device_utils import DEVICE


logger = logging.getLogger(__name__)


def _looks_like_ncnn_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    has_param = any(path.glob("*.param"))
    has_bin = any(path.glob("*.bin"))
    return has_param and has_bin


def infer_yolo_backend(model_path: str) -> str:
    forced = os.getenv("AIGLASS_STD_YOLO_BACKEND", "auto").strip().lower()
    path = Path(model_path)
    inferred = (
        "ncnn"
        if model_path.endswith("_ncnn_model") or _looks_like_ncnn_dir(path)
        else "torch"
    )
    if forced in {"torch", "ncnn"}:
        if forced != inferred:
            raise ValueError(
                f"AIGLASS_STD_YOLO_BACKEND={forced} conflicts with model path '{model_path}' "
                f"(auto-detected as {inferred})"
            )
        return forced
    return inferred


def _normalize_gpu_type(value: Any) -> str:
    gpu_type = str(value).split(".")[-1].lower()
    numeric_map = {
        "0": "discrete",
        "1": "integrated",
        "2": "virtual",
        "3": "cpu",
    }
    return numeric_map.get(gpu_type, gpu_type)


def _ncnn_attr(obj: object, name: str, default: Any = None) -> Any:
    value = getattr(obj, name, default)
    return value() if callable(value) else value


def _coerce_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _score_ncnn_gpu(
    info: Any, index: int, default_index: int
) -> tuple[int, int, int, int]:
    gpu_type = _normalize_gpu_type(_ncnn_attr(info, "type", ""))
    type_score = {
        "discrete": 4,
        "integrated": 3,
        "virtual": 2,
        "cpu": 1,
    }.get(gpu_type, 0)
    vendor_id = _coerce_int(_ncnn_attr(info, "vendor_id", 0), default=0)
    # Prefer common high-throughput desktop/server GPU vendors when type ties.
    vendor_score = {
        0x10DE: 3,  # NVIDIA
        0x1002: 2,  # AMD
        0x8086: 1,  # Intel
    }.get(vendor_id, 0)
    default_bonus = 1 if index == default_index else 0
    return (type_score, vendor_score, default_bonus, -index)


@lru_cache(maxsize=1)
def resolve_ncnn_device() -> str:
    requested = os.getenv("AIGLASS_NCNN_DEVICE", "auto").strip().lower()
    if requested in {"cpu", "cpu:0"}:
        return "cpu"
    if requested.startswith("vulkan"):
        return requested if ":" in requested else "vulkan:0"

    try:
        import ncnn
    except Exception as exc:
        logger.warning(f"[NCNN] 导入 ncnn 失败，回退 CPU: {exc}")
        return "cpu"

    try:
        get_gpu_count = getattr(ncnn, "get_gpu_count", None)
        get_default_gpu_index = getattr(ncnn, "get_default_gpu_index", None)
        get_gpu_info = getattr(ncnn, "get_gpu_info", None)
        if not callable(get_gpu_count):
            logger.info("[NCNN] 当前 ncnn Python 绑定未暴露 GPU 枚举接口，回退 CPU")
            return "cpu"

        gpu_count = _coerce_int(get_gpu_count(), default=0)
        if gpu_count <= 0:
            logger.info("[NCNN] 未检测到 Vulkan GPU，回退 CPU")
            return "cpu"

        default_index = _coerce_int(
            get_default_gpu_index() if callable(get_default_gpu_index) else 0,
            default=0,
        )
        if requested == "auto" and callable(get_gpu_info):
            candidates: list[tuple[tuple[int, int, int, int], int, str]] = []
            for index in range(gpu_count):
                info = get_gpu_info(index)
                score = _score_ncnn_gpu(info, index, default_index)
                name = str(_ncnn_attr(info, "device_name", f"GPU {index}"))
                candidates.append((score, index, name))
            if candidates:
                _, best_index, best_name = max(candidates)
                logger.info(
                    f"[NCNN] 自动选择 Vulkan 设备: {best_name} (index={best_index}, default={default_index})"
                )
                return f"vulkan:{best_index}"

        chosen_index = default_index if 0 <= default_index < gpu_count else 0
        logger.info(f"[NCNN] 使用默认 Vulkan 设备 index={chosen_index}")
        return f"vulkan:{chosen_index}"
    except Exception as exc:
        logger.warning(f"[NCNN] Vulkan 设备探测失败，回退 CPU: {exc}")
        return "cpu"


class StandardYOLOBackend:
    """Runtime wrapper for non-YOLOE models.

    - Torch backend: keep current Ultralytics + `.to(DEVICE)` flow.
    - NCNN backend: load Ultralytics NCNN export directory and skip torch-only device calls.
    """

    def __init__(self, model_path: str, task: str | None = None):
        self.model_path = model_path
        self.task = task
        self.backend = infer_yolo_backend(model_path)
        self.runtime_device = (
            resolve_ncnn_device() if self.backend == "ncnn" else DEVICE
        )
        init_kwargs: dict[str, Any] = {}
        if task:
            init_kwargs["task"] = task
        self.model = YOLO(model_path, **init_kwargs)
        if self.backend == "torch" and hasattr(self.model, "to"):
            self.model.to(DEVICE)

    @property
    def names(self) -> Any:
        return getattr(self.model, "names", {})

    def predict(self, *args: Any, **kwargs: Any):
        call_kwargs = dict(kwargs)
        if self.backend == "ncnn":
            call_kwargs["device"] = self.runtime_device
        else:
            call_kwargs.setdefault("device", DEVICE)
        return self.model.predict(*args, **call_kwargs)

    def __call__(self, *args: Any, **kwargs: Any):
        return self.predict(*args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        return getattr(self.model, item)


def load_standard_yolo_model(
    model_path: str, task: str | None = None
) -> StandardYOLOBackend:
    return StandardYOLOBackend(model_path, task=task)
