# 项目结构说明

本文档描述当前仓库中的实际目录结构，以及与传输链路最相关的核心文件。

## 📁 当前目录结构

```text
./
├── app_main.py                 # FastAPI 主入口：ESP32 / 浏览器 WebSocket 与 UDP 路由
├── navigation_master.py        # 导航状态机
├── workflow_blindpath.py       # 盲道导航
├── workflow_crossstreet.py     # 过马路导航
├── yolomedia.py                # 物品查找 / 处理后画面发送
├── asr_core.py                 # DashScope 实时 ASR 回调
├── omni_client.py              # Qwen-Omni 多模态对话
├── audio_player.py             # 多路音频播放
├── audio_stream.py             # /stream.wav HTTP 音频流
├── bridge_io.py                # 原始/处理后画面桥接
├── sync_recorder.py            # 音视频同步录制
├── device_utils.py             # CUDA / MPS / CPU 自动选择
├── templates/
│   └── index.html              # Web 监控界面
├── static/
│   ├── main.js                 # 前端主逻辑：视频、状态、重连、聊天面板
│   ├── vision.js               # 视觉相关前端工具
│   ├── visualizer.js           # IMU 3D 可视化
│   ├── vision_renderer.js      # 渲染器工具
│   ├── vision.css              # 样式
│   └── AGENTS.md               # 前端补充文档
├── compile/
│   ├── compile.ino             # XIAO ESP32S3 Sense 固件主程序
│   ├── camera_pins.h           # 摄像头引脚定义
│   ├── ICM42688.cpp            # IMU 驱动
│   ├── ICM42688.h              # IMU 驱动头文件
│   ├── platformio.ini          # PlatformIO 配置
│   └── AGENTS.md               # 固件补充文档
├── model/                      # 模型文件（需手动下载）
├── music/                      # 系统提示音
├── voice/                      # 预录语音资源
├── README.md
├── CHANGELOG.md
├── AGENTS.md
└── PROJECT_STRUCTURE.md
```

## 🔑 传输相关核心文件

| 文件 | 角色 |
|------|------|
| `app_main.py` | 服务端实时传输中枢：`/ws/camera`、`/ws_audio`、`/ws/viewer`、`/ws_ui`、`/ws`、UDP IMU |
| `audio_stream.py` | 注册 `/stream.wav`，向 ESP32 下发 HTTP WAV 音频流 |
| `compile/compile.ino` | ESP32 端视频/音频/IMU 采集、发送、重连与状态管理 |
| `static/main.js` | 浏览器端视频订阅、状态 badge 更新、自动重连 |
| `templates/index.html` | Web 监控 UI 容器与状态展示 |
| `bridge_io.py` | 原始 JPEG 输入与处理后画面输出桥接 |
| `sync_recorder.py` | 服务端录制原始视频帧与音频 |

## 🔄 当前实时数据流

### 视频上行

```text
ESP32 Camera
  → [JPEG] WebSocket /ws/camera
  → app_main.py
  → bridge_io.push_raw_jpeg()
  → 导航 / yolomedia 处理
  → [JPEG] WebSocket /ws/viewer
  → Browser Canvas
```

### 音频上行

```text
ESP32 Mic
  → [PCM16, 16kHz, mono, 20ms] WebSocket /ws_audio
  → app_main.py
  → DashScope ASR
  → 文本结果 / AI / 导航控制
```

### 音频下行

```text
TTS / AI Reply
  → audio_stream.py
  → [WAV] HTTP /stream.wav
  → ESP32 Speaker
```

### IMU

```text
ESP32 IMU
  → [JSON] UDP 12345
  → process_imu_and_maybe_store()
  → [JSON] WebSocket /ws
  → Browser 3D Visualizer
```

## 📡 当前传输协议分工

| 方向 | 端点 | 协议 | 负载 |
|------|------|------|------|
| ESP32 → 服务端视频 | `/ws/camera` | WebSocket | JPEG |
| ESP32 → 服务端音频 | `/ws_audio` | WebSocket | PCM16 |
| ESP32 → 服务端 IMU | `12345` | UDP | JSON |
| 服务端 → 浏览器视频 | `/ws/viewer` | WebSocket | JPEG |
| 服务端 → 浏览器状态 | `/ws_ui` | WebSocket | 文本前缀协议 + JSON |
| 服务端 → ESP32 音频 | `/stream.wav` | HTTP | WAV |
| 浏览器 → 服务端调试文本 | `/api/debug_text` | HTTP POST | JSON |

## ⚠️ 当前传输链路结论（2026-04）

- 当前 waiting/live 状态跳变主要反映 **ESP32 ⇄ 服务端** 媒体链路波动，而不是浏览器本地性能问题。
- camera 链路中，ESP32 侧连续发送失败 3 次会主动关闭 websocket 并重连。
- audio 链路中，ESP32 侧重连或收到 `RESTART` 后会重新发送 `START`，因此服务端日志可能出现多次 `[AUDIO] START received`。
- 当前仓库音频上行仍是 **裸 PCM**，**没有使用 Opus**。
- 过马路分割与红绿灯 YOLO 路径都已显式接入 `device_utils.DEVICE`，在 Apple Silicon 上会优先尝试 MPS。
- 相机 websocket 断线重连只重置瞬时计数器，不再把导航状态机强制打回默认状态。

## 🚀 启动与调试入口

### 服务端

```bash
uv sync
uv pip install --torch-backend=auto torch torchvision ultralytics "clip @ git+https://github.com/ultralytics/CLIP.git"
uv run python app_main.py
```

说明：默认 `uv sync` 只同步核心依赖；`uv pip --torch-backend=auto` 用于单独安装 PyTorch / Ultralytics / CLIP 这条机器学习栈，避免后续同步把不同机器上的 CUDA / ROCm / CPU 变体覆盖回通用 wheel。macOS 上的 MPS 仍然是运行时自动选择。

### 固件

```bash
uv run pio run --project-dir compile
uv run pio run --project-dir compile --target upload
```

### 重点调试位置

- 服务端：`app_main.py`
  - `ws_camera_esp()`
  - `ws_audio()`
  - `/api/debug_text`
  - `get_camera_status_payload()`
  - `get_asr_status_payload()`
  - `camera_status_watchdog()`
- 固件：`compile/compile.ino`
  - `taskCamSend()`
  - `taskMicUpload()`
  - `wsCam.onEvent(...)`
  - `wsAud.onEvent(...)`
  - `loop()`
- 前端：`static/main.js`
  - `connectCamera()`
  - `connectASR()`
  - `applyCameraStatus()`
  - `applyAsrStatus()`
  - 调试输入框请求逻辑
