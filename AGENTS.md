# AI智能盲人眼镜系统 (AIGlasses for Navigation)

**Generated:** 2026-04-09
**Commit:** (latest)
**Branch:** main

> ⚠️ **做任何修改前先看 AGENTS.md**。本项目约定、架构、关键符号、反模式都在这里。修改文件前务必确认 WHERE TO LOOK 和 CODE MAP，避免重复造轮子或破坏既有模式。

## OVERVIEW

视障人士智能导航辅助系统。FastAPI后端 + YOLO分割 + 阿里云DashScope语音交互。Python 3.11。

## STRUCTURE

```
./
├── app_main.py              # 主入口：FastAPI + WebSocket路由
├── navigation_master.py     # 导航状态机（IDLE/CHAT/BLINDPATH/CROSSING）
├── workflow_blindpath.py    # 盲道导航：YOLO分割 + 光流稳定 + 避障
├── workflow_crossstreet.py  # 过马路：斑马线检测 + 红绿灯识别
├── yoloe_backend.py         # NCNN-only YOLOE 兼容后端（运行时不支持文本提示词）
├── obstacle_detector_client.py # NCNN/Vulkan 白名单障碍物检测客户端
├── trafficlight_detection.py # NCNN/Vulkan 红绿灯YOLO检测
├── models.py                # 模型加载统一入口
├── asr_core.py              # 实时语音识别（DashScope Paraformer）
├── audio_player.py          # 多路音频混音播放
├── audio_compressor.py      # 音频压缩
├── audio_stream.py          # /stream.wav HTTP音频流
├── bridge_io.py             # 原始/处理后画面桥接
├── sync_recorder.py         # 音视频同步录制
├── device_utils.py          # 设备选择 (CUDA/ROCm/MPS/CPU) + AMP + GPU并发限流
├── crosswalk_awareness.py   # 斑马线感知
├── utils.py                 # 通用工具函数
├── templates/
│   └── index.html           # Web监控界面（含滚动聊天面板）
├── static/                  # 前端JS/CSS（Web监控界面）
│   ├── main.js              # 前端主逻辑
│   ├── visualizer.js        # IMU 3D可视化
│   ├── vision.css           # 样式
│   └── AGENTS.md            # 前端补充文档
├── compile/                 # ESP32固件（PlatformIO项目）
│   ├── compile.ino          # 主程序
│   ├── platformio.ini       # PlatformIO配置
│   └── AGENTS.md            # 固件详细文档
├── model/                   # YOLO模型文件（需下载）
├── voice/                   # 预录语音资源
└── music/                   # 系统提示音
```

## WHERE TO LOOK

| 任务 | 文件 | 关键符号 |
|------|------|----------|
| 启动服务器 | `app_main.py` | `app`, `on_startup()` |
| 添加语音指令 | `app_main.py` | `handle_command_text()` |
| 导航状态切换 | `navigation_master.py` | `NavigationMaster.process_frame()` |
| 盲道检测逻辑 | `workflow_blindpath.py` | `BlindPathNavigator.process_frame()` |
| 过马路逻辑 | `workflow_crossstreet.py` | `CrossStreetNavigator` |
| ASR集成 | `asr_core.py` | `ASRCallback` |
| 音频播放 | `audio_player.py` | `play_voice_text()` |
| 前端界面 | `templates/index.html` → `static/main.js` | - |
| ESP32固件 | `compile/compile.ino` | `setup()`, `loop()` |

## CODE MAP

