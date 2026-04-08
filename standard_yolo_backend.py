from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ultralytics import YOLO

from device_utils import DEVICE


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


class StandardYOLOBackend:
    """Runtime wrapper for non-YOLOE models.

    - Torch backend: keep current Ultralytics + `.to(DEVICE)` flow.
    - NCNN backend: load Ultralytics NCNN export directory and skip torch-only device calls.
    """

    def __init__(self, model_path: str, task: str | None = None):
        self.model_path = model_path
        self.task = task
        self.backend = infer_yolo_backend(model_path)
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
            call_kwargs.pop("device", None)
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
