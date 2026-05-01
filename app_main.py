# app_main.py
# -*- coding: utf-8 -*-
import os, sys, time, json, asyncio
from typing import Any, Dict, Optional, Tuple, List, Callable, Set, Deque
from collections import deque
from dataclasses import dataclass
from contextlib import asynccontextmanager
import re

# 在其它 import 之后加：
from qwen_extractor import extract_english_label
from navigation_master import NavigationMaster, OrchestratorResult

# 新增：导入盲道导航器
from workflow_blindpath import BlindPathNavigator

# 新增：导入过马路导航器
from workflow_crossstreet import CrossStreetNavigator
import torch
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState
import uvicorn
import cv2
import numpy as np
from ultralytics import YOLO
from obstacle_detector_client import ObstacleDetectorClient
from device_utils import DEVICE, IS_CUDA

import torch  # 添加这行


import mediapipe as mp
import bridge_io
import threading
import yolomedia  # 确保和 app_main.py 同目录，文件名就是 yolomedia.py

# ---- Windows 事件循环策略 ----
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# ---- .env ----
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# ---- DashScope ASR 基础 ----
from dashscope import audio as dash_audio  # 若未安装，会在原项目里抛错提示

API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-a9440db694924559ae4ebdc2023d2b9a")
if not API_KEY:
    raise RuntimeError("未设置 DASHSCOPE_API_KEY")

MODEL = "paraformer-realtime-v2"
SAMPLE_RATE = 16000
AUDIO_FMT = "pcm"
CHUNK_MS = 20
BYTES_CHUNK = SAMPLE_RATE * CHUNK_MS // 1000 * 2
SILENCE_20MS = bytes(BYTES_CHUNK)

# ---- 引入我们的模块 ----
from audio_stream import (
    register_stream_route,  # 挂 /stream.wav
    hard_reset_audio,  # 音频+AI 播放总闸
    is_playing_now,
)
from omni_client import cleanup_producer_threads
from asr_core import (
    ASRCallback,
    set_current_recognition,
    stop_current_recognition,
)
from audio_player import initialize_audio_system, play_voice_text, shutdown_audio_system, sanitize_audio_system_state

# ---- 同步录制器 ----
import sync_recorder

# ---- IMU UDP ----
UDP_IP = "0.0.0.0"
UDP_PORT = 12345


@asynccontextmanager
async def lifespan(_: FastAPI):
    await on_startup_register_bridge_sender()
    try:
        await on_startup()
    except Exception:
        bridge_io.set_sender(None)
        bridge_io.clear_frames()
        raise
    try:
        yield
    finally:
        await on_shutdown()


app = FastAPI(lifespan=lifespan)

# ====== 状态与容器 ======
app.mount("/static", StaticFiles(directory="static"), name="static")

ui_clients: Dict[int, WebSocket] = {}
current_partial: str = ""
recent_finals: List[str] = []
RECENT_MAX = 50
last_frames: Deque[Tuple[float, bytes]] = deque(maxlen=10)
AUDIO_FRAME_STALE_SEC = 2.0
CAMERA_FRAME_STALE_SEC = 2.5
CAMERA_FIRST_FRAME_TIMEOUT_SEC = 4.0
CAMERA_SOCKET_GRACE_SEC = 6.0

camera_viewers: Set[WebSocket] = set()
esp32_camera_ws: Optional[WebSocket] = None
imu_ws_clients: Set[WebSocket] = set()
esp32_audio_ws: Optional[WebSocket] = None
camera_connected_at: float = 0.0
camera_last_frame_at: float = 0.0
camera_status_cache: Optional[str] = None
camera_status_task: Optional[asyncio.Task[Any]] = None
imu_broadcast_tasks: Set[asyncio.Task[Any]] = set()
imu_accepting_packets: bool = False
imu_transport: Optional[asyncio.DatagramTransport] = None
esp32_audio_last_frame_at: float = 0.0
asr_streaming_active: bool = False
asr_status_cache: Optional[str] = None
active_asr_stop_fn: Optional[Callable[[], Any]] = None

# 【新增】盲道导航相关全局变量
blind_path_navigator = None
navigation_active = False
yolo_seg_model = None
obstacle_detector = None

# 【新增】过马路导航相关全局变量
cross_street_navigator = None
cross_street_active = False
orchestrator = None  # 新增
startup_ready = False

# 【新增】omni对话状态标志
omni_conversation_active = False  # 标记omni对话是否正在进行
omni_previous_nav_state = None  # 保存omni激活前的导航状态，用于恢复
omni_session_generation = 0

def reset_ui_session_state():
    global current_partial, recent_finals, camera_status_cache, asr_status_cache, omni_conversation_active, omni_previous_nav_state
    current_partial = ""
    recent_finals = []
    camera_status_cache = None
    asr_status_cache = None
    omni_conversation_active = False
    omni_previous_nav_state = None

def bump_omni_generation():
    global omni_session_generation
    omni_session_generation += 1
    return omni_session_generation

def clear_navigation_session_state():
    global blind_path_navigator, cross_street_navigator, orchestrator, navigation_active, cross_street_active
    blind_path_navigator = None
    cross_street_navigator = None
    orchestrator = None
    navigation_active = False
    cross_street_active = False

def reset_trafficlight_runtime_state():
    try:
        import trafficlight_detection
        return trafficlight_detection.reset_runtime_state()
    except Exception:
        return False


# 【新增】模型加载函数
def load_navigation_models():
    """加载盲道导航所需的模型"""
    global yolo_seg_model, obstacle_detector

    try:
        seg_model_path = os.getenv("BLIND_PATH_MODEL", "model/yolo-seg.pt")

        if os.path.exists(seg_model_path):
            print(f"[NAVIGATION] 模型文件存在，开始加载...")
            yolo_seg_model = YOLO(seg_model_path)
            yolo_seg_model.to(DEVICE)
            print(f"[NAVIGATION] 盲道分割模型加载成功，设备: {DEVICE}")

            try:
                test_img = np.zeros((640, 640, 3), dtype=np.uint8)
                results = yolo_seg_model.predict(
                    test_img,
                    device=DEVICE,
                    verbose=False,
                )
                print(
                    f"[NAVIGATION] 模型测试成功，支持的类别数: {len(yolo_seg_model.names) if hasattr(yolo_seg_model, 'names') else '未知'}"
                )
                if hasattr(yolo_seg_model, "names"):
                    print(f"[NAVIGATION] 模型类别: {yolo_seg_model.names}")
            except Exception as e:
                print(f"[NAVIGATION] 模型测试失败: {e}")
                yolo_seg_model = None
        else:
            print(f"[NAVIGATION] 错误：找不到模型文件: {seg_model_path}")
            print(f"[NAVIGATION] 当前工作目录: {os.getcwd()}")
            print(f"[NAVIGATION] 请检查文件路径是否正确")

        obstacle_model_path = os.getenv("OBSTACLE_MODEL", "model/yoloe-11l-seg.pt")
        print(f"[NAVIGATION] 尝试加载障碍物检测模型: {obstacle_model_path}")

        if os.path.exists(obstacle_model_path):
            print(f"[NAVIGATION] 障碍物检测模型文件存在，开始加载...")
            try:
                obstacle_detector = ObstacleDetectorClient(
                    model_path=obstacle_model_path
                )
                print(f"[NAVIGATION] ========== YOLO-E 障碍物检测器加载成功 ==========")

                if (
                    hasattr(obstacle_detector, "model")
                    and obstacle_detector.model is not None
                ):
                    print(f"[NAVIGATION] YOLO-E 模型已初始化")
                    print(
                        f"[NAVIGATION] 模型设备: {next(obstacle_detector.model.parameters()).device}"
                    )
                else:
                    print(f"[NAVIGATION] 警告：YOLO-E 模型初始化异常")

                if hasattr(obstacle_detector, "WHITELIST_CLASSES"):
                    print(
                        f"[NAVIGATION] 白名单类别数: {len(obstacle_detector.WHITELIST_CLASSES)}"
                    )
                    print(
                        f"[NAVIGATION] 白名单前10个类别: {', '.join(obstacle_detector.WHITELIST_CLASSES[:10])}"
                    )
                else:
                    print(f"[NAVIGATION] 警告：白名单类别未定义")

                if (
                    hasattr(obstacle_detector, "whitelist_embeddings")
                    and obstacle_detector.whitelist_embeddings is not None
                ):
                    print(f"[NAVIGATION] YOLO-E 文本特征已预计算")
                    print(
                        f"[NAVIGATION] 文本特征张量形状: {obstacle_detector.whitelist_embeddings.shape if hasattr(obstacle_detector.whitelist_embeddings, 'shape') else '未知'}"
                    )
                else:
                    print(f"[NAVIGATION] 警告：YOLO-E 文本特征未预计算")

                # 测试障碍物检测功能
                print(f"[NAVIGATION] 开始测试 YOLO-E 检测功能...")
                try:
                    test_img = np.zeros((640, 640, 3), dtype=np.uint8)
                    # 在测试图像中画一个白色矩形，模拟一个物体
                    cv2.rectangle(test_img, (200, 200), (400, 400), (255, 255, 255), -1)

                    # 测试检测（不提供 path_mask）
                    test_results = obstacle_detector.detect(test_img)
                    print(f"[NAVIGATION] YOLO-E 检测测试成功!")
                    print(f"[NAVIGATION] 测试检测结果数: {len(test_results)}")

                    if len(test_results) > 0:
                        print(f"[NAVIGATION] 测试检测到的物体:")
                        for i, obj in enumerate(test_results):
                            print(
                                f"  - 物体 {i + 1}: {obj.get('name', 'unknown')}, "
                                f"面积比例: {obj.get('area_ratio', 0):.3f}, "
                                f"位置: ({obj.get('center_x', 0):.0f}, {obj.get('center_y', 0):.0f})"
                            )
                except Exception as e:
                    print(f"[NAVIGATION] YOLO-E 检测测试失败: {e}")
                    import traceback

                    traceback.print_exc()
                    obstacle_detector = None

                print(f"[NAVIGATION] ========== YOLO-E 障碍物检测器加载完成 ==========")

            except Exception as e:
                print(f"[NAVIGATION] 障碍物检测器加载失败: {e}")
                import traceback

                traceback.print_exc()
                obstacle_detector = None
        else:
            print(f"[NAVIGATION] 警告：找不到障碍物检测模型文件: {obstacle_model_path}")

    except Exception as e:
        print(f"[NAVIGATION] 模型加载失败: {e}")
        import traceback

        traceback.print_exc()