| 符号 | 类型 | 位置 | 角色 |
|------|------|------|------|
| `NavigationMaster` | Class | navigation_master.py:316 | 状态机统领 |
| `BlindPathNavigator` | Class | workflow_blindpath.py:86 | 盲道导航核心 |
| `TrafficLightDetector` | Class | navigation_master.py:69 | 红绿灯检测 |
| `OrchestratorResult` | Class | navigation_master.py:32 | 导航结果封装 |
| `YoloEBackend` | Class | yoloe_backend.py:18 | NCNN-only YOLOE兼容后端 |
| `ObstacleDetectorClient` | Class | obstacle_detector_client.py:16 | NCNN障碍物检测客户端 |
| `load_navigation_models` | Func | app_main.py:137 | 模型加载入口 |
| `handle_command_text` | Func | app_main.py:548 | 语音/调试文本指令处理 |
| `ws_camera_esp` | Func | app_main.py:1120 | ESP32视频WebSocket |
| `process_imu_and_maybe_store` | Func | app_main.py:1449 | IMU数据处理 |
| `get_device` | Func | device_utils.py:24 | 设备自动选择 |
| `DEVICE` | Var | device_utils.py:105 | 全局设备字符串 |
| `IS_ROCM` | Var | device_utils.py:110 | ROCm/AMD GPU标识 |
| `AMP_DTYPE` | Var | device_utils.py:140 | AMP数据类型（bf16/fp16/None） |
| `gpu_infer_slot` | Func | device_utils.py:148 | GPU并发限流+AMP |

### ESP32 固件 (compile/)

| 符号 | 类型 | 位置 | 角色 |
|------|------|------|------|
| `WIFI_SSID` | Const | compile.ino:19 | WiFi名称 |
| `SERVER_HOST` | Const | compile.ino:21 | 服务器地址 |
| `STATUS_LED_PIN` | Const | compile.ino:25 | LED引脚 (GPIO21) |
| `setup()` | Func | compile.ino:875 | 初始化WiFi/摄像头/I2S |
| `loop()` | Func | compile.ino:1015 | WebSocket连接维护 |

## CONVENTIONS

### 环境管理 (uv)
- 使用 `uv` 管理 Python 环境和依赖
- Python 版本: `3.11`
- 虚拟环境: `.venv/` (uv 自动创建)
- PyTorch / Ultralytics / CLIP 仅用于从 `.pt` 离线导出 NCNN；运行时只需 `uv sync`，不要把导出工具链理解成运行时依赖

### 启动方式
- **不用** `uvicorn module:app`，直接 `uv run python app_main.py`
- 端口硬编码在 `app_main.py`: `0.0.0.0:8081`
- IMU UDP端口: `12345`

### 模型路径
- `.pt` 只用于离线导出，运行时视觉推理禁止加载 `.pt`。
- 必须存放在 `./model/`:
  - `yolo-seg.pt` → `yolo-seg_ncnn_model/` (盲道/斑马线分割)
  - `yoloe-11l-seg.pt` → `yoloe-11l-seg_ncnn_model/` (白名单障碍物分割)
  - `trafficlight.pt` → `trafficlight_ncnn_model/` (红绿灯)
- 运行时环境变量默认值: `BLIND_PATH_MODEL=model/yolo-seg_ncnn_model`, `OBSTACLE_MODEL=model/yoloe-11l-seg_ncnn_model`, `TRAFFIC_LIGHT_MODEL=model/trafficlight_ncnn_model`, `YOLOE_MODEL_PATH=model/yoloe-11l-seg_ncnn_model`。

### 环境变量
- **必需**: `DASHSCOPE_API_KEY` (阿里云ASR)
- NCNN/Vulkan: `AIGLASS_INFER_BACKEND=ncnn`, `AIGLASS_REQUIRE_NCNN=1`；`AIGLASS_NCNN_DEVICE` 可选，不设置时使用 `ncnn.get_default_gpu_index()` 自动选择
- 相机尺寸: `AIGLASS_CAMERA_WIDTH=640`, `AIGLASS_CAMERA_HEIGHT=480`, `AIGLASS_NCNN_IMGSZ=480,640`
- 可选调参: `AIGLASS_MASK_MIN_AREA`, `AIGLASS_PANEL_SCALE`

