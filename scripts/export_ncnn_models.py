# scripts/export_ncnn_models.py
# -*- coding: utf-8 -*-
"""Export local visual models to Ultralytics NCNN and smoke-test Vulkan runtime."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ncnn_runtime import (  # noqa: E402
    assert_ncnn_model_path,
    get_infer_device,
    get_ncnn_imgsz,
    predict_kwargs,
)
from obstacle_detector_client import ObstacleDetectorClient  # noqa: E402


EXPORTS = {
    "blindpath": {
        "src": "model/yolo-seg.pt",
        "dst": "model/yolo-seg_ncnn_model",
        "kind": "yolo",
    },
    "trafficlight": {
        "src": "model/trafficlight.pt",
        "dst": "model/trafficlight_ncnn_model",
        "kind": "yolo",
    },
    "obstacle": {
        "src": "model/yoloe-11l-seg.pt",
        "dst": "model/yoloe-11l-seg_ncnn_model",
        "kind": "yoloe",
    },
}


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _require_source(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"导出源模型不存在: {path}")
    if path.suffix != ".pt":
        raise RuntimeError(f"导出源模型必须是 .pt: {path}")


def _export_yolo(src: Path, half: bool) -> None:
    from ultralytics import YOLO

    model = YOLO(str(src))
    model.export(format="ncnn", imgsz=get_ncnn_imgsz(), half=half)


def _export_yoloe(src: Path, half: bool) -> None:
    from ultralytics import YOLOE

    names = ObstacleDetectorClient.WHITELIST_CLASSES
    model = YOLOE(str(src))
    text_pe = model.get_text_pe(names)
    model.set_classes(names, text_pe)
    model.export(format="ncnn", imgsz=get_ncnn_imgsz(), half=half)


def export_models(names: Iterable[str], half: bool) -> None:
    for name in names:
        config = EXPORTS[name]
        src = _resolve(config["src"])
        _require_source(src)
        print(f"[EXPORT] 开始导出 {name}: {src}")
        if config["kind"] == "yoloe":
            _export_yoloe(src, half=half)
        else:
            _export_yolo(src, half=half)
        dst = _resolve(config["dst"])
        assert_ncnn_model_path(str(dst), f"{name} 导出结果")
        print(f"[EXPORT] 导出完成 {name}: {dst}")


def smoke_test_model(name: str) -> None:
    from ultralytics import YOLO

    config = EXPORTS[name]
    dst = _resolve(config["dst"])
    assert_ncnn_model_path(str(dst), f"{name} NCNN 模型")
    h, w = get_ncnn_imgsz()
    image = np.zeros((h, w, 3), dtype=np.uint8)
    print(f"[SMOKE] 加载 {name}: {dst}")
    model = YOLO(str(dst))
    results = model.predict(image, **predict_kwargs(conf=0.25))
    if not results:
        raise RuntimeError(f"{name} NCNN smoke test 未返回结果")
    result = results[0]
    boxes = getattr(result, "boxes", None)
    masks = getattr(result, "masks", None)
    names_map = getattr(result, "names", getattr(model, "names", None))
    print(
        f"[SMOKE] {name} ok: boxes={boxes is not None}, "
        f"masks={masks is not None}, names={names_map}"
    )
    if name in {"blindpath", "obstacle"} and boxes is not None and len(boxes) > 0 and masks is None:
        raise RuntimeError(f"{name} NCNN 有检测框但输出缺少 masks")
    if name == "obstacle":
        if boxes is not None and len(boxes) > 0 and getattr(boxes, "cls", None) is None:
            raise RuntimeError("obstacle NCNN 有检测框但输出缺少 boxes.cls")
        model_names = names_map if isinstance(names_map, (dict, list)) else {}
        print(f"[SMOKE] obstacle 白名单 fallback 顺序: {ObstacleDetectorClient.WHITELIST_CLASSES}")
        print(f"[SMOKE] obstacle NCNN metadata names: {model_names}")


def smoke_tests(names: Iterable[str]) -> None:
    for name in names:
        smoke_test_model(name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export visual YOLO models to NCNN.")
    parser.add_argument(
        "--model",
        choices=sorted(EXPORTS),
        action="append",
        help="只导出指定模型；可重复传入。默认导出全部。",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="跳过导出，仅运行 NCNN smoke test。",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="跳过 smoke test。",
    )
    parser.add_argument(
        "--half",
        action="store_true",
        default=os.getenv("AIGLASS_NCNN_HALF", "0").lower() in {"1", "true", "yes", "on"},
        help="导出 FP16 NCNN 模型。默认读取 AIGLASS_NCNN_HALF。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    names = args.model or list(EXPORTS.keys())
    print(f"[NCNN] imgsz={get_ncnn_imgsz()}, device={get_infer_device()}, half={args.half}")
    if not args.skip_export:
        export_models(names, half=args.half)
    if not args.skip_smoke:
        smoke_tests(names)
    print("[NCNN] 导出/验证完成")


if __name__ == "__main__":
    main()
