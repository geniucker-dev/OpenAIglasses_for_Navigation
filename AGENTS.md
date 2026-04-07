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