### 设备选择 (视觉运行时 NCNN/Vulkan)
- 本地视觉推理运行时只走 Ultralytics NCNN runtime；未设置 `AIGLASS_NCNN_DEVICE` 时使用 `ncnn.get_default_gpu_index()`，也可用 `AIGLASS_NCNN_DEVICE=vulkan:N` 手动覆盖。
- 不允许 PyTorch fallback；若 `_ncnn_model/` 缺失、路径配置为 `.pt`、Vulkan 推理失败或输出缺必要字段，直接报错。
- `AIGLASS_DEVICE`、`device_utils.py` 的 CUDA/ROCm/MPS/CPU 逻辑仅保留给离线导出或非视觉辅助代码，不参与视觉运行时推理。
- 后端不 resize ESP32 相机帧；默认按 `FRAMESIZE_VGA` 的 `(480, 640)` 导出和推理，分辨率变化必须重新导出 NCNN。

### 项目特定约定
- 使用 `pyproject.toml` 管理依赖
- **无** lint/format配置
- 测试为根目录 `test_*.py` 脚本（直接 `uv run python test_xxx.py`）

## ANTI-PATTERNS

- `workflow_blindpath.py:292` 有未完成的 `TODO` (YOLO红绿灯解析)，相邻有裸 `except` + `pass`

## UNIQUE STYLES

### 状态机设计
- `NavigationMaster` 维护全局状态: `IDLE` → `CHAT` / `BLINDPATH_NAV` / `CROSSING` / `TRAFFIC_LIGHT_DETECTION`
- 每个模式有独立 `workflow_*.py` 实现类

### 光流稳定
- `workflow_blindpath.py` 使用 Lucas-Kanade 光流稳定YOLO分割掩码
- 减少帧间抖动，提高导航连续性

### 多路音频
- `audio_player.py` 支持 TTS语音 / 环境音 播放
- 使用 pygame 混音器

## COMMANDS

```bash
# 安装运行时依赖
uv sync

# 仅在需要从 .pt 重新导出 NCNN 模型时安装导出工具链
uv pip install --torch-backend=auto torch torchvision ultralytics "clip @ git+https://github.com/ultralytics/CLIP.git"

# 导出 NCNN/Vulkan 运行时模型
uv run python scripts/export_ncnn_models.py

# 启动服务
uv run python app_main.py

# ESP32 固件编译
cd compile && uv run pio run

# ESP32 固件烧录
cd compile && uv run pio run --target upload

# ESP32 串口监视
screen /dev/tty.usbmodem* 115200

# Docker
docker compose up --build

# 测试（文件当前不存在于仓库）
uv run python test_cross_street_blindpath.py
uv run python test_traffic_light.py
uv run python test_recorder.py
```

## NOTES

- **NCNN/Vulkan 运行时**: 视觉推理只加载 `*_ncnn_model/`；未设置 `AIGLASS_NCNN_DEVICE` 时使用 `ncnn.get_default_gpu_index()` 自动选择，也可手动设置 `AIGLASS_NCNN_DEVICE=vulkan:N`；不允许 PyTorch fallback。
- **PyTorch / Ultralytics 安装**: 仅在需要从 `.pt` 重新导出 NCNN 模型时执行 `uv pip install --torch-backend=auto torch torchvision ultralytics "clip @ git+https://github.com/ultralytics/CLIP.git"`。
- **Linux 音频构建依赖**: `pyaudio` 需要系统提供 `portaudio.h`；Ubuntu / Debian 可先安装 `portaudio19-dev` 与 `python3-dev`
- 模型文件需从 ModelScope 下载: https://www.modelscope.cn/models/archifancy/AIGlasses_for_navigation
- 下载 `.pt` 后执行 `uv run python scripts/export_ncnn_models.py` 生成运行时 NCNN 模型目录。
- 需手动创建 `.env` 并设置 `DASHSCOPE_API_KEY`
- 测试文件在 `PROJECT_STRUCTURE.md` 中文档化，但实际不在仓库中
- 无CI/CD配置
- **上游仓库缺少 `voice/黄灯.WAV`**：原仓库只有 `黄灯_原始.WAV`，需手动复制：
  ```bash
  cp "voice/黄灯_原始.WAV" "voice/黄灯.WAV"
  ```
  否则启动时会提示 `[AUDIO] 映射文件缺失: voice/黄灯.WAV`

