# models.py
# -*- coding: utf-8 -*-
"""Legacy model preload compatibility module.

本项目视觉运行时已统一迁移为 NCNN/Vulkan；此模块只保留少量全局引用，避免旧入口误用 PyTorch 模型。
"""

from __future__ import annotations

import logging
import os

import numpy as np
from ultralytics import YOLO

from ncnn_runtime import assert_ncnn_model_path, get_expected_frame_hw, predict_kwargs
from obstacle_detector_client import ObstacleDetectorClient

logger = logging.getLogger(__name__)

obstacle_detector_client: ObstacleDetectorClient | None = None
blindpath_seg_model: YOLO | None = None
models_are_loaded = False


def init_all_models():
    """加载 NCNN/Vulkan 视觉模型；不提供 PyTorch fallback。"""
    global models_are_loaded, obstacle_detector_client, blindpath_seg_model
    if models_are_loaded:
        return

    seg_path = os.getenv("BLIND_PATH_MODEL", "model/yolo-seg_ncnn_model")
    obs_path = os.getenv("OBSTACLE_MODEL", "model/yoloe-11l-seg_ncnn_model")

    logger.info("========= 开始预加载 NCNN/Vulkan 视觉模型 =========")
    assert_ncnn_model_path(seg_path, "盲道分割模型")
    assert_ncnn_model_path(obs_path, "障碍物检测模型")

    blindpath_seg_model = YOLO(seg_path)
    obstacle_detector_client = ObstacleDetectorClient(obs_path)

    h, w = get_expected_frame_hw()
    blank = np.zeros((h, w, 3), dtype=np.uint8)
    blindpath_seg_model.predict(blank, **predict_kwargs())
    obstacle_detector_client.detect(blank)

    models_are_loaded = True
    logger.info("========= NCNN/Vulkan 视觉模型预加载完成 =========")