# ============== 关键：系统级"硬重置"总闸 =================
interrupt_lock = asyncio.Lock()
audio_ws_claim_lock = asyncio.Lock()
camera_ws_claim_lock = asyncio.Lock()

# ============== YOLO媒体线程管理 =================
yolomedia_thread: Optional[threading.Thread] = None
yolomedia_stop_event = threading.Event()
yolomedia_running = False
yolomedia_sending_frames = False  # 新增：标记YOLO是否已经开始发送处理后的帧

# 物品名称到YOLO类别的映射
ITEM_TO_CLASS_MAP = {
    "红牛": "Red_Bull",
    "AD钙奶": "AD_milk",
    "ad钙奶": "AD_milk",
    "钙奶": "AD_milk",
}


async def ui_broadcast_raw(msg: str):
    dead = []
    for k, ws in list(ui_clients.items()):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(k)
    for k in dead:
        ui_clients.pop(k, None)


def get_camera_status_payload() -> Dict[str, Any]:
    now = time.time()
    if esp32_camera_ws is None:
        state = "disconnected"
        text = "Camera: disconnected"
    elif (
        camera_last_frame_at > 0
        and (now - camera_last_frame_at) <= CAMERA_FRAME_STALE_SEC
    ):
        state = "live"
        text = "Camera: live"
    elif camera_last_frame_at <= 0:
        state = "waiting"
        text = "Camera: waiting for first frame"
    else:
        state = "waiting"
        text = "Camera: frame stream stalled"

    return {
        "state": state,
        "text": text,
        "socket_connected": esp32_camera_ws is not None,
        "viewer_count": len(camera_viewers),
        "last_frame_age_sec": None
        if camera_last_frame_at <= 0
        else max(0.0, round(now - camera_last_frame_at, 2)),
    }


async def broadcast_camera_status(force: bool = False):
    global camera_status_cache
    payload = get_camera_status_payload()
    message = "CAMERA_STATUS:" + json.dumps(payload, ensure_ascii=False)
    if not force and message == camera_status_cache:
        return
    camera_status_cache = message
    await ui_broadcast_raw(message)


def get_asr_status_payload() -> Dict[str, Any]:
    now = time.time()
    if esp32_audio_ws is None and active_asr_stop_fn is not None:
        state = "error"
        text = "ASR: cleanup incomplete"
    elif esp32_audio_ws is None:
        state = "disconnected"
        text = "ASR: audio device disconnected"
    elif (
        asr_streaming_active
        and esp32_audio_last_frame_at > 0
        and (now - esp32_audio_last_frame_at) <= AUDIO_FRAME_STALE_SEC
    ):
        state = "live"
        text = "ASR: listening"
    elif asr_streaming_active:
        state = "waiting"
        text = "ASR: waiting for audio"
    else:
        state = "idle"
        text = "ASR: device connected"

    return {
        "state": state,
        "text": text,
        "socket_connected": esp32_audio_ws is not None,
        "streaming": asr_streaming_active,
        "last_frame_age_sec": None
        if esp32_audio_last_frame_at <= 0
        else max(0.0, round(now - esp32_audio_last_frame_at, 2)),
    }


async def broadcast_asr_status(force: bool = False):
    global asr_status_cache
    payload = get_asr_status_payload()
    message = "ASR_STATUS:" + json.dumps(payload, ensure_ascii=False)
    if not force and message == asr_status_cache:
        return
    asr_status_cache = message
    await ui_broadcast_raw(message)


async def ui_broadcast_partial(text: str):
    global current_partial
    current_partial = text
    await ui_broadcast_raw("PARTIAL:" + text)


async def ui_broadcast_final(text: str):
    global current_partial, recent_finals
    current_partial = ""
    recent_finals.append(text)
    if len(recent_finals) > RECENT_MAX:
        recent_finals = recent_finals[-RECENT_MAX:]
    await ui_broadcast_raw("FINAL:" + text)
    print(f"[ASR/AI FINAL] {text}", flush=True)


async def full_system_reset(reason: str = "") -> bool:
    """
    回到刚启动后的状态：
    1) 停播 + 取消AI任务 + 切断所有/stream.wav（hard_reset_audio）
    2) 停止 ASR 实时识别流（关键）
    3) 清 UI 状态
    4) 清最近相机帧（避免把旧帧又拼进下一轮）
    5) 告知 ESP32：RESET（可选）
    """
    global active_asr_stop_fn, asr_streaming_active, esp32_audio_last_frame_at

    bump_omni_generation()
    reset_ui_session_state()

    # 1) 音频&AI
    await hard_reset_audio(reason or "full_system_reset")
    omni_threads_clean = cleanup_producer_threads()

    # 2) ASR
    recognition_stopped = True
    if active_asr_stop_fn is not None:
        recognition_stopped = await active_asr_stop_fn()
    else:
        recognition_stopped = await stop_current_recognition()
        if recognition_stopped:
            active_asr_stop_fn = None
            asr_streaming_active = False
            esp32_audio_last_frame_at = 0.0
    if not recognition_stopped:
        print("[SYSTEM] full reset incomplete: recognition stop failed.", flush=True)
    if not omni_threads_clean:
        print("[SYSTEM] full reset incomplete: omni producer thread still alive.", flush=True)

    reset_imu_runtime_state()
    traffic_reset_ok = reset_trafficlight_runtime_state()
    bridge_io.clear_frames()

    # 2.5) 停止运行中的找物品线程
    yolomedia_stopped = stop_yolomedia()
    if not yolomedia_stopped:
        print("[SYSTEM] full reset incomplete: yolomedia still running.", flush=True)

    if yolomedia_stopped:
        clear_navigation_session_state()

    # 3) UI
    await ui_broadcast_raw("RESET_UI")
    await ui_broadcast_partial("")

    # 4) 相机帧
    try:
        last_frames.clear()
    except Exception:
        pass

    # 5) 通知 ESP32
    try:
        if esp32_audio_ws and (esp32_audio_ws.client_state == WebSocketState.CONNECTED):
            await esp32_audio_ws.send_text("RESET")
    except Exception:
        pass

    if not traffic_reset_ok:
        print("[SYSTEM] full reset incomplete: traffic-light runtime reset failed.", flush=True)

    if yolomedia_stopped and recognition_stopped and traffic_reset_ok and omni_threads_clean:
        print("[SYSTEM] full reset done.", flush=True)
    else:
        print("[SYSTEM] full reset incomplete.", flush=True)
    return bool(yolomedia_stopped and recognition_stopped and traffic_reset_ok and omni_threads_clean)