### ESP32 固件

- **开发板**: Seeed Studio XIAO ESP32S3 Sense
- **摄像头**: OV2640 或 OV3660
- **构建系统**: PlatformIO (推荐) 或 Arduino IDE
- **LED状态**: GPIO21 (LOW=ON)
  - 灭 = WiFi 未连接
  - 闪烁 = WiFi 已连接，等待服务器
  - 常亮 = 服务器已连接
- **PlatformIO 平台**: `https://github.com/pioarduino/platform-espressif32.git`
- 详细文档见 `compile/AGENTS.md`

## RECENT FIXES

### 2026-04-09: NCNN 迁移回退 / ROCm 性能修复 / 前端滚动修复

#### 已完成修复
- **NCNN 迁移放弃**：revert 了全部 9 个 NCNN 相关提交，保留纯 PyTorch 推理路径。NCNN 无关的改动（固件服务器地址、ROCm cudnn.benchmark 修复）已单独加回。
- **ROCm MIOpen autotuning 修复**：`device_utils.py` 新增 `IS_ROCM` 标识，ROCm/AMD GPU 上不再开启 `cudnn.benchmark`，避免 MIOpen autotuning 比 NVIDIA cuDNN 慢几个数量级导致的卡顿。
- **前端聊天面板滚动修复**：`templates/index.html` 的 CSS 布局链修复——`.chat` 添加 `max-height`，`#chatContainer` 成为唯一滚动容器，`scrollTop = scrollHeight` 自动滚到底部。最终文本框不再随消息增加无限变长。

#### 代码审查结论
- MPS float64 特殊处理（`yoloe_backend.py:30-38`、`obstacle_detector_client.py:58-67`）正确守卫，仅在 `device == "mps"` 时触发，CUDA 不走。
- CUDA 上所有 `.cpu()` 调用都是推理后 tensor→NumPy 的标准转换，无多余 CPU 回退。
- bf16 使用正确：`AMP_DTYPE` 在 CUDA Ampere+ 上默认 `torch.bfloat16`，由 `gpu_infer_slot()` 的 `torch.amp.autocast` 全局生效；三处 `bfloat16 → float32` 转换（`workflow_blindpath.py:849`、`obstacle_detector_client.py:89,141`）是配套善后，因为 numpy 不支持 bfloat16。

### 2026-04-08: MPS / 状态保留 / 调试入口文档同步

#### 已完成修复
- `workflow_crossstreet.py` 中的 YOLO 包装推理现在显式传 `device=DEVICE`，避免仅依赖 `model.to(...)` 导致实际推理仍落到 CPU。
- `trafficlight_detection.py` 中红绿灯 YOLO 模型加载后会显式 `.to(DEVICE)`，在 Apple Silicon 上可正确跑到 MPS。
- `navigation_master.py` 的 `reset_for_camera_reconnect()` 会保留 `state`、`prev_nav_state_before_search` 和 `prev_target_state`，相机断线重连不再冲掉恢复目标。
- `audio_player.py` 在 `voice/map.zh-CN.json` 缺失、损坏或为空时，会回退为按 `voice/*.wav` 文件名建立基础映射。
- Web 监控页新增调试输入框，对应后端接口 `/api/debug_text`，可直接下发文本指令绕过 ASR 调试。

#### 当前含义
- 用户看到 GPU 占用低、CPU 高时，至少过马路分割和红绿灯检测这两条 YOLO 路径已经显式接入 `device_utils.DEVICE`，后续优先检查的是运行环境的 `AIGLASS_DEVICE` / PyTorch MPS 可用性，而不是这两处业务代码忘记传设备。
- 相机 websocket 的断线重连现在只重置瞬时计数器，不再把导航状态机强制打回默认导航目标。

### 2026-04-07: WebSocket 传输稳定性修复

#### 问题描述
ESP32 端的音频 WebSocket (`wsAud`) 存在与之前 camera 相同的并发访问风险，导致音频上传不稳定。同时，浏览器端的视频和状态 WebSocket 断开后不会自动重连，需要手动点击"重连"按钮。

