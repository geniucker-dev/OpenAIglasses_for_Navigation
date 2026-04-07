# AI智能盲人眼镜系统 (AIGlasses for Navigation)

**Generated:** 2026-04-07
**Commit:** (latest)
**Branch:** main

## OVERVIEW

视障人士智能导航辅助系统。FastAPI后端 + YOLO分割 + MediaPipe手部检测 + 阿里云DashScope语音交互。Python 3.11。

## STRUCTURE

```
./
├── app_main.py              # 主入口：FastAPI + WebSocket路由
├── navigation_master.py     # 导航状态机（IDLE/CHAT/BLINDPATH/CROSSING/ITEM_SEARCH）
├── workflow_blindpath.py    # 盲道导航：YOLO分割 + 光流稳定 + 避障
├── workflow_crossstreet.py  # 过马路：斑马线检测 + 红绿灯识别
├── yolomedia.py             # 物品查找：YOLO-E开放词汇 + MediaPipe手部追踪
├── asr_core.py              # 实时语音识别（DashScope Paraformer）
├── omni_client.py           # Qwen-Omni多模态对话
├── audio_player.py          # 多路音频混音播放
├── device_utils.py          # 设备选择 (CUDA/MPS/CPU)
├── static/                  # 前端JS/CSS（Web监控界面）
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
| 添加语音指令 | `app_main.py` | `start_ai_with_text_custom()` |
| 导航状态切换 | `navigation_master.py` | `NavigationMaster.process_frame()` |
| 盲道检测逻辑 | `workflow_blindpath.py` | `BlindPathNavigator.process_frame()` |
| 过马路逻辑 | `workflow_crossstreet.py` | `CrossStreetNavigator` |
| 物品查找逻辑 | `yolomedia.py` | `main()`, `YOLOEBackend` |
| ASR集成 | `asr_core.py` | `ASRCallback` |
| 音频播放 | `audio_player.py` | `play_voice_text()` |
| 前端界面 | `templates/index.html` → `static/main.js` | - |
| ESP32固件 | `compile/compile.ino` | `setup()`, `loop()` |

## CODE MAP

| 符号 | 类型 | 位置 | 角色 |
|------|------|------|------|
| `NavigationMaster` | Class | navigation_master.py:245 | 状态机统领 |
| `BlindPathNavigator` | Class | workflow_blindpath.py:86 | 盲道导航核心 |
| `TrafficLightDetector` | Class | navigation_master.py:60 | 红绿灯检测 |
| `OrchestratorResult` | Class | navigation_master.py:28 | 导航结果封装 |
| `load_navigation_models` | Func | app_main.py:119 | 模型加载入口 |
| `start_ai_with_text_custom` | Func | app_main.py:410 | 语音指令处理 |
| `ws_camera_esp` | Func | app_main.py:863 | ESP32视频WebSocket |
| `process_imu_and_maybe_store` | Func | app_main.py:1130 | IMU数据处理 |
| `get_device` | Func | device_utils.py:17 | 设备自动选择 |
| `DEVICE` | Var | device_utils.py:94 | 全局设备字符串 |
| `gpu_infer_slot` | Func | device_utils.py:141 | GPU并发限流+AMP |

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

### 启动方式
- **不用** `uvicorn module:app`，直接 `uv run python app_main.py`
- 端口硬编码在 `app_main.py`: `0.0.0.0:8081`
- IMU UDP端口: `12345`

### 模型路径
- 必须存放在 `./model/`:
  - `yolo-seg.pt` (盲道分割)
  - `yoloe-11l-seg.pt` (开放词汇检测)
  - `shoppingbest5.pt` (物品识别)
  - `trafficlight.pt` (红绿灯)
  - `hand_landmarker.task` (MediaPipe手部)
- 环境变量可覆盖: `BLIND_PATH_MODEL`, `YOLOE_MODEL_PATH`, `OBSTACLE_MODEL`

### 环境变量
- **必需**: `DASHSCOPE_API_KEY` (阿里云ASR/Qwen)
- 可选调参: `AIGLASS_MASK_MIN_AREA`, `AIGLASS_PANEL_SCALE`, `AIGLASS_DEVICE`

### 设备选择 (CUDA > MPS > CPU 自动 Fallback)
- 系统自动选择最佳计算设备：CUDA (NVIDIA GPU) > MPS (Apple Silicon) > CPU
- 强制指定设备：设置环境变量 `AIGLASS_DEVICE=cuda` / `mps` / `cpu`
- AMP 自动混合精度：CUDA 支持 bf16/fp16，MPS 支持 fp16
- 配置文件: `device_utils.py`

### 项目特定约定
- 使用 `pyproject.toml` 管理依赖
- **无** lint/format配置
- 测试为根目录 `test_*.py` 脚本（直接 `uv run python test_xxx.py`）

## ANTI-PATTERNS

- `workflow_blindpath.py:292` 有未完成的 `TODO` (YOLO红绿灯解析)，相邻有裸 `except` + `pass`

## UNIQUE STYLES

### 状态机设计
- `NavigationMaster` 维护全局状态: `IDLE` → `CHAT` / `BLINDPATH_NAV` / `CROSSING` / `TRAFFIC_LIGHT_DETECTION` / `ITEM_SEARCH`
- 每个模式有独立 `workflow_*.py` 实现类

### 光流稳定
- `workflow_blindpath.py` 使用 Lucas-Kanade 光流稳定YOLO分割掩码
- 减少帧间抖动，提高导航连续性

### 多路音频
- `audio_player.py` 支持 TTS语音 / AI回复 / 环境音 同时播放
- 使用 pygame 混音器

## COMMANDS

```bash
# 安装依赖
uv sync

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

- **GPU推荐**: CUDA 11.8+ (Linux/Windows)，macOS 使用 MPS 加速，无 GPU 则自动使用 CPU
- 模型文件需从 ModelScope 下载: https://www.modelscope.cn/models/archifancy/AIGlasses_for_navigation
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