# ========= 启动/停止 YOLO 媒体处理 =========
def start_yolomedia_with_target(target_name: str) -> bool:
    """启动yolomedia线程，搜索指定物品"""
    global \
        yolomedia_thread, \
        yolomedia_stop_event, \
        yolomedia_running, \
        yolomedia_sending_frames

    # 如果已经在运行，先停止
    if yolomedia_running:
        if not stop_yolomedia():
            return False

    # 查找对应的YOLO类别
    yolo_class = ITEM_TO_CLASS_MAP.get(target_name, target_name)
    print(
        f"[YOLOMEDIA] Starting with target: {target_name} -> YOLO class: {yolo_class}",
        flush=True,
    )
    print(
        f"[YOLOMEDIA] Available mappings: {ITEM_TO_CLASS_MAP}", flush=True
    )  # 添加这行调试

    yolomedia_stop_event.clear()
    yolomedia_running = True
    yolomedia_sending_frames = False  # 重置发送帧状态
    worker_started = threading.Event()

    def _run():
        worker_started.set()
        try:
            # 传递目标类别名和停止事件
            yolomedia.main(
                headless=True, prompt_name=yolo_class, stop_event=yolomedia_stop_event
            )
        except Exception as e:
            print(f"[YOLOMEDIA] worker stopped: {e}", flush=True)
        finally:
            global yolomedia_running, yolomedia_sending_frames
            yolomedia_running = False
            yolomedia_sending_frames = False

    yolomedia_thread = threading.Thread(target=_run, daemon=True)
    yolomedia_thread.start()
    worker_started.wait(timeout=0.2)
    if yolomedia_thread is None or not yolomedia_thread.is_alive():
        yolomedia_running = False
        yolomedia_sending_frames = False
        return False
    print(
        f"[YOLOMEDIA] background worker started for: {yolo_class}（正在初始化，暂时显示原始画面）",
        flush=True,
    )
    return True


def stop_yolomedia() -> bool:
    """停止yolomedia线程"""
    global \
        yolomedia_thread, \
        yolomedia_stop_event, \
        yolomedia_running, \
        yolomedia_sending_frames

    if yolomedia_running:
        print("[YOLOMEDIA] Stopping worker...", flush=True)
        yolomedia_stop_event.set()

        # 等待线程结束（最多等5秒）
        if yolomedia_thread and yolomedia_thread.is_alive():
            yolomedia_thread.join(timeout=5.0)

        if yolomedia_thread and yolomedia_thread.is_alive():
            print("[YOLOMEDIA] Worker still alive after stop timeout.", flush=True)
            return False

        yolomedia_thread = None
        yolomedia_running = False
        yolomedia_sending_frames = False

        # 【新增】如果orchestrator在找物品模式，结束时不自动恢复（由命令控制）
        # 只清理标志位即可
        print("[YOLOMEDIA] Worker stopped, 等待状态切换.", flush=True)
    return True


# ========= 自定义的 start_ai_with_text，支持识别特殊命令 =========
async def start_ai_with_text_custom(user_text: str):
    """扩展版的AI启动函数，支持识别特殊命令"""
    global \
        navigation_active, \
        blind_path_navigator, \
        cross_street_active, \
        cross_street_navigator, \
        orchestrator

    # 【修改】在导航模式和红绿灯检测模式下，只有特定词才进入omni对话
    if orchestrator:
        current_state = orchestrator.get_state()
        # 如果在导航模式或红绿灯检测模式（非CHAT模式）
        if current_state not in ["CHAT", "IDLE"]:
            # 检查是否是允许的对话触发词
            allowed_keywords = [
                "帮我看",
                "帮我看下",
                "帮我找",
                "找一下",
                "看看",
                "识别一下",
            ]
            is_allowed_query = any(keyword in user_text for keyword in allowed_keywords)

            # 检查是否是导航控制命令
            nav_control_keywords = [
                "开始过马路",
                "过马路结束",
                "结束过马路",
                "停止过马路",
                "取消过马路",
                "开始导航",
                "盲道导航",
                "停止导航",
                "结束导航",
                "取消导航",
                "检测红绿灯",
                "看红绿灯",
                "停止检测",
                "取消检测",
                "停止红绿灯",
                "取消红绿灯",
            ]
            is_nav_control = any(
                keyword in user_text for keyword in nav_control_keywords
            )

            # 如果既不是允许的查询，也不是导航控制命令，则丢弃
            if not is_allowed_query and not is_nav_control:
                mode_name = (
                    "红绿灯检测"
                    if current_state == "TRAFFIC_LIGHT_DETECTION"
                    else "导航"
                )
                print(f"[{mode_name}模式] 丢弃非对话语音: {user_text}")
                return  # 直接丢弃，不进入omni

    # 【修改】检查是否是过马路相关命令 - 使用orchestrator控制
    if "开始过马路" in user_text or "帮我过马路" in user_text:
        # 【新增】如果正在找物品，先停止
        if yolomedia_running:
            if not stop_yolomedia():
                await ui_broadcast_final("[系统] 找物品任务仍在停止中，请稍后再试")
                return
            print("[ITEM_SEARCH] 从找物品模式切换到过马路")

        if orchestrator:
            orchestrator.start_crossing()
            print(f"[CROSS_STREET] 过马路模式已启动，状态: {orchestrator.get_state()}")
            # 播放启动语音并广播到UI
            play_voice_text("过马路模式已启动。")
            await ui_broadcast_final("[系统] 过马路模式已启动")
        else:
            print("[CROSS_STREET] 警告：导航统领器未初始化！")
            play_voice_text("启动过马路模式失败，请稍后重试。")
            await ui_broadcast_final("[系统] 导航系统未就绪")
        return

    if (
        "过马路结束" in user_text
        or "结束过马路" in user_text
        or "停止过马路" in user_text
        or "取消过马路" in user_text
    ):
        if orchestrator:
            orchestrator.stop_navigation()
            print(f"[CROSS_STREET] 导航已停止，状态: {orchestrator.get_state()}")
            # 播放停止语音并广播到UI
            play_voice_text("已停止导航。")
            await ui_broadcast_final("[系统] 过马路模式已停止")
        else:
            await ui_broadcast_final("[系统] 导航系统未运行")
        return

    # 【修改】检查是否是红绿灯检测命令 - 实现与盲道导航互斥
    if "检测红绿灯" in user_text or "看红绿灯" in user_text:
        try:
            import trafficlight_detection

            # 【改进】使用主线程模式而不是独立线程，避免掉帧
            success = trafficlight_detection.init_model()  # 只初始化模型，不启动线程
            reset_ok = trafficlight_detection.reset_runtime_state(clear_model=False)  # 重置状态但保留模型

            if success and reset_ok and orchestrator:
                # 切换orchestrator到红绿灯检测模式（暂停盲道导航）
                orchestrator.start_traffic_light_detection()
                print(
                    f"[TRAFFIC] 切换到红绿灯检测模式，状态: {orchestrator.get_state()}"
                )
                await ui_broadcast_final("[系统] 红绿灯检测已启动")
            elif success and reset_ok:
                await ui_broadcast_final("[系统] 导航系统未就绪")
            elif not reset_ok:
                await ui_broadcast_final("[系统] 红绿灯运行态重置失败")
            else:
                await ui_broadcast_final("[系统] 红绿灯模型加载失败")
        except Exception as e:
            print(f"[TRAFFIC] 启动红绿灯检测失败: {e}")
            await ui_broadcast_final(f"[系统] 启动失败: {e}")
        return

    if (
        "停止检测" in user_text
        or "取消检测" in user_text
        or "停止红绿灯" in user_text
        or "取消红绿灯" in user_text
    ):
        try:
            if not reset_trafficlight_runtime_state():
                raise RuntimeError("红绿灯检测运行态清理失败")

            # 恢复到对话模式
            if orchestrator:
                orchestrator.stop_navigation()  # 回到CHAT模式
                print(f"[TRAFFIC] 红绿灯检测停止，恢复到{orchestrator.get_state()}模式")
                await ui_broadcast_final("[系统] 红绿灯检测已停止")
            else:
                await ui_broadcast_final("[系统] 导航系统未就绪")
        except Exception as e:
            print(f"[TRAFFIC] 停止红绿灯检测失败: {e}")
            await ui_broadcast_final(f"[系统] 停止失败: {e}")
        return

    # 【修改】检查是否是导航相关命令 - 使用orchestrator控制
    if "开始导航" in user_text or "盲道导航" in user_text or "帮我导航" in user_text:
        # 【新增】如果正在找物品，先停止
        if yolomedia_running:
            if not stop_yolomedia():
                await ui_broadcast_final("[系统] 找物品任务仍在停止中，请稍后再试")
                return
            print("[ITEM_SEARCH] 从找物品模式切换到盲道导航")

        if orchestrator:
            orchestrator.start_blind_path_navigation()
            print(f"[NAVIGATION] 盲道导航已启动，状态: {orchestrator.get_state()}")
            await ui_broadcast_final("[系统] 盲道导航已启动")
        else:
            print("[NAVIGATION] 警告：导航统领器未初始化！")
            await ui_broadcast_final("[系统] 导航系统未就绪")
        return

    if "停止导航" in user_text or "结束导航" in user_text or "取消导航" in user_text:
        if orchestrator:
            orchestrator.stop_navigation()
            print(f"[NAVIGATION] 导航已停止，状态: {orchestrator.get_state()}")
            await ui_broadcast_final("[系统] 盲道导航已停止")
        else:
            await ui_broadcast_final("[系统] 导航系统未运行")
        return

    nav_cmd_keywords = [
        "开始过马路",
        "过马路结束",
        "结束过马路",
        "停止过马路",
        "取消过马路",
        "开始导航",
        "盲道导航",
        "停止导航",
        "结束导航",
        "取消导航",
        "立即通过",
        "现在通过",
        "继续",
    ]
    if any(k in user_text for k in nav_cmd_keywords):
        if orchestrator:
            orchestrator.on_voice_command(user_text)
            await ui_broadcast_final("[系统] 导航模式已更新")
        else:
            await ui_broadcast_final("[系统] 导航统领器未初始化")
        return

    # 检查是否是"帮我找/识别一下xxx"的命令
    # 扩展正则表达式，支持更多关键词
    find_pattern = r"(?:^\s*帮我)?\s*找一下\s*(.+?)(?:。|！|？|$)"
    match = re.search(find_pattern, user_text)

    if match:
        # 提取中文物品名称
        item_cn = match.group(1).strip()
        if item_cn:
            # 【新增】用本地映射 + Qwen 提取英文类名
            label_en, src = extract_english_label(item_cn)
            print(
                f"[COMMAND] Finder request: '{item_cn}' -> '{label_en}' (src={src})",
                flush=True,
            )

            if not orchestrator:
                await ui_broadcast_final("[系统] 导航系统未就绪")
                return

            # 【新增】切换到找物品模式（暂停导航）
            # 【关键】把英文类名传给 yolomedia（它会在找不到类时自动切 YOLOE）
            if not start_yolomedia_with_target(label_en):
                await ui_broadcast_final("[找物品] 上一次找物品任务仍在停止中，请稍后再试。")
                return

            # 【新增】切换到找物品模式（暂停导航）
            orchestrator.start_item_search()
            print(
                f"[ITEM_SEARCH] 已切换到找物品模式，状态: {orchestrator.get_state()}"
            )

            # 给前端/语音来个确认反馈
            try:
                await ui_broadcast_final(f"[找物品] 正在寻找 {item_cn}...")
            except Exception:
                pass

            return

    # 检查是否是"找到了"的命令
    if "找到了" in user_text or "拿到了" in user_text:
        print("[COMMAND] Found command detected", flush=True)
        # 停止yolomedia
        if not stop_yolomedia():
            await ui_broadcast_final("[找物品] 当前找物品任务仍在停止中，请稍后再试。")
            return

        # 【新增】停止找物品模式，恢复之前的导航状态
        if orchestrator:
            orchestrator.stop_item_search(restore_nav=True)
            current_state = orchestrator.get_state()
            print(f"[ITEM_SEARCH] 找物品结束，当前状态: {current_state}")

            # 根据恢复的状态给出反馈
            if current_state in [
                "BLINDPATH_NAV",
                "SEEKING_CROSSWALK",
                "WAIT_TRAFFIC_LIGHT",
                "CROSSING",
                "SEEKING_NEXT_BLINDPATH",
            ]:
                await ui_broadcast_final("[找物品] 已找到物品，继续导航。")
            else:
                await ui_broadcast_final("[找物品] 已找到物品。")
        else:
            await ui_broadcast_final("[找物品] 已找到物品。")

        return

    print(f"[COMMAND] No keyword matched, ignoring text: {user_text}", flush=True)
    return