#### 根本原因
1. **嵌入式端**: ArduinoWebsockets 库不是线程安全的，`wsAud` 被多个 FreeRTOS 任务/回调并发访问：
   - `taskMicUpload()` 调用 `sendBinary()`
   - `loop()` 调用 `connect()` 和 `poll()`
   - `onMessage()` 回调中调用 `send("START")`
   
2. **前端**: `static/main.js` 中 `/ws/viewer` 和 `/ws_ui` 只在 `onclose` 时更新状态，没有重连逻辑。

#### 解决方案

**ESP32 固件 (`compile/compile.ino`)**:
- 新增 `aud_ws_mutex` 互斥量，保护 `wsAud` 的所有访问
- 音频发送失败后连续 3 次才触发重连，避免偶发失败导致频繁断开
- 失败时自动重置 `qAudio` 队列，避免旧数据堆积
- 连接成功后只有 `START` 真正发送成功才启动 `/stream.wav` 播放

**浏览器前端 (`static/main.js`)**:
- `/ws/viewer` 和 `/ws_ui` 断开后自动重连（延迟 1.2 秒）
- 手动重连按钮仍然保留，与自动重连互不冲突
- 重连逻辑轻量，不增加额外性能开销

#### 关键代码位置
- 嵌入式: `compile/compile.ino` 
  - `aud_ws_mutex` (行 84)
  - `lock_aud_ws()`, `unlock_aud_ws()` (行 112-118)
  - `taskMicUpload()` (行 356-386)
  - `loop()` 音频连接逻辑 (行 1167-1195)
- 前端: `static/main.js`
  - `scheduleReconnect()` (行 248-259)
  - `connectCamera()` 重连逻辑 (行 306-312)
  - `connectASR()` 重连逻辑 (行 335-338)

#### 验证状态
- [x] 固件编译成功 (RAM 23.1%, Flash 34.6%)
- [x] 固件烧录成功
- [ ] 待实测验证 ASR 稳定性和前端自动重连效果

## RECENT ANALYSIS

### 2026-04-07: ESP32 ⇄ 服务端传输链路复盘

#### 已确认现状
- 前端状态框（`waiting/live`）的跳变主要是**在显示底层真实传输波动**，不是前端自身渲染瓶颈。
- 在当前使用场景里，浏览器与服务端基本同机，性能瓶颈优先怀疑 **ESP32 ⇄ 服务端** 链路，而不是浏览器 ⇄ 服务端。
- 当前媒体链路是混合传输：
  - 视频上行：`/ws/camera`（JPEG over WebSocket）
  - 音频上行：`/ws_audio`（PCM16 over WebSocket）
  - 音频下行：`/stream.wav`（HTTP WAV）
  - IMU：UDP `12345`

#### 根因排序（当前代码）
1. `compile/compile.ino` 中 camera 上传在 `sendBinary()` 连续失败 3 次后会主动 `close()`，导致服务端反复看到相机断开再重连。
2. `/ws_audio` 链路会在重连或 `RESTART` 后重复发送 `START`，所以日志中会出现多次 `[AUDIO] START received`。
3. `app_main.py` 的状态 watchdog 每 0.5 秒重算一次 camera / asr 状态，前端 `static/main.js` 收到后立即刷新 badge，没有去抖，因此会放大底层抖动的可见性。

#### 协议结论（仅限 ESP32 ⇄ 服务端）
- **当前仓库未使用 Opus**；音频上行是 16kHz PCM16 单声道。
- 若只看最终效果、不考虑实现复杂度，视频上行更偏向 **RTP/UDP**，音频上行更偏向带编解码与自适应能力的方案（如 **WebRTC/Opus**）。
- 若同时考虑 **ESP32-S3** 平台成熟度与工程自然度，最值得额外评估的替代方向是：
  - 视频上行：**MJPEG/HTTP**
  - 音频上行：继续以 **WebSocket / PCM** 作为现实基线
