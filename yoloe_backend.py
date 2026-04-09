# yoloe_backend.py
from typing import List, Dict, Any, Optional, Union
import os
import cv2
import numpy as np
import numpy.typing as npt

from device_utils import DEVICE
from standard_yolo_backend import infer_yolo_backend, load_standard_yolo_model

try:
    from ultralytics import YOLOE as _MODEL
except Exception:
    from ultralytics import YOLO as _MODEL

DEFAULT_MODEL_PATH = os.getenv("YOLOE_MODEL_PATH", "model/yoloe-11l-seg.pt")
TRACKER_CFG = os.getenv("YOLO_TRACKER_YAML", "bytetrack.yaml")


def _to_numpy(value: Any) -> Optional[npt.NDArray[np.generic]]:
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        return value
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        return value.numpy()
    return np.asarray(value)


def _normalize_name(value: str) -> str:
    return str(value).strip().lower()


class YoloEBackend:
    def __init__(
        self, model_path: Optional[str] = None, device: Optional[Union[str, int]] = None
    ):
        self.device = str(device if device else DEVICE)
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.backend = infer_yolo_backend(self.model_path)
        self.requested_names: List[str] = []
        self.allowed_class_ids: Optional[set[int]] = None
        self.prompt_filter_supported = True
        self._prompt_warning_emitted = False

        if self.backend == "ncnn":
            self.model = load_standard_yolo_model(self.model_path, task="segment")
        else:
            self.model = _MODEL(self.model_path)
            self.model.to(self.device)

    def set_text_classes(self, names: List[str]):
        self.requested_names = list(names)
        requested_normalized = {_normalize_name(name) for name in names}

        if self.backend == "ncnn":
            names_map = getattr(self.model, "names", {}) or {}
            allowed_ids = {
                int(class_id)
                for class_id, class_name in names_map.items()
                if _normalize_name(str(class_name)) in requested_normalized
            }
            self.allowed_class_ids = allowed_ids if allowed_ids else set()
            self.prompt_filter_supported = bool(allowed_ids)
            return

        orig_device = None
        if self.device == "mps":
            orig_device = getattr(self.model, "device", self.device)
            self.model.to("cpu")
        try:
            get_text_pe = getattr(self.model, "get_text_pe", None)
            set_classes = getattr(self.model, "set_classes", None)
            if not callable(get_text_pe) or not callable(set_classes):
                raise RuntimeError("当前 YOLOE 模型不支持运行时文本提示词")
            text_pe = get_text_pe(names)
            set_classes(names, text_pe)
        finally:
            if orig_device is not None:
                self.model.to(orig_device)

    def segment(
        self,
        frame_bgr: npt.NDArray[np.uint8],
        conf: float = 0.20,
        iou: float = 0.45,
        imgsz: int = 640,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        返回:
          dict{
            'masks': List[np.uint8(H,W)],      # 0/1 mask
            'boxes': List[Tuple[x1,y1,x2,y2]],
            'cls_ids': List[int],
            'names': List[str],
            'ids': List[Optional[int]]
          }
        """
        if self.backend == "ncnn":
            results = self.model.predict(
                frame_bgr,
                conf=conf,
                iou=iou,
                imgsz=imgsz,
                verbose=False,
            )
        else:
            results = self.model.track(
                frame_bgr,
                conf=conf,
                iou=iou,
                imgsz=imgsz,
                persist=persist,
                tracker=TRACKER_CFG,
                verbose=False,
            )

        r = results[0]

        out = {"masks": [], "boxes": [], "cls_ids": [], "names": [], "ids": []}
        masks_obj = getattr(r, "masks", None)
        boxes_obj = getattr(r, "boxes", None)

        if masks_obj is None or getattr(masks_obj, "data", None) is None:
            return out

        mask_arr = _to_numpy(masks_obj.data)
        if mask_arr is None:
            return out
        H, W = frame_bgr.shape[:2]
        id2name = r.names if hasattr(r, "names") else {}
        N = mask_arr.shape[0]

        if boxes_obj is not None:
            xyxy_arr = _to_numpy(getattr(boxes_obj, "xyxy", None))
            xyxy = xyxy_arr.tolist() if xyxy_arr is not None else [None] * N
            cls_arr = _to_numpy(getattr(boxes_obj, "cls", None))
            cls = cls_arr.tolist() if cls_arr is not None else [0] * N
            ids_arr = _to_numpy(getattr(boxes_obj, "id", None))
            tids = (
                ids_arr.astype(np.int32).tolist() if ids_arr is not None else [None] * N
            )
        else:
            xyxy = [None] * N
            cls = [0] * N
            tids = [None] * N

        for i in range(N):
            cid = int(cls[i]) if cls is not None else 0
            if self.allowed_class_ids is not None and cid not in self.allowed_class_ids:
                continue

            bin_mask = (mask_arr[i] > 0.5).astype(np.uint8)
            if bin_mask.shape[:2] != (H, W):
                bin_mask = cv2.resize(bin_mask, (W, H), interpolation=cv2.INTER_NEAREST)
            out["masks"].append(bin_mask)
            raw_box = xyxy[i]
            out["boxes"].append(tuple(raw_box) if raw_box is not None else None)
            out["cls_ids"].append(cid)
            out["names"].append(id2name.get(cid, str(cid)))
            raw_id = tids[i]
            out["ids"].append(int(raw_id) if raw_id is not None else None)

        if (
            self.backend == "ncnn"
            and self.requested_names
            and not self.prompt_filter_supported
            and not self._prompt_warning_emitted
        ):
            print(
                "[YOLOE] NCNN 导出模型不支持动态文本提示词；"
                f"当前请求目标 {self.requested_names} 未映射到导出类别，返回空结果"
            )
            self._prompt_warning_emitted = True
        return out