# ---------- 页面 / 健康 ----------
@app.get("/", response_class=HTMLResponse)
def root():
    with open(os.path.join("templates", "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/api/health", response_class=PlainTextResponse)
def health():
    ready = startup_ready and orchestrator is not None
    return PlainTextResponse("OK" if ready else "STARTING", status_code=200 if ready else 503)


@app.post("/api/debug_text")
async def debug_text(request: Request):
    data = await request.json()
    user_text = data.get("text", "").strip()
    if not user_text:
        return {"success": False, "error": "Empty text"}

    async with interrupt_lock:
        await start_ai_with_text_custom(user_text)
    return {"success": True, "text": user_text}


# 注册 /stream.wav
register_stream_route(app)


# ---------- WebSocket：WebUI 文本（ASR/AI 状态推送） ----------
@app.websocket("/ws_ui")
async def ws_ui(ws: WebSocket):
    await ws.accept()
    ui_clients[id(ws)] = ws
    try:
        init = {
            "partial": current_partial,
            "finals": recent_finals[-10:],
            "camera": get_camera_status_payload(),
            "asr": get_asr_status_payload(),
        }
        await ws.send_text("INIT:" + json.dumps(init, ensure_ascii=False))
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        ui_clients.pop(id(ws), None)


# ---------- WebSocket：ESP32 音频入口（ASR 上行） ----------
@app.websocket("/ws_audio")
async def ws_audio(ws: WebSocket):
    global esp32_audio_ws, esp32_audio_last_frame_at, asr_streaming_active, active_asr_stop_fn
    async with audio_ws_claim_lock:
        if active_asr_stop_fn is not None:
            await ws.close(code=1013)
            return
        if esp32_audio_ws is not None:
            await ws.close(code=1013)
            return
        await ws.accept()
        esp32_audio_ws = ws
        esp32_audio_last_frame_at = 0.0
        asr_streaming_active = False
    print("\n[AUDIO] client connected")
    await broadcast_asr_status(force=True)
    recognition = None
    streaming = False
    last_ts = time.monotonic()
    keepalive_task: Optional[asyncio.Task[Any]] = None

    async def stop_rec(send_notice: Optional[str] = None):
        global asr_streaming_active, esp32_audio_last_frame_at
        nonlocal recognition, streaming, keepalive_task
        stop_ok = True
        if keepalive_task and not keepalive_task.done():
            keepalive_task.cancel()
            try:
                await keepalive_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        keepalive_task = None
        if recognition:
            try:
                recognition.stop()
            except Exception:
                stop_ok = False
            if stop_ok:
                recognition = None
                await set_current_recognition(None)
                streaming = False
                asr_streaming_active = False
                esp32_audio_last_frame_at = 0.0
                await ui_broadcast_partial("")
                await broadcast_asr_status(force=True)
        if send_notice:
            if stop_ok:
                try:
                    await ws.send_text(send_notice)
                except Exception:
                    pass
        return stop_ok

    async def on_sdk_error(_msg: str):
        await stop_rec(send_notice="RESTART")

    async def keepalive_loop():
        nonlocal last_ts, recognition, streaming
        try:
            while streaming and recognition is not None:
                idle = time.monotonic() - last_ts
                if idle > 0.35:
                    try:
                        for _ in range(30):  # ~600ms 静音
                            recognition.send_audio_frame(SILENCE_20MS)
                        last_ts = time.monotonic()
                    except Exception:
                        await on_sdk_error("keepalive send failed")
                        return
                await asyncio.sleep(0.10)
        except asyncio.CancelledError:
            return

    try:
        while True:
            if WebSocketState and ws.client_state != WebSocketState.CONNECTED:
                break
            try:
                msg = await ws.receive()
            except WebSocketDisconnect:
                break
            except RuntimeError as e:
                if 'Cannot call "receive"' in str(e):
                    break
                raise

            if "text" in msg and msg["text"] is not None:
                raw = (msg["text"] or "").strip()
                cmd = raw.upper()

                if cmd == "START":
                    print("[AUDIO] START received")
                    esp32_audio_last_frame_at = 0.0
                    if not await stop_rec():
                        print("[AUDIO] previous recognition stop failed")
                    if not await stop_current_recognition():
                        print("[AUDIO] global recognition stop failed; refusing restart")
                        await broadcast_asr_status(force=True)
                        await ws.send_text("ERR:ASR_STOP_FAILED")
                        continue
                    loop = asyncio.get_running_loop()

                    def post(coro):
                        asyncio.run_coroutine_threadsafe(coro, loop)

                    # 组装 ASR 回调（把依赖都注入）
                    cb = ASRCallback(
                        on_sdk_error=lambda s: post(on_sdk_error(s)),
                        post=post,
                        ui_broadcast_partial=ui_broadcast_partial,
                        ui_broadcast_final=ui_broadcast_final,
                        is_playing_now_fn=is_playing_now,
                        start_ai_with_text_fn=start_ai_with_text_custom,  # 使用自定义版本
                        full_system_reset_fn=full_system_reset,
                        interrupt_lock=interrupt_lock,
                    )

                    recognition = dash_audio.asr.Recognition(
                        api_key=API_KEY,
                        model=MODEL,
                        format=AUDIO_FMT,
                        sample_rate=SAMPLE_RATE,
                        callback=cb,
                    )
                    recognition.start()
                    await set_current_recognition(recognition)
                    streaming = True
                    asr_streaming_active = True
                    active_asr_stop_fn = stop_rec
                    last_ts = time.monotonic()
                    keepalive_task = asyncio.create_task(keepalive_loop())
                    await broadcast_asr_status(force=True)
                    await ui_broadcast_partial("（已开始接收音频…）")
                    await ws.send_text("OK:STARTED")

                elif cmd == "STOP":
                    if recognition:
                        for _ in range(15):  # ~300ms 静音
                            try:
                                recognition.send_audio_frame(SILENCE_20MS)
                            except Exception:
                                break
                    if not await stop_rec(send_notice="OK:STOPPED"):
                        print("[AUDIO] recognition stop failed during STOP")
                        await ws.send_text("ERR:STOP_FAILED")

                elif raw.startswith("PROMPT:"):
                    # 设备端主动发起一轮：同样使用“先硬重置后播放”的强语义
                    text = raw[len("PROMPT:") :].strip()
                    if text:
                        async with interrupt_lock:
                            await start_ai_with_text_custom(
                                text
                            )  # 使用自定义的启动函数
                        await ws.send_text("OK:PROMPT_ACCEPTED")
                    else:
                        await ws.send_text("ERR:EMPTY_PROMPT")

            elif "bytes" in msg and msg["bytes"] is not None:
                if streaming and recognition:
                    try:
                        recognition.send_audio_frame(msg["bytes"])
                        last_ts = time.monotonic()
                        esp32_audio_last_frame_at = time.time()
                        await broadcast_asr_status()
                    except Exception:
                        await on_sdk_error("send_audio_frame failed")

    except Exception as e:
        print(f"\n[WS ERROR] {e}")
    finally:
        stop_ok = await stop_rec()
        if not stop_ok:
            print("[WS] recognition stop failed during websocket cleanup")
        try:
            if WebSocketState is None or ws.client_state == WebSocketState.CONNECTED:
                await ws.close(code=1000)
        except Exception:
            pass
        owns_ws = esp32_audio_ws is ws
        if owns_ws:
            esp32_audio_ws = None
            esp32_audio_last_frame_at = 0.0
        if stop_ok and owns_ws and active_asr_stop_fn is stop_rec:
            active_asr_stop_fn = None
        if stop_ok and owns_ws:
            asr_streaming_active = False
            await ui_broadcast_partial("")
            await broadcast_asr_status(force=True)
        print("[WS] connection closed")


# ---------- WebSocket：ESP32 相机入口（JPEG 二进制） ----------
@app.websocket("/ws/camera")
async def ws_camera_esp(ws: WebSocket):
    global \
        esp32_camera_ws, \
        camera_connected_at, \
        camera_last_frame_at, \
        blind_path_navigator, \
        cross_street_navigator, \
        cross_street_active, \
        navigation_active, \
        orchestrator
    async with camera_ws_claim_lock:
        if esp32_camera_ws is not None:
            await ws.close(code=1013)
            return
        await ws.accept()
        esp32_camera_ws = ws
        camera_connected_at = time.time()
        camera_last_frame_at = 0.0
    print("[CAMERA] ESP32 connected")
    await broadcast_camera_status(force=True)
    frame_counter = 0  # 添加帧计数器

    try:
        # 【新增】初始化盲道导航器
        next_blind_path_navigator = blind_path_navigator
        next_cross_street_navigator = cross_street_navigator
        next_orchestrator = orchestrator

        if next_blind_path_navigator is None and yolo_seg_model is not None:
            next_blind_path_navigator = BlindPathNavigator(yolo_seg_model, obstacle_detector)
            print("[NAVIGATION] 盲道导航器已初始化")
        else:
            if next_blind_path_navigator is not None:
                print("[NAVIGATION] 导航器已存在，无需重新初始化")
            elif yolo_seg_model is None:
                print("[NAVIGATION] 警告：YOLO模型未加载，无法初始化导航器")

        # 【新增】初始化过马路导航器
        if next_cross_street_navigator is None:
            if yolo_seg_model:
                next_cross_street_navigator = CrossStreetNavigator(
                    seg_model=yolo_seg_model,
                    coco_model=None,  # 不使用交通灯检测
                    obs_model=None,  # 暂时也不用障碍物检测，让它更快
                )
                print("[CROSS_STREET] 过马路导航器已初始化（简化版 - 仅斑马线检测）")
            else:
                print("[CROSS_STREET] 错误：缺少分割模型，无法初始化过马路导航器")

                if not yolo_seg_model:
                    print("[CROSS_STREET] - 缺少分割模型 (yolo_seg_model)")
                if not obstacle_detector:
                    print("[CROSS_STREET] - 缺少障碍物检测器 (obstacle_detector)")

        if (
            next_orchestrator is None
            and next_blind_path_navigator is not None
            and next_cross_street_navigator is not None
        ):
            next_orchestrator = NavigationMaster(next_blind_path_navigator, next_cross_street_navigator)
            print("[NAV MASTER] 统领状态机已初始化（托管模式）")

        if (
            next_blind_path_navigator is None
            or next_cross_street_navigator is None
            or next_orchestrator is None
        ):
            raise RuntimeError("camera navigation init incomplete")

        blind_path_navigator = next_blind_path_navigator
        cross_street_navigator = next_cross_street_navigator
        orchestrator = next_orchestrator

        while True:
            msg = await ws.receive()
            if "bytes" in msg and msg["bytes"] is not None:
                data = msg["bytes"]
                if camera_last_frame_at <= 0:
                    print(
                        f"[CAMERA] first frame received ({len(data)} bytes)", flush=True
                    )
                camera_last_frame_at = time.time()
                await broadcast_camera_status()
                frame_counter += 1

                # 【新增】录制原始帧
                try:
                    if sync_recorder.record_frame(data) is False:
                        print("[RECORDER] 录制器帧写入失败，已停止当前录制会话")
                except Exception as e:
                    if frame_counter % 100 == 0:  # 避免日志刷屏
                        print(f"[RECORDER] 录制帧失败: {e}")

                try:
                    last_frames.append((time.time(), data))
                except Exception:
                    pass

                # 推送到bridge_io（供yolomedia使用）
                bridge_io.push_raw_jpeg(data)

                # 【调试】检查导航条件
                if frame_counter % 30 == 0:  # 每30帧输出一次
                    state_dbg = orchestrator.get_state() if orchestrator else "N/A"
                    print(
                        f"[NAVIGATION DEBUG] 帧:{frame_counter}, state={state_dbg}, yolomedia_running={yolomedia_running}"
                    )

                # 统一解码（添加更严格的异常处理）
                try:
                    arr = np.frombuffer(data, dtype=np.uint8)
                    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    # 验证解码结果
                    if bgr is None or bgr.size == 0:
                        if frame_counter % 30 == 0:
                            print(f"[JPEG] 解码失败：数据长度={len(data)}")
                        bgr = None
                except Exception as e:
                    if frame_counter % 30 == 0:
                        print(f"[JPEG] 解码异常: {e}")
                    bgr = None

                # 【托管】优先交给统领状态机（寻物未占用画面时）
                # 【修改】找物品模式时不执行导航处理，让yolomedia接管画面
                if orchestrator and not yolomedia_running and bgr is not None:
                    current_state = orchestrator.get_state()

                    # 【新增】找物品模式：不处理画面，等待yolomedia发送处理后的帧
                    if current_state == "ITEM_SEARCH":
                        # 找物品模式下，如果yolomedia还没开始发送帧，先显示原始画面
                        if not yolomedia_sending_frames and camera_viewers:
                            ok, enc = cv2.imencode(
                                ".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                            )
                            if ok:
                                jpeg_data = enc.tobytes()
                                dead = []
                                for viewer_ws in list(camera_viewers):
                                    try:
                                        await viewer_ws.send_bytes(jpeg_data)
                                    except Exception:
                                        dead.append(viewer_ws)
                                for d in dead:
                                    camera_viewers.discard(d)
                        continue  # 跳过后续的导航处理

                    out_img = bgr
                    try:
                        # 【新增】检查是否在红绿灯检测模式
                        if current_state == "TRAFFIC_LIGHT_DETECTION":
                            # 红绿灯检测较重，放到线程里避免阻塞控制命令和UI消息
                            import trafficlight_detection

                            result = await asyncio.to_thread(
                                trafficlight_detection.process_single_frame,
                                bgr,
                                ui_broadcast_callback=ui_broadcast_final,
                            )
                            out_img = (
                                result["vis_image"]
                                if result["vis_image"] is not None
                                else bgr
                            )
                        else:
                            # 导航/过马路处理较重，放到线程里避免卡住 debug_text/停止命令
                            res = await asyncio.to_thread(orchestrator.process_frame, bgr)

                            # 语音引导（内部已节流）
                            # 注：omni对话时已切换到CHAT模式，不会生成导航语音
                            state_after_processing = (
                                orchestrator.get_state() if orchestrator else current_state
                            )
                            if (
                                state_after_processing not in ["CHAT", "IDLE"]
                                and res.guidance_text
                            ):
                                try:
                                    # 先播放语音，再广播到UI
                                    play_voice_text(res.guidance_text)
                                    await ui_broadcast_final(
                                        f"[导航] {res.guidance_text}"
                                    )
                                except Exception:
                                    pass

                            # 输出图像
                            out_img = (
                                res.annotated_image
                                if res.annotated_image is not None
                                else bgr
                            )
                    except Exception as e:
                        if frame_counter % 100 == 0:
                            print(f"[NAV MASTER] 处理帧时出错: {e}")

                    # 广播图像
                    if camera_viewers and out_img is not None:
                        ok, enc = cv2.imencode(
                            ".jpg", out_img, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                        )
                        if ok:
                            jpeg_data = enc.tobytes()
                            dead = []
                            for viewer_ws in list(camera_viewers):
                                try:
                                    await viewer_ws.send_bytes(jpeg_data)
                                except Exception:
                                    dead.append(viewer_ws)
                            for d in dead:
                                camera_viewers.discard(d)
                    # 已托管，进入下一帧
                    continue

                # 【回退】寻物占用或者未解码成功，按原始画面回传
                if not yolomedia_sending_frames and camera_viewers:
                    try:
                        if bgr is None:
                            arr = np.frombuffer(data, dtype=np.uint8)
                            bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if bgr is not None:
                            ok, enc = cv2.imencode(
                                ".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                            )
                            if ok:
                                jpeg_data = enc.tobytes()
                                dead = []
                                for viewer_ws in list(camera_viewers):
                                    try:
                                        await viewer_ws.send_bytes(jpeg_data)
                                    except Exception:
                                        dead.append(viewer_ws)
                                for ws in dead:
                                    camera_viewers.discard(ws)
                    except Exception as e:
                        print(f"[CAMERA] Broadcast error: {e}")

            elif "type" in msg and msg["type"] in (
                "websocket.close",
                "websocket.disconnect",
            ):
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[CAMERA ERROR] {e}")
    finally:
        try:
            if WebSocketState is None or ws.client_state == WebSocketState.CONNECTED:
                await ws.close(code=1000)
        except Exception:
            pass
        owns_ws = esp32_camera_ws is ws
        if owns_ws:
            stop_yolomedia()
            esp32_camera_ws = None
            camera_connected_at = 0.0
            camera_last_frame_at = 0.0
            bridge_io.clear_frames()
            last_frames.clear()
            print("[CAMERA] ESP32 disconnected")
            await broadcast_camera_status(force=True)

            if orchestrator:
                preserved_state = orchestrator.get_state()
                orchestrator.reset_for_camera_reconnect()
                print(f"[NAV MASTER] 相机重连重置完成，保留状态: {preserved_state}")
            else:
                if blind_path_navigator:
                    blind_path_navigator.reset()
                if cross_street_navigator:
                    cross_street_navigator.reset()


# ---------- WebSocket：浏览器订阅相机帧 ----------
@app.websocket("/ws/viewer")
async def ws_viewer(ws: WebSocket):
    await ws.accept()
    camera_viewers.add(ws)
    await broadcast_camera_status(force=True)
    print(
        f"[VIEWER] Browser connected. Total viewers: {len(camera_viewers)}", flush=True
    )
    try:
        while True:
            # 保持连接活跃
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        print("[VIEWER] Browser disconnected", flush=True)
    except asyncio.CancelledError:
        pass
    finally:
        try:
            camera_viewers.remove(ws)
        except Exception:
            pass
        await broadcast_camera_status(force=True)
        print(f"[VIEWER] Removed. Total viewers: {len(camera_viewers)}", flush=True)


# ---------- WebSocket：浏览器订阅 IMU ----------
@app.websocket("/ws")
async def ws_imu(ws: WebSocket):
    await ws.accept()
    imu_ws_clients.add(ws)
    try:
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        imu_ws_clients.discard(ws)


async def imu_broadcast(msg: str):
    if not imu_ws_clients:
        return
    dead = []
    for ws in list(imu_ws_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        imu_ws_clients.discard(ws)


# ---------- 服务端 IMU 估计（原样保留） ----------
from math import atan2, hypot, pi

GRAV_BETA = 0.98
STILL_W = 0.4
YAW_DB = 0.08
YAW_LEAK = 0.2
ANG_EMA = 0.15
AUTO_REZERO = True
USE_PROJ = True
FREEZE_STILL = True
G = 9.807
A_TOL = 0.08 * G
gLP = {"x": 0.0, "y": 0.0, "z": 0.0}
gOff = {"x": 0.0, "y": 0.0, "z": 0.0}
BIAS_ALPHA = 0.002
yaw = 0.0
Rf = Pf = Yf = 0.0
ref = {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}
holdStart = 0.0
isStill = False
last_ts_imu = 0.0
last_wall = 0.0
imu_store: List[Dict[str, Any]] = []

def reset_imu_runtime_state():
    global gLP, gOff, yaw, Rf, Pf, Yf, ref, holdStart, isStill, last_ts_imu, last_wall, imu_store
    gLP = {"x": 0.0, "y": 0.0, "z": 0.0}
    gOff = {"x": 0.0, "y": 0.0, "z": 0.0}
    yaw = 0.0
    Rf = Pf = Yf = 0.0
    ref = {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}
    holdStart = 0.0
    isStill = False
    last_ts_imu = 0.0
    last_wall = 0.0
    imu_store = []


def _wrap180(a: float) -> float:
    a = a % 360.0
    if a >= 180.0:
        a -= 360.0
    if a < -180.0:
        a += 360.0
    return a


def process_imu_and_maybe_store(d: Dict[str, Any]):
    global gLP, gOff, yaw, Rf, Pf, Yf, ref, holdStart, isStill, last_ts_imu, last_wall

    t_ms = float(d.get("ts", 0.0))
    now_wall = time.monotonic()
    if t_ms <= 0.0:
        t_ms = now_wall * 1000.0
    if last_ts_imu <= 0.0 or t_ms <= last_ts_imu or (t_ms - last_ts_imu) > 3000.0:
        dt = 0.02
    else:
        dt = (t_ms - last_ts_imu) / 1000.0
    last_ts_imu = t_ms

    # 原始IMU坐标：x朝前，y朝上，z朝右
    # 统一业务坐标：x朝前，y朝左，z朝上
    ax_raw = float(((d.get("accel") or {}).get("x", 0.0)))
    ay_raw = float(((d.get("accel") or {}).get("y", 0.0)))
    az_raw = float(((d.get("accel") or {}).get("z", 0.0)))
    wx_raw = float(((d.get("gyro") or {}).get("x", 0.0)))
    wy_raw = float(((d.get("gyro") or {}).get("y", 0.0)))
    wz_raw = float(((d.get("gyro") or {}).get("z", 0.0)))

    ax = ax_raw
    ay = -az_raw
    az = ay_raw
    wx = wx_raw
    wy = -wz_raw
    wz = wy_raw

    gLP["x"] = GRAV_BETA * gLP["x"] + (1.0 - GRAV_BETA) * ax
    gLP["y"] = GRAV_BETA * gLP["y"] + (1.0 - GRAV_BETA) * ay
    gLP["z"] = GRAV_BETA * gLP["z"] + (1.0 - GRAV_BETA) * az
    gmag = hypot(gLP["x"], gLP["y"], gLP["z"]) or 1.0
    gHat = {"x": gLP["x"] / gmag, "y": gLP["y"] / gmag, "z": gLP["z"] / gmag}

    # 机体坐标约定：x 朝前，y 朝左，z 朝上
    roll = atan2(ay, az) * 180.0 / pi
    pitch = atan2(-ax, hypot(ay, az)) * 180.0 / pi

    aNorm = hypot(ax, ay, az)
    wNorm = hypot(wx, wy, wz)
    nearFlat = abs(roll) < 2.0 and abs(pitch) < 2.0
    stillCond = (abs(aNorm - G) < A_TOL) and (wNorm < STILL_W)

    if stillCond:
        if holdStart <= 0.0:
            holdStart = t_ms
        if not isStill and (t_ms - holdStart) > 350.0:
            isStill = True
        gOff["x"] = (1.0 - BIAS_ALPHA) * gOff["x"] + BIAS_ALPHA * wx
        gOff["y"] = (1.0 - BIAS_ALPHA) * gOff["y"] + BIAS_ALPHA * wy
        gOff["z"] = (1.0 - BIAS_ALPHA) * gOff["z"] + BIAS_ALPHA * wz
    else:
        holdStart = 0.0
        isStill = False

    if USE_PROJ:
        yawdot = (
            (wx - gOff["x"]) * gHat["x"]
            + (wy - gOff["y"]) * gHat["y"]
            + (wz - gOff["z"]) * gHat["z"]
        )
    else:
        yawdot = wz - gOff["z"]

    if abs(yawdot) < YAW_DB:
        yawdot = 0.0
    if FREEZE_STILL and stillCond:
        yawdot = 0.0

    yaw = _wrap180(yaw + yawdot * dt)

    if (YAW_LEAK > 0.0) and nearFlat and stillCond and abs(yaw) > 0.0:
        step = YAW_LEAK * dt * (-1.0 if yaw > 0 else (1.0 if yaw < 0 else 0.0))
        if abs(yaw) <= abs(step):
            yaw = 0.0
        else:
            yaw += step

    global Rf, Pf, Yf, ref, last_wall
    Rf = ANG_EMA * roll + (1.0 - ANG_EMA) * Rf
    Pf = ANG_EMA * pitch + (1.0 - ANG_EMA) * Pf
    Yf = ANG_EMA * yaw + (1.0 - ANG_EMA) * Yf

    if AUTO_REZERO and nearFlat and (wNorm < STILL_W):
        if holdStart <= 0.0:
            holdStart = t_ms
        if not isStill and (t_ms - holdStart) > 350.0:
            ref.update({"roll": Rf, "pitch": Pf, "yaw": Yf})
            isStill = True

    R = _wrap180(Rf - ref["roll"])
    P = _wrap180(Pf - ref["pitch"])
    Y = _wrap180(Yf - ref["yaw"])

    now_wall = time.monotonic()
    if last_wall <= 0.0 or (now_wall - last_wall) >= 0.100:
        last_wall = now_wall
        item = {
            "ts": t_ms / 1000.0,
            "angles": {"roll": R, "pitch": P, "yaw": Y},
            "accel": {"x": ax, "y": ay, "z": az},
            "gyro": {"x": wx, "y": wy, "z": wz},
        }
        imu_store.append(item)


# ---------- UDP 接收 IMU 并转发 ----------
class UDPProto(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        print(f"[UDP] listening on {UDP_IP}:{UDP_PORT}")

    def datagram_received(self, data, addr):
        try:
            if not imu_accepting_packets:
                return
            s = data.decode("utf-8", errors="ignore").strip()
            d = json.loads(s)
            if "ts" not in d and "timestamp_ms" in d:
                d["ts"] = d.pop("timestamp_ms")
            process_imu_and_maybe_store(d)
            task = asyncio.create_task(imu_broadcast(json.dumps(d)))
            imu_broadcast_tasks.add(task)
            task.add_done_callback(lambda done: imu_broadcast_tasks.discard(done))
        except Exception:
            pass


# === 新增：注册给 bridge_io 的发送回调（把 JPEG 广播给 /ws/viewer） ===
async def on_startup_register_bridge_sender():
    # 保存主线程的事件循环
    main_loop = asyncio.get_event_loop()

    def _sender(jpeg_bytes: bytes):
        # 注意：这个函数可能在非协程线程里被调用，需要切回主事件循环
        try:
            # 检查事件循环状态，避免在关闭时发送
            if main_loop.is_closed():
                return

            # 标记YOLO已经开始发送处理后的帧
            global yolomedia_sending_frames
            if not yolomedia_sending_frames:
                yolomedia_sending_frames = True
                print("[YOLOMEDIA] 开始发送处理后的帧，切换到YOLO画面", flush=True)

            async def _broadcast():
                if not camera_viewers:
                    return
                dead = []
                for ws in list(camera_viewers):
                    try:
                        await ws.send_bytes(jpeg_bytes)
                    except Exception as e:
                        dead.append(ws)
                for ws in dead:
                    try:
                        camera_viewers.remove(ws)
                    except Exception:
                        pass

            # 使用保存的主线程事件循环
            future = asyncio.run_coroutine_threadsafe(_broadcast(), main_loop)
            # 不等待结果，避免阻塞生产线程
        except Exception as e:
            # 只在非预期错误时打印日志
            if "Event loop is closed" not in str(e):
                print(f"[DEBUG] _sender error: {e}", flush=True)

    bridge_io.set_sender(_sender)


async def on_startup():
    global camera_status_task, imu_accepting_packets, imu_transport, esp32_audio_ws, esp32_camera_ws, active_asr_stop_fn, asr_streaming_active, camera_connected_at, camera_last_frame_at, esp32_audio_last_frame_at, blind_path_navigator, cross_street_navigator, orchestrator, yolo_seg_model, obstacle_detector, startup_ready

    async def _close_stale_ws(ws: Optional[WebSocket], code: int = 1001) -> bool:
        if ws is None:
            return True
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.close(code=code)
            return True
        except Exception:
            return False

    startup_state_ok = True
    startup_ready = False
    esp32_audio_last_frame_at = 0.0
    reset_imu_runtime_state()
    if not reset_trafficlight_runtime_state():
        startup_state_ok = False

    pending_imu_tasks = list(imu_broadcast_tasks)
    if pending_imu_tasks:
        done, pending = await asyncio.wait(pending_imu_tasks, timeout=1.0)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        imu_broadcast_tasks.clear()

    if active_asr_stop_fn is not None:
        if not await active_asr_stop_fn():
            startup_state_ok = False
        else:
            active_asr_stop_fn = None
            asr_streaming_active = False

    if esp32_audio_ws is not None:
        if not await _close_stale_ws(esp32_audio_ws):
            startup_state_ok = False
        else:
            esp32_audio_ws = None
    esp32_audio_last_frame_at = 0.0

    if esp32_camera_ws is not None:
        if not await _close_stale_ws(esp32_camera_ws):
            startup_state_ok = False
        else:
            esp32_camera_ws = None
            camera_connected_at = 0.0
            camera_last_frame_at = 0.0

    for ws in list(ui_clients.values()):
        if not await _close_stale_ws(ws):
            startup_state_ok = False
    if startup_state_ok:
        ui_clients.clear()

    for ws in list(camera_viewers):
        if not await _close_stale_ws(ws):
            startup_state_ok = False
    if startup_state_ok:
        camera_viewers.clear()

    for ws in list(imu_ws_clients):
        if not await _close_stale_ws(ws):
            startup_state_ok = False
    if startup_state_ok:
        imu_ws_clients.clear()

    if sync_recorder.stop_recording() is False:
        startup_state_ok = False

    await hard_reset_audio("startup_preflight")
    from audio_stream import current_ai_task as _startup_ai_task, stream_clients as _startup_stream_clients
    if _startup_ai_task is not None or _startup_stream_clients:
        startup_state_ok = False

    if not cleanup_producer_threads():
        startup_state_ok = False

    if not sanitize_audio_system_state():
        startup_state_ok = False

    if not stop_yolomedia():
        startup_state_ok = False

    bridge_io.clear_frames()
    last_frames.clear()
    bump_omni_generation()
    reset_ui_session_state()
    clear_navigation_session_state()
    yolo_seg_model = None
    obstacle_detector = None

    if not startup_state_ok:
        raise RuntimeError("上一次关闭未完全清理，拒绝在同进程内继续启动")

    async def camera_status_watchdog():
        while True:
            try:
                now = time.time()
                stale_camera_ws = esp32_camera_ws
                if stale_camera_ws is not None:
                    first_frame_overdue = (
                        camera_last_frame_at <= 0
                        and camera_connected_at > 0
                        and (now - camera_connected_at) > CAMERA_FIRST_FRAME_TIMEOUT_SEC
                    )
                    stream_stalled = (
                        camera_last_frame_at > 0
                        and (now - camera_last_frame_at) > CAMERA_SOCKET_GRACE_SEC
                    )
                    if first_frame_overdue or stream_stalled:
                        reason = (
                            "no first frame"
                            if first_frame_overdue
                            else "frame stream stalled"
                        )
                        print(
                            f"[CAMERA] closing stale websocket: {reason}",
                            flush=True,
                        )
                        try:
                            if stale_camera_ws.client_state == WebSocketState.CONNECTED:
                                await stale_camera_ws.close(code=1011)
                        except Exception as close_err:
                            print(
                                f"[CAMERA] stale close failed: {close_err}",
                                flush=True,
                            )
                await broadcast_camera_status()
                await broadcast_asr_status()
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                return
            except Exception as e:
                print(f"[CAMERA STATUS] watchdog error: {e}", flush=True)
                await asyncio.sleep(1.0)

    try:
        initialize_audio_system()

        print("[NAVIGATION] 开始加载导航模型...")
        load_navigation_models()
        if yolo_seg_model is None or obstacle_detector is None:
            raise RuntimeError("导航模型未完成加载")
        print(f"[NAVIGATION] 模型加载完成 - yolo_seg_model: {yolo_seg_model is not None}")

        print("[RECORDER] 启动同步录制系统...")
        if not sync_recorder.start_recording():
            raise RuntimeError("同步录制系统启动失败")
        print("[RECORDER] 录制系统已启动，将自动保存视频和音频")

        # 【新增】预加载红绿灯检测模型（避免进入WAIT_TRAFFIC_LIGHT状态时卡顿）
        try:
            import trafficlight_detection

            print("[TRAFFIC_LIGHT] 开始预加载红绿灯检测模型...")
            if trafficlight_detection.init_model():
                print("[TRAFFIC_LIGHT] 红绿灯检测模型预加载成功")
                try:
                    test_img = np.zeros((640, 640, 3), dtype=np.uint8)
                    _ = trafficlight_detection.process_single_frame(test_img)
                    print("[TRAFFIC_LIGHT] 模型预热完成")
                except Exception as e:
                    raise RuntimeError(f"红绿灯模型预热失败: {e}")
            else:
                raise RuntimeError("红绿灯检测模型预加载失败")
        except Exception as e:
            raise RuntimeError(f"红绿灯模型预加载出错: {e}")

        camera_status_task = asyncio.create_task(camera_status_watchdog())
        loop = asyncio.get_running_loop()
        imu_accepting_packets = True
        transport, _ = await loop.create_datagram_endpoint(
            lambda: UDPProto(), local_addr=(UDP_IP, UDP_PORT)
        )
        imu_transport = transport
        startup_ready = True
    except Exception:
        print("[STARTUP] 启动失败，正在回收已初始化资源...", flush=True)
        imu_accepting_packets = False

        if imu_transport is not None:
            try:
                imu_transport.close()
            except Exception:
                pass
            imu_transport = None

        if camera_status_task and not camera_status_task.done():
            camera_status_task.cancel()
            try:
                await camera_status_task
            except asyncio.CancelledError:
                pass
        camera_status_task = None

        bridge_io.set_sender(None)
        bridge_io.clear_frames()
        last_frames.clear()
        reset_imu_runtime_state()
        if not reset_trafficlight_runtime_state():
            print("[STARTUP] 启动失败时红绿灯运行态未完全重置", flush=True)
        reset_ui_session_state()
        clear_navigation_session_state()
        yolo_seg_model = None
        obstacle_detector = None
        await hard_reset_audio("startup_failed")
        audio_shutdown_ok = shutdown_audio_system()
        recorder_shutdown_ok = True
        if audio_shutdown_ok is False:
            print("[STARTUP] 启动失败时音频系统未完全关闭", flush=True)

        try:
            recorder_shutdown_ok = sync_recorder.stop_recording()
            if recorder_shutdown_ok is False:
                print("[STARTUP] 启动失败时录制器未完全关闭", flush=True)
        except Exception as e:
            print(f"[STARTUP] 启动失败时关闭录制器失败: {e}", flush=True)

        if audio_shutdown_ok is False or recorder_shutdown_ok is False:
            print("[STARTUP] 启动失败清理未完成，开始重试一次...", flush=True)
            await hard_reset_audio("startup_failed_retry")
            if shutdown_audio_system() is False:
                print("[STARTUP] 启动失败重试后音频系统仍未完全关闭", flush=True)
            try:
                if sync_recorder.stop_recording() is False:
                    print("[STARTUP] 启动失败重试后录制器仍未完全关闭", flush=True)
            except Exception as e:
                print(f"[STARTUP] 启动失败重试关闭录制器失败: {e}", flush=True)

        raise


async def on_shutdown():
    """应用关闭时的清理工作"""
    global camera_status_task, imu_accepting_packets, imu_transport, esp32_audio_ws, esp32_camera_ws, active_asr_stop_fn, asr_streaming_active, camera_connected_at, camera_last_frame_at, esp32_audio_last_frame_at, blind_path_navigator, cross_street_navigator, orchestrator, yolo_seg_model, obstacle_detector, startup_ready
    print("[SHUTDOWN] 开始清理资源...")
    shutdown_ok = True
    startup_ready = False

    async def _close_ws_client(ws: Optional[WebSocket], code: int = 1001) -> bool:
        if ws is None:
            return True
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.close(code=code)
            return True
        except Exception:
            return False

    async def _retry_failed_cleanup_once() -> bool:
        global active_asr_stop_fn, asr_streaming_active, esp32_audio_last_frame_at, esp32_audio_ws, esp32_camera_ws, camera_connected_at, camera_last_frame_at
        retry_ok = True

        if not reset_trafficlight_runtime_state():
            retry_ok = False

        recognition_retry_ok = True
        if active_asr_stop_fn is not None:
            recognition_retry_ok = await active_asr_stop_fn()
        else:
            recognition_retry_ok = await stop_current_recognition()
            if recognition_retry_ok:
                active_asr_stop_fn = None
                asr_streaming_active = False
                esp32_audio_last_frame_at = 0.0
        if not recognition_retry_ok:
            retry_ok = False

        if esp32_audio_ws is not None:
            if not await _close_ws_client(esp32_audio_ws):
                retry_ok = False
            else:
                esp32_audio_ws = None
                if recognition_retry_ok:
                    active_asr_stop_fn = None
                    asr_streaming_active = False
                esp32_audio_last_frame_at = 0.0

        if esp32_camera_ws is not None:
            if not await _close_ws_client(esp32_camera_ws):
                retry_ok = False
            else:
                esp32_camera_ws = None
                camera_connected_at = 0.0
                camera_last_frame_at = 0.0

        for ws in list(ui_clients.values()):
            if not await _close_ws_client(ws):
                retry_ok = False
            else:
                ui_clients.pop(id(ws), None)

        for ws in list(camera_viewers):
            if not await _close_ws_client(ws):
                retry_ok = False
            else:
                camera_viewers.discard(ws)

        for ws in list(imu_ws_clients):
            if not await _close_ws_client(ws):
                retry_ok = False
            else:
                imu_ws_clients.discard(ws)

        if not stop_yolomedia():
            retry_ok = False

        await hard_reset_audio("shutdown_retry")
        if not cleanup_producer_threads():
            retry_ok = False
        if shutdown_audio_system() is False:
            retry_ok = False

        try:
            if sync_recorder.stop_recording() is False:
                retry_ok = False
        except Exception:
            retry_ok = False

        return retry_ok

    imu_accepting_packets = False
    reset_imu_runtime_state()
    if not reset_trafficlight_runtime_state():
        shutdown_ok = False

    if imu_transport is not None:
        try:
            imu_transport.close()
        except Exception as e:
            print(f"[SHUTDOWN] 关闭 IMU UDP transport 失败: {e}")
        imu_transport = None

    pending_imu_tasks = list(imu_broadcast_tasks)
    if pending_imu_tasks:
        done, pending = await asyncio.wait(pending_imu_tasks, timeout=1.0)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        imu_broadcast_tasks.clear()

    if camera_status_task and not camera_status_task.done():
        camera_status_task.cancel()
        try:
            await camera_status_task
        except asyncio.CancelledError:
            pass
    camera_status_task = None

    recognition_stopped = True
    if active_asr_stop_fn is not None:
        recognition_stopped = await active_asr_stop_fn()
    else:
        recognition_stopped = await stop_current_recognition()
        if recognition_stopped:
            active_asr_stop_fn = None
            asr_streaming_active = False
            esp32_audio_last_frame_at = 0.0
    if not recognition_stopped:
        print("[SHUTDOWN] 停止识别会话失败")
        shutdown_ok = False
    elif esp32_audio_ws is None:
        active_asr_stop_fn = None
        asr_streaming_active = False

    if esp32_audio_ws is not None:
        if not await _close_ws_client(esp32_audio_ws):
            print("[SHUTDOWN] 关闭音频 websocket 失败")
            shutdown_ok = False
        else:
            esp32_audio_ws = None
            if recognition_stopped:
                active_asr_stop_fn = None
                asr_streaming_active = False
    esp32_audio_last_frame_at = 0.0

    if esp32_camera_ws is not None:
        if not await _close_ws_client(esp32_camera_ws):
            print("[SHUTDOWN] 关闭相机 websocket 失败")
            shutdown_ok = False
        else:
            esp32_camera_ws = None
            camera_connected_at = 0.0
            camera_last_frame_at = 0.0

    ui_ws_clients = list(ui_clients.values())
    for ws in ui_ws_clients:
        if not await _close_ws_client(ws):
            shutdown_ok = False
        else:
            ui_clients.pop(id(ws), None)

    viewer_ws_clients = list(camera_viewers)
    for ws in viewer_ws_clients:
        if not await _close_ws_client(ws):
            shutdown_ok = False
        else:
            camera_viewers.discard(ws)

    imu_clients = list(imu_ws_clients)
    for ws in imu_clients:
        if not await _close_ws_client(ws):
            shutdown_ok = False
        else:
            imu_ws_clients.discard(ws)

    # 停止YOLO媒体处理
    if not stop_yolomedia():
        shutdown_ok = False

    bridge_io.set_sender(None)
    bridge_io.clear_frames()
    last_frames.clear()
    bump_omni_generation()
    reset_ui_session_state()
    clear_navigation_session_state()
    yolo_seg_model = None
    obstacle_detector = None

    # 停止音频和AI任务
    await hard_reset_audio("shutdown")
    if not cleanup_producer_threads():
        shutdown_ok = False

    if shutdown_audio_system() is False:
        shutdown_ok = False

    try:
        if sync_recorder.stop_recording() is False:
            shutdown_ok = False
    except Exception as e:
        print(f"[SHUTDOWN] 关闭录制器失败: {e}")
        shutdown_ok = False

    if not shutdown_ok:
        print("[SHUTDOWN] 首次清理未完成，开始重试一次...")
        shutdown_ok = await _retry_failed_cleanup_once()

    if shutdown_ok:
        print("[SHUTDOWN] 资源清理完成")
    else:
        print("[SHUTDOWN] 资源清理未完全完成")


# app_main.py —— 在文件里已有的 @app.on_event("startup") 之后，再加一个新的 startup 钩子


# --- 导出接口（可选） ---
def get_last_frames():
    return last_frames


def get_camera_ws():
    return esp32_camera_ws


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8081,
        log_level="warning",
        access_log=False,
        loop="asyncio",
        workers=1,
        reload=False,
    )
