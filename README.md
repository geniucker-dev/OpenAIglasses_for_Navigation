# AI 智能盲人眼镜系统 🤖👓

<div align="center">

一个面向视障人士的智能导航与辅助系统，集成了盲道导航、过马路辅助、实时语音交互等功能。  本项目仅为交流学习使用，请勿直接给视障人群使用。本项目内仅包含代码，模型地址：https://www.modelscope.cn/models/archifancy/AIGlasses_for_navigation  。下载后存放在/model 文件夹

[功能特性](#功能特性) • [快速开始](#快速开始) • [系统架构](#系统架构) • [使用说明](#使用说明) • [开发文档](#开发文档)

</div>

---
<img width="2481" height="3508" alt="1" src="https://github.com/user-attachments/assets/e8dec4a6-8fa6-4d94-bd66-4e9864b67daf" />
<img width="2480" height="3508" alt="2" src="https://github.com/user-attachments/assets/bc7d1aac-a9e9-4ef8-9d67-224708d0c9fd" />
<img width="2481" height="3508" alt="4" src="https://github.com/user-attachments/assets/6dd19750-57af-4560-a007-9a7059956b53" />

## 📋 目录

- [功能特性](#功能特性)
- [系统要求](#系统要求)
- [快速开始](#快速开始)
- [系统架构](#系统架构)
- [使用说明](#使用说明)
- [配置说明](#配置说明)
- [开发文档](#开发文档)

## ✨ 功能特性

### 🚶 盲道导航系统
- **实时盲道检测**：基于 YOLO 分割模型实时识别盲道
- **智能语音引导**：提供精准的方向指引（左转、右转、直行等）
- **障碍物检测与避障**：自动识别前方障碍物并规划避障路线
- **转弯检测**：自动识别急转弯并提前提醒
- **光流稳定**：使用 Lucas-Kanade 光流算法稳定掩码，减少抖动

### 🚦 过马路辅助
- **斑马线识别**：实时检测斑马线位置和方向
- **红绿灯识别**：基于颜色和形状的红绿灯状态检测
- **对齐引导**：引导用户对准斑马线中心
- **安全提醒**：绿灯时语音提示可以通行

### 🎙️ 实时语音交互
- **语音识别（ASR）**：基于阿里云 DashScope Paraformer 实时语音识别
- **智能指令解析**：自动识别导航、红绿灯检测等系统指令
- **上下文感知**：在不同模式下智能过滤无关指令

### 📹 视频与音频处理
- **实时视频流**：ESP32 以 JPEG 帧上传，服务端再分发到浏览器监控界面
- **音视频同步录制**：自动保存带时间戳的录像和音频文件
- **IMU 数据融合**：接收 ESP32 的 IMU 数据，支持姿态估计
- **多路音频混音**：支持系统语音和环境音播放

### 🎨 可视化与交互
- **Web 实时监控**：浏览器端实时查看处理后的视频流
- **IMU 3D 可视化**：Three.js 实时渲染设备姿态
- **状态面板**：显示导航状态、检测信息、FPS 等
- **中文友好**：所有界面和语音使用中文，支持自定义字体

## 💻 系统要求

### 硬件要求
- **开发/服务器端**：
  - CPU: Intel i5 或以上（推荐 i7/i9）
  - GPU: 支持 Vulkan 的显卡或集成显卡。视觉推理运行时强制使用 NCNN/Vulkan；未配置设备时使用 `ncnn.get_default_gpu_index()` 自动选择，不回退 PyTorch
  - 内存: 8GB RAM（推荐 16GB）
  - 存储: 10GB 可用空间

- **客户端设备**（可选）：
  - Seeed Studio XIAO ESP32S3 Sense（推荐）或其他可运行同类固件的 ESP32-S3 设备
  - 麦克风（用于语音输入）
  - 扬声器/耳机（用于语音输出）

### 软件要求
- **操作系统**: Windows 10/11, Linux (Ubuntu 20.04+), macOS 10.15+
- **Python**: 3.11
- **NCNN/Vulkan**: 本地视觉推理运行时只加载 `*_ncnn_model/`，未配置设备时使用 `ncnn.get_default_gpu_index()` 自动选择，不支持 PyTorch fallback
- **PyTorch / Ultralytics**: 仅用于离线导出 NCNN 模型；运行时视觉链路不加载 `.pt`
- **浏览器**: Chrome 90+, Firefox 88+, Edge 90+（用于 Web 监控）

### API 密钥
- **阿里云 DashScope API Key**（必需）：
  - 用于语音识别（ASR）
  - 申请地址：https://dashscope.console.aliyun.com/

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/aiglass.git
cd aiglass
```

### 2. 安装依赖

#### 推荐安装方式（NCNN/Vulkan 运行时）
```bash
uv sync
```

如果需要从 `.pt` 重新导出 `*_ncnn_model/`，再额外安装离线导出工具链：

```bash
uv pip install --torch-backend=auto torch torchvision ultralytics "clip @ git+https://github.com/ultralytics/CLIP.git"
```

说明：

- `uv sync` 同步项目核心依赖，其中包含运行时需要的 `ncnn` 和导出需要的 `pnnx`。
- PyTorch / Ultralytics / CLIP 只用于离线导出 `*_ncnn_model/`；视觉运行时不加载 `.pt`，也不做 PyTorch fallback。
- Linux 若安装 `pyaudio` 失败并提示缺少 `portaudio.h`，请先安装系统依赖，例如 Ubuntu / Debian 使用 `sudo apt install portaudio19-dev python3-dev`。

### 3. 下载模型文件

将以下 `.pt` 源模型文件放入 `model/` 目录，并导出 NCNN 模型目录：

| 源模型文件 | 运行时 NCNN 目录 | 用途 | 下载链接 |
|---------|------|------|---------|
| `yolo-seg.pt` | `yolo-seg_ncnn_model/` | 盲道/斑马线分割 | [待补充] |
| `yoloe-11l-seg.pt` | `yoloe-11l-seg_ncnn_model/` | 白名单障碍物分割 | [待补充] |
| `trafficlight.pt` | `trafficlight_ncnn_model/` | 红绿灯检测 | [待补充] |

导出命令：

```bash
uv run python scripts/export_ncnn_models.py
```

默认导出/推理尺寸为 `(480, 640)`，对应 ESP32 固件默认 `FRAMESIZE_VGA`。后端不会额外 resize 相机帧；如果修改相机分辨率，需要同步设置 `AIGLASS_CAMERA_WIDTH`、`AIGLASS_CAMERA_HEIGHT`、`AIGLASS_NCNN_IMGSZ` 并重新导出 NCNN 模型。

### 4. 配置 API 密钥

创建 `.env` 文件：

```bash
# .env
DASHSCOPE_API_KEY=your_api_key_here
AIGLASS_INFER_BACKEND=ncnn
# 默认不设置时使用 ncnn.get_default_gpu_index() 自动选择；需要固定设备时再设置：
# AIGLASS_NCNN_DEVICE=vulkan:0
AIGLASS_REQUIRE_NCNN=1
AIGLASS_CAMERA_WIDTH=640
AIGLASS_CAMERA_HEIGHT=480
AIGLASS_NCNN_IMGSZ=480,640
BLIND_PATH_MODEL=model/yolo-seg_ncnn_model
OBSTACLE_MODEL=model/yoloe-11l-seg_ncnn_model
TRAFFIC_LIGHT_MODEL=model/trafficlight_ncnn_model
```

### 5. 补充缺失的音频文件

> **注意**：上游仓库缺少 `voice/黄灯.WAV` 文件，需手动创建：
> ```bash
> cp "voice/黄灯_原始.WAV" "voice/黄灯.WAV"
> ```

### 6. 启动系统

```bash
uv run python app_main.py
```

系统将在 `http://0.0.0.0:8081` 启动，打开浏览器访问即可看到实时监控界面。

### 7. 连接 ESP32 设备（可选）

如果使用 XIAO ESP32S3 Sense，请：

#### 修改配置
编辑 `compile/compile.ino` 顶部的配置：
```cpp
const char* WIFI_SSID   = "你的WiFi名称";
const char* WIFI_PASS   = "你的WiFi密码";
const char* SERVER_HOST = "服务器IP地址";  // 如 "192.168.1.100" 或 "Mac.lan"
```

#### 烧录固件
```bash
# 安装 PlatformIO
uv add --dev platformio

# 编译并烧录
cd compile
uv run pio run --target upload
```

#### LED 状态指示
| LED 状态 | 含义 |
|---------|------|
| 灭 | WiFi 未连接 |
| 闪烁 | WiFi 已连接，等待服务器 |
| 常亮 | 服务器已连接（正常工作） |

详细文档见 [compile/AGENTS.md](compile/AGENTS.md)

## 🏗️ 系统架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        客户端层                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ XIAO ESP32S3 │  │   浏览器      │  │   移动端      │      │
│  │ (视频/音频/IMU)│ │  (监控界面)   │  │  (语音控制)   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼─────────────┘
│ WS/HTTP/UDP      │ HTTP/WS          │ WebSocket
┌─────────┼──────────────────┼──────────────────┼─────────────┐
│         │                  │                  │              │
│    ┌────▼──────────────────▼──────────────────▼────────┐    │
│    │         FastAPI 主服务 (app_main.py)              │    │
│    │  - WebSocket 路由管理                              │    │
│    │  - 音视频流分发                                     │    │
│    │  - 状态管理与协调                                   │    │
│    └────┬────────────────┬────────────────┬─────────────┘    │
│         │                │                │                  │
│  ┌──────▼──────┐  ┌──────▼──────┐                         │
│  │ ASR 模块     │  │ 音频播放     │                         │
│  │ (asr_core)   │  │(audio_player)│                         │
│  └──────────────┘  └──────────────┘                         │
│                                                               │
│         应用层                                                │
└───────────────────────────────────────────────────────────────┘
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼──────────────┐
│                     导航统领层                                │
│    ┌─────────────────────────────────────────────────┐       │
│    │  NavigationMaster (navigation_master.py)         │       │
│    │  - 状态机：IDLE/CHAT/BLINDPATH_NAV/              │       │
│    │            CROSSING/TRAFFIC_LIGHT                │       │
│    │  - 模式切换与协调                                │       │
│    └───┬─────────────────────┬───────────────────────┘       │
│        │                     │                               │
│   ┌────▼────────┐   ┌────────▼────────┐                      │
│   │ 盲道导航     │   │  过马路导航      │                      │
│   │(blindpath)   │   │ (crossstreet)   │                      │
│   └──────────────┘   └──────────────────┘                    │
└───────────────────────────────────────────────────────────────┘
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼──────────────┐
│                       模型推理层                              │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ NCNN 盲道分割 │  │ NCNN 障碍物   │                         │
│  │ (Vulkan)     │  │ (白名单YOLOE) │                         │
│  └──────────────┘  └──────────────┘                         │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ NCNN红绿灯    │  │ 光流稳定      │                         │
│  │ (Vulkan)     │  │(Lucas-Kanade)│                         │
│  └──────────────┘  └──────────────┘                         │
└───────────────────────────────────────────────────────────────┘
          │
┌─────────▼─────────────────────────────────────────────────────┐
│                    外部服务层                                  │
│  ┌──────────────────────────────────────────────┐            │
│  │  阿里云 DashScope API                         │            │
│  │  - Paraformer ASR (实时语音识别)              │            │
│  └──────────────────────────────────────────────┘            │
└───────────────────────────────────────────────────────────────┘
```

### 核心模块说明

| 模块 | 文件 | 功能 |
|------|------|------|
| **主应用** | `app_main.py` | FastAPI 服务、传输路由、状态协调 |
| **导航统领** | `navigation_master.py` | 状态机管理、模式切换、语音节流 |
| **盲道导航** | `workflow_blindpath.py` | 盲道检测、避障、转弯引导 |
| **过马路导航** | `workflow_crossstreet.py` | 斑马线检测、红绿灯识别、对齐引导 |
| **语音识别** | `asr_core.py` | 实时 ASR、VAD、指令解析 |
| **音频播放** | `audio_player.py` | 多路混音、TTS 播放、音量控制 |
| **视频录制** | `sync_recorder.py` | 音视频同步录制 |
| **桥接 IO** | `bridge_io.py` | 线程安全的帧缓冲与分发 |

## 📖 使用说明

### 语音指令

系统支持以下语音指令（说话时无需唤醒词）：

#### 导航控制
```
"开始导航" / "盲道导航"     → 启动盲道导航
"停止导航" / "结束导航"     → 停止盲道导航
"开始过马路" / "帮我过马路"  → 启动过马路模式
"过马路结束" / "结束过马路"  → 停止过马路模式
```

#### 红绿灯检测
```
"检测红绿灯" / "看红绿灯"   → 启动红绿灯检测
"停止检测" / "停止红绿灯"   → 停止检测
```

### 导航状态说明

系统包含以下主要状态（自动切换）：

1. **IDLE** - 空闲状态
   - 等待用户指令
   - 显示原始视频流

2. **CHAT** - 待机模式（历史状态名）
   - 显示原始视频流
   - 等待语音或调试文本指令

3. **BLINDPATH_NAV** - 盲道导航
   - **ONBOARDING**: 上盲道引导
     - ROTATION: 旋转对准盲道
     - TRANSLATION: 平移至盲道中心
   - **NAVIGATING**: 沿盲道行走
     - 实时方向修正
     - 障碍物检测
   - **MANEUVERING_TURN**: 转弯处理
   - **AVOIDING_OBSTACLE**: 避障

4. **CROSSING** - 过马路模式
   - **SEEKING_CROSSWALK**: 寻找斑马线
   - **WAIT_TRAFFIC_LIGHT**: 等待绿灯
   - **CROSSING**: 过马路中
   - **SEEKING_NEXT_BLINDPATH**: 寻找对面盲道

5. **TRAFFIC_LIGHT_DETECTION** - 红绿灯检测
   - 实时检测红绿灯状态
   - 语音播报颜色变化

### Web 监控界面

打开浏览器访问 `http://localhost:8081`，可以看到：

- **实时视频流**：显示处理后的视频，包括导航标注
- **状态面板**：当前模式、检测信息、FPS
- **IMU 可视化**：设备姿态 3D 实时渲染
- **语音识别结果**：显示识别文本和系统状态消息
- **调试输入框**：可直接向服务端发送文本指令，绕过 ASR 便于调试状态机与语音命令
- **消息面板滚动**：状态消息面板自动滚动到底部，不会随消息增加无限变长

### 实时传输端点

| 端点 | 用途 | 数据格式 |
|------|------|---------|
| `/ws/camera` | ESP32 相机推流 | Binary (JPEG) |
| `/ws/viewer` | 浏览器订阅视频 | Binary (JPEG) |
| `/ws_audio` | ESP32 音频上传 | Binary (PCM16) |
| `/ws_ui` | UI 状态推送 | Text 前缀消息 + JSON 片段 |
| `/ws` | IMU 数据接收 | JSON |
| `/stream.wav` | 音频下载流 | Binary (WAV) |
| `/api/debug_text` | 调试文本指令输入 | JSON POST |

### 当前传输架构说明

- **ESP32 → 服务端视频**：`/ws/camera`，单条 WebSocket 上传 JPEG 帧
- **ESP32 → 服务端音频**：`/ws_audio`，单条 WebSocket 上传 16kHz PCM16 单声道音频
- **ESP32 → 服务端 IMU**：UDP `12345`
- **服务端 → 浏览器视频**：`/ws/viewer`，JPEG 二进制帧
- **服务端 → 浏览器状态**：`/ws_ui`，文本前缀协议（`INIT:`、`CAMERA_STATUS:`、`ASR_STATUS:`、`PARTIAL:`、`FINAL:`）
- **服务端 → ESP32 音频下行**：`/stream.wav`，HTTP WAV 流

### 传输链路现状（2026-04）

- 已修复 `wsAud` 的并发访问风险，并为 `/ws/viewer`、`/ws_ui` 增加自动重连。
- 相机断线重连后，导航状态机会保留原有导航状态，不再因为 camera websocket 重连而被重置回默认状态。
- 当前已确认：前端状态框抖动主要反映 **ESP32 ⇄ 服务端** 媒体链路波动，不是浏览器渲染瓶颈。
- 当前仓库中音频上行仍是 **PCM over WebSocket**，**未使用 Opus**。
- 视觉推理运行时已统一为 **NCNN/Vulkan**，默认加载 `*_ncnn_model/`，未配置设备时使用 `ncnn.get_default_gpu_index()` 自动选择，不回退 PyTorch。
- 面向 **ESP32 ⇄ 服务端** 的效果导向分析结论：
  - **视频上行**：若只看最终实时效果，优先考虑 **RTP/UDP**；若同时考虑 ESP32-S3 上的实现成熟度与工程自然度，**MJPEG/HTTP** 是最值得评估的替代方向。
  - **音频上行**：在 ESP32-S3 级别平台上，当前 PCM-over-WebSocket 仍是现实基线；若只看最终效果，带编解码与自适应能力的方案（如 WebRTC/Opus）理论上更优，但当前仓库未实现。

## ⚙️ 配置说明

### 环境变量

创建 `.env` 文件配置以下参数：

```bash
# 阿里云 API
DASHSCOPE_API_KEY=sk-xxxxx

# 视觉推理：强制 NCNN/Vulkan，不回退 PyTorch
AIGLASS_INFER_BACKEND=ncnn
# 可选：固定 NCNN/Vulkan 设备；不设置时使用 ncnn.get_default_gpu_index() 自动选择
# AIGLASS_NCNN_DEVICE=vulkan:0
AIGLASS_REQUIRE_NCNN=1
AIGLASS_CAMERA_WIDTH=640
AIGLASS_CAMERA_HEIGHT=480
AIGLASS_NCNN_IMGSZ=480,640

# 运行时模型路径必须是 *_ncnn_model 目录
BLIND_PATH_MODEL=model/yolo-seg_ncnn_model
OBSTACLE_MODEL=model/yoloe-11l-seg_ncnn_model
YOLOE_MODEL_PATH=model/yoloe-11l-seg_ncnn_model
TRAFFIC_LIGHT_MODEL=model/trafficlight_ncnn_model

# 导航参数
AIGLASS_MASK_MIN_AREA=1500      # 最小掩码面积
AIGLASS_MASK_MORPH=3            # 形态学核大小
AIGLASS_MASK_MISS_TTL=6         # 掩码丢失容忍帧数
AIGLASS_PANEL_SCALE=0.65        # 数据面板缩放

# 音频配置
TTS_INTERVAL_SEC=1.0            # 语音播报间隔
ENABLE_TTS=true                 # 启用语音播报
```

### 修改模型路径

优先通过环境变量覆盖默认路径，而不是直接改源码：

```bash
BLIND_PATH_MODEL=/your/path/yolo-seg_ncnn_model
OBSTACLE_MODEL=/your/path/yoloe-11l-seg_ncnn_model
YOLOE_MODEL_PATH=/your/path/yoloe-11l-seg_ncnn_model
TRAFFIC_LIGHT_MODEL=/your/path/trafficlight_ncnn_model
```

### 语音映射回退

- 默认会读取 `voice/map.zh-CN.json` 建立预录语音映射。
- 如果映射文件缺失、损坏，或读出来为空，系统会回退为按 `voice/*.wav` 文件名建立基础映射。
- 这意味着像 `红灯`、`绿灯`、`黄灯`、`已停止导航。` 这类与文件名一致的固定提示，在映射文件异常时仍可继续播放。

### 调整性能参数

根据硬件性能调整：

```python
# workflow_blindpath.py  
FEATURE_PARAMS = dict(
    maxCorners=600,      # 光流特征点数（越少越快）
    qualityLevel=0.001,  # 特征点质量
    minDistance=5        # 特征点最小间距
)
```

## 🛠️ 开发文档

### 添加新的语音指令

1. 在 `app_main.py` 的 `handle_command_text()` 函数中添加：

```python
# 检查新指令
if "新指令关键词" in user_text:
    # 执行自定义逻辑
    print("[CUSTOM] 新指令被触发")
    await ui_broadcast_final("[系统] 新功能已启动")
    return
```

### 调试文本指令

前端监控页提供调试输入框，也可以直接请求接口：

```bash
curl -X POST http://localhost:8081/api/debug_text \
  -H 'Content-Type: application/json' \
  -d '{"text":"开始过马路"}'
```

适合在不接麦克风或不想等待 ASR 时直接验证状态切换、过马路流程。

### 扩展导航功能

1. 在 `workflow_blindpath.py` 添加新状态：

```python
# 在 BlindPathNavigator.__init__() 中初始化
self.your_new_state_var = False

# 在 process_frame() 中处理
def process_frame(self, image):
    if self.your_new_state_var:
        # 自定义处理逻辑
        guidance_text = "新状态引导"
    # ...
```

2. 在 `navigation_master.py` 添加状态机状态：

```python
class NavigationMaster:
    def start_your_new_mode(self):
        self.state = "YOUR_NEW_MODE"
        # 初始化逻辑
```

### 集成新模型

1. 创建模型包装类：

```python
# your_model_wrapper.py
class YourModelWrapper:
    def __init__(self, model_path):
        self.model = load_your_model(model_path)
    
    def detect(self, image):
        # 推理逻辑
        return results
```

2. 在 `app_main.py` 中加载：

```python
your_model = YourModelWrapper("model/your_model.pt")
```

3. 在相应的工作流中调用：

```python
results = your_model.detect(image)
```

### 调试技巧

1. **启用详细日志**：

```python
# app_main.py 顶部
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **查看帧率瓶颈**：关注 `workflow_blindpath.py`、`workflow_crossstreet.py` 和 `trafficlight_detection.py` 的单帧处理耗时。

3. **测试单个模块**：

```bash
# 测试盲道导航
python test_cross_street_blindpath.py

# 测试红绿灯检测
python test_traffic_light.py

# 测试录制功能
python test_recorder.py
```





## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件
