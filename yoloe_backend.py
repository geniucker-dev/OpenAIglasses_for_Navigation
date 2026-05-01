# yoloe_backend.py
# -*- coding: utf-8 -*-
"""NCNN-only compatibility backend for legacy traffic-light probing."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import os

import cv2
import numpy as np
from ultralytics import YOLO

from ncnn_runtime import (
    assert_frame_shape,
    assert_ncnn_model_path,
    get_infer_device,
    predict_kwargs,
    tensor_like_scalar,
    tensor_like_to_numpy,
)

DEFAULT_MODEL_PATH = os.getenv("YOLOE_MODEL_PATH", "model/yoloe-11l-seg_ncnn_model")
TRACKER_CFG = os.getenv("YOLO_TRACKER_YAML", "bytetrack.yaml")


class YoloEBackend:
    def __init__(
        self, model_path: Optional[str] = None, device: Optional[Union[str, int]] = None
    ):
        if device is not None and str(device) != get_infer_device():
            raise RuntimeError("视觉运行时只允许使用 AIGLASS_NCNN_DEVICE 配置的 NCNN/Vulkan 设备")
        self.model_path = str(assert_ncnn_model_path(model_path or DEFAULT_MODEL_PATH, "YOLOE NCNN 后端"))
        self.model = YOLO(self.model_path)

    def set_text_classes(self, names: List[str]):
        raise RuntimeError("运行时不再支持 YOLOE 文本提示词；请在导出 NCNN 前固化类别")

    def segment(
        self,
        frame_bgr: np.ndarray,
        conf: float = 0.20,
        iou: float = 0.45,
        imgsz: Optional[int] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        assert_frame_shape(frame_bgr, "yoloe_backend frame")
        try:
            results = self.model.track(
                frame_bgr,
                **predict_kwargs(conf=conf, iou=iou, persist=persist, tracker=TRACKER_CFG),
            )
        except Exception:
            results = self.model.predict(frame_bgr, **predict_kwargs(conf=conf, iou=iou))
        r = results[0]

        out = {"masks": [], "boxes": [], "cls_ids": [], "names": [], "ids": []}
        masks_obj = getattr(r, "masks", None)
        boxes_obj = getattr(r, "boxes", None)

        if masks_obj is None or getattr(masks_obj, "data", None) is None:
            return out

        mask_arr = tensor_like_to_numpy(masks_obj.data)
        height, width = frame_bgr.shape[:2]
        id2name = r.names if hasattr(r, "names") else getattr(self.model, "names", {})
        num_masks = mask_arr.shape[0]

        if boxes_obj is not None:
            xyxy = tensor_like_to_numpy(boxes_obj.xyxy) if getattr(boxes_obj, "xyxy", None) is not None else [None] * num_masks
            cls = tensor_like_to_numpy(boxes_obj.cls) if getattr(boxes_obj, "cls", None) is not None else [0] * num_masks
            tids = (
                tensor_like_to_numpy(boxes_obj.id).astype(int).tolist()
                if getattr(boxes_obj, "id", None) is not None
                else [None] * num_masks
            )
        else:
            xyxy = [None] * num_masks
            cls = [0] * num_masks
            tids = [None] * num_masks

        for i in range(num_masks):
            bin_mask = (mask_arr[i] > 0.5).astype(np.uint8)
            if bin_mask.shape[:2] != (height, width):
                bin_mask = cv2.resize(bin_mask, (width, height), interpolation=cv2.INTER_NEAREST)
            out["masks"].append(bin_mask)
            out["boxes"].append(tuple(xyxy[i]) if xyxy[i] is not None else None)
            cid = int(cls[i]) if cls is not None else 0
            out["cls_ids"].append(cid)
            if isinstance(id2name, dict):
                out["names"].append(id2name.get(cid, str(cid)))
            elif isinstance(id2name, list) and 0 <= cid < len(id2name):
                out["names"].append(id2name[cid])
            else:
                out["names"].append(str(cid))
            out["ids"].append(int(tids[i]) if tids[i] is not None else None)
        return out


def _default_backend() -> YoloEBackend:
    global _BACKEND
    try:
        return _BACKEND
    except NameError:
        _BACKEND = YoloEBackend()
        return _BACKEND


def infer_image(frame_bgr: np.ndarray) -> List[Dict[str, Any]]:
    result = _default_backend().segment(frame_bgr)
    detections: List[Dict[str, Any]] = []
    for box, cls_id, name in zip(result["boxes"], result["cls_ids"], result["names"]):
        if box is None:
            continue
        detections.append({"label": name, "name": name, "bbox": list(box), "cls": cls_id})
    return detections


def detect(frame_bgr: np.ndarray, target_classes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    target_set = {item.lower() for item in target_classes or []}
    detections = infer_image(frame_bgr)
    if target_set:
        detections = [
            item
            for item in detections
            if str(item.get("name", item.get("label", ""))).lower() in target_set
        ]
    for item in detections:
        if "bbox" in item:
            item["box"] = item["bbox"]
    return detections
