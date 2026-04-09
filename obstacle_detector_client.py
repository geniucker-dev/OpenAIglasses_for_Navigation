# app/cloud/obstacle_detector_client.py
import logging
import os
import cv2
import numpy as np
import numpy.typing as npt
import torch
from typing import List, Dict, Any, Optional
from ultralytics import YOLOE

# 导入统一的设备管理工具
from device_utils import DEVICE, DEVICE_TYPE, IS_CUDA, AMP_DTYPE, gpu_infer_slot
from standard_yolo_backend import infer_yolo_backend, load_standard_yolo_model

logger = logging.getLogger(__name__)


class ObstacleDetectorClient:
    def __init__(self, model_path: str = "model/yoloe-11l-seg_ncnn_model"):
        self.model = None
        self.whitelist_embeddings = None
        self.model_path = model_path
        self.backend = infer_yolo_backend(model_path)
        self._warned_unfiltered_ncnn = False
        self.WHITELIST_CLASSES = [
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
        try:
            logger.info("正在加载 YOLOE 障碍物模型...")
            if self.backend == "ncnn":
                self.model = load_standard_yolo_model(model_path, task="segment")
                logger.info("YOLOE NCNN 障碍物模型加载成功，使用 NCNN 运行时")
            else:
                self.model = YOLOE(model_path)
                self.model.fuse()
                logger.info(f"YOLOE 障碍物模型加载成功，使用设备: {DEVICE}")

                logger.info("正在为 YOLOE 预计算白名单文本特征...")
                if DEVICE_TYPE == "mps":
                    self.model.to("cpu")
                    with torch.inference_mode():
                        self.whitelist_embeddings = self.model.get_text_pe(
                            self.WHITELIST_CLASSES
                        )
                    self.model.to(DEVICE)
                    if self.whitelist_embeddings is not None:
                        self.whitelist_embeddings = self.whitelist_embeddings.to(DEVICE)
                elif AMP_DTYPE is not None:
                    with (
                        torch.inference_mode(),
                        torch.amp.autocast(device_type=DEVICE_TYPE, dtype=AMP_DTYPE),
                    ):
                        self.whitelist_embeddings = self.model.get_text_pe(
                            self.WHITELIST_CLASSES
                        )
                else:
                    self.whitelist_embeddings = self.model.get_text_pe(
                        self.WHITELIST_CLASSES
                    )
                logger.info("YOLOE 特征预计算完成。")

                self.model.to(DEVICE)
        except Exception as e:
            logger.error(f"YOLOE 模型加载或特征计算失败: {e}", exc_info=True)
            raise

    @staticmethod
    def tensor_to_numpy_mask(mask_tensor):
        if mask_tensor.dtype in (torch.bfloat16, torch.float16):
            mask_tensor = mask_tensor.float()

        mask = mask_tensor.cpu().numpy()

        if mask.max() <= 1.0:
            mask = (mask > 0.5).astype(np.uint8) * 255
        else:
            mask = mask.astype(np.uint8)

        return mask

    def detect(
        self,
        image: npt.NDArray[np.uint8],
        path_mask: Optional[npt.NDArray[np.uint8]] = None,
    ) -> List[Dict[str, Any]]:
        """
        利用白名单作为提示词寻找障碍物。
        如果提供了 path_mask，则执行与路径相关的空间过滤。
        如果 path_mask 为 None，则进行全局检测。
        """
        if self.model is None:
            return []

        H, W = image.shape[:2]
        if self.backend != "ncnn":
            try:
                self.model.set_classes(
                    self.WHITELIST_CLASSES, self.whitelist_embeddings
                )
            except Exception as e:
                logger.error(f"设置 YOLOE 提示词失败: {e}")
                return []
        elif not self._warned_unfiltered_ncnn:
            logger.warning(
                "YOLOE NCNN 导出模型不支持运行时白名单提示词；障碍物检测将使用导出模型的原生类别结果"
            )
            self._warned_unfiltered_ncnn = True

        conf_thr = float(os.getenv("AIGLASS_OBS_CONF", "0.25"))
        with gpu_infer_slot():
            results = self.model.predict(image, verbose=False, conf=conf_thr)

        if not (results and results[0].masks):
            return []

        # --- 过滤与后处理 (逻辑与 blindpath 工作流保持一致) ---
        final_obstacles = []
        masks_data = results[0].masks.data
        boxes = results[0].boxes
        boxes_cls = (
            boxes.cls
            if boxes is not None and getattr(boxes, "cls", None) is not None
            else None
        )
        num_boxes = len(boxes_cls) if boxes_cls is not None else 0

        for i, mask_tensor in enumerate(masks_data):
            if i >= num_boxes:
                continue

            # 【修复】处理 BFloat16 类型的掩码
            # 先转换为 float32，避免 numpy 不支持 BFloat16 的问题
            if mask_tensor.dtype == torch.bfloat16:
                mask_tensor = mask_tensor.float()

            # 转换为 numpy 数组
            mask = np.asarray(mask_tensor.cpu().numpy())

            # 处理概率掩码（值在0-1之间）或二值掩码
            if mask.max() <= 1.0:
                # 概率掩码，需要二值化
                mask = (mask > 0.5).astype(np.uint8) * 255
            else:
                # 已经是二值掩码
                mask = mask.astype(np.uint8)

            mask = cv2.resize(mask, (W, H), interpolation=cv2.INTER_NEAREST)
            mask_positive = mask.astype(np.uint8) > 0
            area = int(np.sum(mask_positive))

            # 尺寸过滤：太大的物体（如整片地面）通常是误识别
            if (area / (H * W)) > 0.7:
                continue

            # 空间过滤：如果提供了 path_mask，则只保留路径上的障碍物
            if path_mask is not None:
                overlap_mask = cv2.bitwise_and(mask, path_mask)
                intersection_area = int(np.sum(overlap_mask.astype(np.uint8) > 0))
                # 必须与路径有足够的重叠
                if intersection_area < 100 or (intersection_area / area) < 0.01:
                    continue

            if boxes_cls is None:
                continue

            cls_id = int(boxes_cls[i])
            class_names_map = results[0].names
            class_name = "Unknown"
            if isinstance(class_names_map, dict):
                # 如果是字典，使用 .get() 方法
                class_name = class_names_map.get(cls_id, "Unknown")
            elif isinstance(class_names_map, list) and 0 <= cls_id < len(
                class_names_map
            ):
                # 如果是列表，通过索引安全地获取
                class_name = class_names_map[cls_id]

            # 计算距离指标
            y_coords, x_coords = np.where(mask_positive)
            if len(y_coords) == 0:
                continue

            final_obstacles.append(
                {
                    "name": class_name.strip(),
                    "mask": mask,
                    "area": area,
                    "area_ratio": area / (H * W),
                    "center_x": np.mean(x_coords),
                    "center_y": np.mean(y_coords),
                    "bottom_y_ratio": np.max(y_coords) / H,
                }
            )

        return final_obstacles
