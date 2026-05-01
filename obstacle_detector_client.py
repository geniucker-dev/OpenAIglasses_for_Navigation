# obstacle_detector_client.py
# -*- coding: utf-8 -*-
import logging
import os
from typing import Any, Dict, List

import cv2
import numpy as np
from ultralytics import YOLO

from ncnn_runtime import (
    assert_frame_shape,
    assert_ncnn_model_path,
    predict_kwargs,
    tensor_like_scalar,
    tensor_like_to_numpy,
)

logger = logging.getLogger(__name__)


class ObstacleDetectorClient:
    WHITELIST_CLASSES = [
        "bicycle",
        "car",
        "motorcycle",
        "bus",
        "truck",
        "animal",
        "scooter",
        "stroller",
        "dog",
        "pole",
        "post",
        "column",
        "pillar",
        "stanchion",
        "bollard",
        "utility pole",
        "telegraph pole",
        "light pole",
        "street pole",
        "signpost",
        "support post",
        "vertical post",
        "bench",
        "chair",
        "potted plant",
        "hydrant",
        "cone",
        "stone",
        "box",
    ]

    def __init__(self, model_path: str = "model/yoloe-11l-seg_ncnn_model"):
        self.model = None
        self.model_path = str(assert_ncnn_model_path(model_path, "障碍物检测模型"))
        logger.info("正在加载 NCNN 障碍物模型: %s", self.model_path)
        try:
            self.model = YOLO(self.model_path)
            logger.info("NCNN 障碍物模型加载成功")
        except Exception as e:
            logger.error("NCNN 障碍物模型加载失败: %s", e, exc_info=True)
            raise

    @staticmethod
    def _class_name(names: Any, cls_id: int) -> str:
        if isinstance(names, dict):
            value = names.get(cls_id)
            if value is not None:
                return str(value)
        elif isinstance(names, list) and 0 <= cls_id < len(names):
            return str(names[cls_id])

        if 0 <= cls_id < len(ObstacleDetectorClient.WHITELIST_CLASSES):
            return ObstacleDetectorClient.WHITELIST_CLASSES[cls_id]
        return f"class_{cls_id}"

    @staticmethod
    def _mask_to_uint8(mask_value: Any, width: int, height: int) -> np.ndarray:
        mask = tensor_like_to_numpy(mask_value)
        if mask.ndim > 2:
            mask = np.squeeze(mask)
        if mask.max() <= 1.0:
            mask = (mask > 0.5).astype(np.uint8) * 255
        else:
            mask = mask.astype(np.uint8)
        if mask.shape[:2] != (height, width):
            mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)
        return mask

    def detect(
        self, image: np.ndarray, path_mask: np.ndarray = None
    ) -> List[Dict[str, Any]]:
        """使用已固化白名单的 NCNN 障碍物模型检测。"""
        if self.model is None:
            raise RuntimeError("障碍物 NCNN 模型未加载")

        assert_frame_shape(image, "obstacle frame")
        height, width = image.shape[:2]
        conf_thr = float(os.getenv("AIGLASS_OBS_CONF", "0.25"))

        results = self.model.predict(image, **predict_kwargs(conf=conf_thr))
        if not results:
            return []

        result = results[0]
        masks_obj = getattr(result, "masks", None)
        boxes_obj = getattr(result, "boxes", None)
        if masks_obj is None or getattr(masks_obj, "data", None) is None:
            if boxes_obj is not None and len(boxes_obj) > 0:
                raise RuntimeError("障碍物 NCNN 有检测框但缺少 masks")
            return []
        if boxes_obj is None or getattr(boxes_obj, "cls", None) is None:
            raise RuntimeError("障碍物 NCNN 输出缺少 boxes.cls，无法完成白名单类别映射")

        masks_data = list(masks_obj.data)
        cls_data = list(boxes_obj.cls)
        num_boxes = len(cls_data)
        names_map = getattr(result, "names", getattr(self.model, "names", {}))

        final_obstacles: List[Dict[str, Any]] = []
        for i, mask_value in enumerate(masks_data):
            if i >= num_boxes:
                continue

            mask = self._mask_to_uint8(mask_value, width, height)
            area = int(np.sum(mask > 0))
            if area <= 0:
                continue

            if (area / (height * width)) > 0.7:
                continue

            if path_mask is not None:
                if path_mask.shape[:2] != (height, width):
                    path_mask = cv2.resize(
                        path_mask, (width, height), interpolation=cv2.INTER_NEAREST
                    )
                intersection_area = np.sum(cv2.bitwise_and(mask, path_mask) > 0)
                if intersection_area < 100 or (intersection_area / area) < 0.01:
                    continue

            cls_id = int(tensor_like_scalar(cls_data[i]))
            class_name = self._class_name(names_map, cls_id).strip()

            y_coords, x_coords = np.where(mask > 0)
            if len(y_coords) == 0:
                continue

            final_obstacles.append(
                {
                    "name": class_name,
                    "mask": mask,
                    "area": area,
                    "area_ratio": area / (height * width),
                    "center_x": float(np.mean(x_coords)),
                    "center_y": float(np.mean(y_coords)),
                    "bottom_y_ratio": float(np.max(y_coords) / height),
                }
            )

        return final_obstacles
