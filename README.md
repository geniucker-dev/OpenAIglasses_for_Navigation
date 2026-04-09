# AI 智能盲人眼镜系统 🤖👓

<div align="center">

一个面向视障人士的智能导航与辅助系统，集成了盲道导航、过马路辅助、物品识别、实时语音交互等功能。  本项目仅为交流学习使用，请勿直接给视障人群使用。本项目内仅包含代码，模型地址：https://www.modelscope.cn/models/archifancy/AIGlasses_for_navigation  。下载后存放在/model 文件夹

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

### 🔍 物品识别与查找
- **智能物品搜索**：语音指令查找物品（如"帮我找一下红牛"）
- **实时目标追踪**：使用 YOLO-E 开放词汇检测 + ByteTrack 追踪
- **手部引导**：结合 MediaPipe 手部检测，引导用户手部靠近物品
- **抓取检测**：检测手部握持动作，确认物品已拿到
- **多模态反馈**：视觉标注 + 语音引导 + 居中提示

### 🎙️ 实时语音交互
- **语音识别（ASR）**：基于阿里云 DashScope Paraformer 实时语音识别
- **多模态对话**：Qwen-Omni-Turbo 支持图像+文本输入，语音输出
- **智能指令解析**：自动识别导航、查找、对话等不同类型指令
- **上下文感知**：在不同模式下智能过滤无关指令

### 📹 视频与音频处理
- **实时视频流**：ESP32 以 JPEG 帧上传，服务端再分发到浏览器监控界面
- **音视频同步录制**：自动保存带时间戳的录像和音频文件
- **IMU 数据融合**：接收 ESP32 的 IMU 数据，支持姿态估计
- **多路音频混音**：支持系统语音、AI 回复、环境音同时播放

### 🎨 可视化与交互
- **Web 实时监控**：浏览器端实时查看处理后的视频流
- **IMU 3D 可视化**：Three.js 实时渲染设备姿态
- **状态面板**：显示导航状态、检测信息、FPS 等
- **中文友好**：所有界面和语音使用中文，支持自定义字体

## 💻 系统要求

### 硬件要求
- **开发/服务器端**：
  - CPU: Intel i5 或以上（推荐 i7/i9）
  - GPU: 可选。NVIDIA GPU（CUDA）、Apple Silicon（MPS）或纯 CPU 均可运行；如需更高帧率，推荐 RTX 3060 或以上
  - 内存: 8GB RAM（推荐 16GB）
  - 存储: 10GB 可用空间

- **客户端设备**（可选）：
  - Seeed Studio XIAO ESP32S3 Sense（推荐）或其他可运行同类固件的 ESP32-S3 设备
  - 麦克风（用于语音输入）
  - 扬声器/耳机（用于语音输出）

### 软件要求
- **操作系统**: Windows 10/11, Linux (Ubuntu 20.04+), macOS 10.15+
- **Python**: 3.11
- **PyTorch 安装**: 推荐使用 `uv pip --torch-backend=auto` 自动选择 CPU / CUDA / ROCm；macOS 安装后运行时自动使用 MPS（若可用）
- **浏览器**: Chrome 90+, Firefox 88+, Edge 90+（用于 Web 监控）

### API 密钥
- **阿里云 DashScope API Key**（必需）：
  - 用于语音识别（ASR）和 Qwen-Omni 对话
  - 申请地址：https://dashscope.console.aliyun.com/

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/aiglass.git
cd aiglass
```

### 2. 安装依赖

#### 推荐安装方式（uv + PyTorch 自动选择后端）
```bash
uv sync
uv pip install --torch-backend=auto torch torchvision ultralytics "clip @ git+https://github.com/ultralytics/CLIP.git" pnnx
```

说明：

- 默认 `uv sync` ；PyTorch / Ultralytics / CLIP 这条机器学习栈仍需单独安装，避免后续 `uv sync` 把已安装的 CUDA / ROCm / CPU 变体覆盖回通用 wheel。
- `uv pip --torch-backend=auto` 会为当前机器自动选择合适的 PyTorch 安装来源（如 CPU / CUDA / ROCm）。
- macOS / Apple Silicon 不存在单独的 “MPS wheel”；安装 macOS 版 PyTorch 后，程序运行时会自动检测并使用 `mps`。
- 如需 NVIDIA GPU 加速，请先确保本机 CUDA 驱动环境正常，再执行上面的安装命令。
- Linux 若安装 `pyaudio` 失败并提示缺少 `portaudio.h`，请先安装系统依赖，例如 Ubuntu / Debian 使用 `sudo apt install portaudio19-dev python3-dev`。

### 3. 下载模型文件

将以下模型文件放入 `model/` 目录：

| 模型文件 | 用途 | 大小 | 下载链接 |
|---------|------|------|---------|
| `yolo-seg.pt` | 盲道分割 | ~50MB | [待补充] |
| `yoloe-11l-seg.pt` | 开放词汇检测 | ~80MB | [待补充] |
| `shoppingbest5.pt` | 物品识别 | ~30MB | [待补充] |
| `trafficlight.pt` | 红绿灯检测 | ~20MB | [待补充] |
| `hand_landmarker.task` | 手部检测 | ~15MB | [MediaPipe Models](https://developers.google.com/mediapipe/solutions/vision/hand_landmarker#models) |

下载完成后，**这些 YOLO 模型都先保留 `.pt` 原始文件，再按运行模式补充导出需要的 NCNN 目录**。当前分支采用混合方案：障碍物 YOLOE 读取 `yoloe-11l-seg_ncnn_model`，找物 YOLOE 继续读取 `.pt`。

### 4. 配置 API 密钥

创建 `.env` 文件：

```bash
# .env
DASHSCOPE_API_KEY=your_api_key_here
```

或在代码中直接修改（不推荐）：
```python
# app_main.py, line 50
API_KEY = "your_api_key_here"
```

### 5. 补充缺失的音频文件

> **注意**：上游仓库缺少 `voice/黄灯.WAV` 文件，需手动创建：
> ```bash
> cp "voice/黄灯_原始.WAV" "voice/黄灯.WAV"
> ```

### 6. 启动系统

首次启动前，请先完成下文的 **NCNN 转换步骤**。

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
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐         │
│  │ ASR 模块     │  │ Omni 对话   │  │ 音频播放     │         │
│  │ (asr_core)   │  │(omni_client)│  │(audio_player)│         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                               │
│         应用层                                                │
└───────────────────────────────────────────────────────────────┘
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼──────────────┐
│                     导航统领层                                │
│    ┌─────────────────────────────────────────────────┐       │
│    │  NavigationMaster (navigation_master.py)         │       │
│    │  - 状态机：IDLE/CHAT/BLINDPATH_NAV/              │       │
│    │            CROSSING/TRAFFIC_LIGHT/ITEM_SEARCH    │       │
│    │  - 模式切换与协调                                │       │
│    └───┬─────────────────────┬───────────────────┬───┘       │
│        │                     │                   │            │
│   ┌────▼────────┐   ┌────────▼────────┐   ┌─────▼──────┐   │
│   │ 盲道导航     │   │  过马路导航      │   │ 物品查找    │   │
│   │(blindpath)   │   │ (crossstreet)   │   │(yolomedia)  │   │
│   └──────────────┘   └──────────────────┘   └─────────────┘   │
└───────────────────────────────────────────────────────────────┘
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼──────────────┐
│                       模型推理层                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ YOLO 分割     │  │  YOLO-E 检测 │  │ MediaPipe    │       │
│  │ (盲道/斑马线) │  │ (开放词汇)   │  │  (手部检测)   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ 红绿灯检测    │  │ 光流稳定      │                         │
│  │(HSV+YOLO)     │  │(Lucas-Kanade)│                         │
│  └──────────────┘  └──────────────┘                         │
└───────────────────────────────────────────────────────────────┘
          │
┌─────────▼─────────────────────────────────────────────────────┐
│                    外部服务层                                  │
│  ┌──────────────────────────────────────────────┐            │
│  │  阿里云 DashScope API                         │            │
│  │  - Paraformer ASR (实时语音识别)              │            │
│  │  - Qwen-Omni-Turbo (多模态对话)               │            │
│  │  - Qwen-Turbo (标签提取)                      │            │
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
| **物品查找** | `yolomedia.py` | 物品检测、手部引导、抓取确认 |
| **语音识别** | `asr_core.py` | 实时 ASR、VAD、指令解析 |
| **语音合成** | `omni_client.py` | Qwen-Omni 流式语音生成 |
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

#### 物品查找
```
"帮我找一下 [物品名]"       → 启动物品搜索
  示例：
  - "帮我找一下红牛"
  - "找一下AD钙奶"
  - "帮我找矿泉水"
"找到了" / "拿到了"         → 确认找到物品
```

#### 智能对话
```
"帮我看看这是什么"          → 拍照识别
"这个东西能吃吗"            → 物品咨询
任何其他问题                 → AI 对话
```

### 导航状态说明

系统包含以下主要状态（自动切换）：

1. **IDLE** - 空闲状态
   - 等待用户指令
   - 显示原始视频流

2. **CHAT** - 对话模式
   - 与 AI 进行多模态对话
   - 暂停导航功能

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

5. **ITEM_SEARCH** - 物品查找
   - 实时检测目标物品
   - 引导手部靠近
   - 确认抓取

6. **TRAFFIC_LIGHT_DETECTION** - 红绿灯检测
   - 实时检测红绿灯状态
   - 语音播报颜色变化

### Web 监控界面

打开浏览器访问 `http://localhost:8081`，可以看到：

- **实时视频流**：显示处理后的视频，包括导航标注
- **状态面板**：当前模式、检测信息、FPS
- **IMU 可视化**：设备姿态 3D 实时渲染
- **语音识别结果**：显示识别的文字和 AI 回复
- **调试输入框**：可直接向服务端发送文本指令，绕过 ASR 便于调试状态机与语音命令

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
- 过马路分割模型与红绿灯 YOLO 模型现在都会显式使用 `device_utils.DEVICE`；在 Apple Silicon + PyTorch MPS 可用时，会优先跑在 `mps` 上。
- 面向 **ESP32 ⇄ 服务端** 的效果导向分析结论：
  - **视频上行**：若只看最终实时效果，优先考虑 **RTP/UDP**；若同时考虑 ESP32-S3 上的实现成熟度与工程自然度，**MJPEG/HTTP** 是最值得评估的替代方向。
  - **音频上行**：在 ESP32-S3 级别平台上，当前 PCM-over-WebSocket 仍是现实基线；若只看最终效果，带编解码与自适应能力的方案（如 WebRTC/Opus）理论上更优，但当前仓库未实现。

## ⚙️ 配置说明

### 环境变量

创建 `.env` 文件配置以下参数：

```bash
# 阿里云 API
DASHSCOPE_API_KEY=sk-xxxxx

# 设备选择（可选：cuda / mps / cpu）
AIGLASS_DEVICE=mps

# 模型路径（普通 YOLO 默认读取转换后的 NCNN 目录）
BLIND_PATH_MODEL=model/yolo-seg_ncnn_model
OBSTACLE_MODEL=model/yoloe-11l-seg_ncnn_model
YOLOE_MODEL_PATH=model/yoloe-11l-seg.pt
TRAFFIC_LIGHT_MODEL=model/trafficlight_ncnn_model

# NCNN 运行设备（默认 auto：优先 Vulkan，其次 CPU）
AIGLASS_NCNN_DEVICE=auto

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
YOLOE_MODEL_PATH=/your/path/yoloe-11l-seg.pt
TRAFFIC_LIGHT_MODEL=/your/path/trafficlight_ncnn_model
```

如果你已经把普通 YOLO 模型导出成 NCNN，可直接把路径改成导出的目录（通常以 `_ncnn_model` 结尾）：

```bash
BLIND_PATH_MODEL=model/yolo-seg_ncnn_model
TRAFFIC_LIGHT_MODEL=model/trafficlight_ncnn_model
```

说明：

- 现在仓库里的 **普通 YOLO**（如盲道分割、红绿灯检测）默认应指向导出的 NCNN 目录。
- 当前分支采用 **混合 YOLOE 路径**：
  - `OBSTACLE_MODEL` → `model/yoloe-11l-seg_ncnn_model`（障碍物检测，NCNN + Vulkan）
  - `YOLOE_MODEL_PATH` → `model/yoloe-11l-seg.pt`（找物模式，保留开放词汇文本提示词）
- 原因是 YOLOE 导出成 NCNN 后，不再保留运行时文本提示词接口（如 `set_classes` / `get_text_pe`）；因此障碍物检测适合走 NCNN，找物模式则继续保留 Torch 路径。
- 下载到的 `.pt` 文件不要删；它们是后续重新导出 NCNN 的输入模型。
- 普通 YOLO 的 NCNN 推理现在默认会尝试 **Vulkan**，并自动选择最优候选 GPU；如果没有可用 Vulkan 设备，会自动回退到 CPU。
- 如需强制指定 NCNN 设备，可设置 `AIGLASS_NCNN_DEVICE=cpu` 或 `AIGLASS_NCNN_DEVICE=vulkan:0` / `vulkan:1`。

### 导出普通 YOLO 的 NCNN 模型

本仓库运行时要求普通 YOLO 以 **Ultralytics 导出的 `_ncnn_model` 目录** 形式存在，这样 `standard_yolo_backend.py` 才能直接用 `YOLO("..._ncnn_model")` 加载。

在这个仓库里，实际采用的是 Ultralytics 的 `format="ncnn"` 导出入口；它会直接生成本仓库可用的目录结构。

参考：

- NCNN 官方说明：<https://github.com/tencent/ncnn/wiki/use-ncnn-with-pytorch-or-onnx>

先确保基础环境已经按上面的方式准备好：

```bash
uv sync
uv pip install --torch-backend=auto torch torchvision ultralytics "clip @ git+https://github.com/ultralytics/CLIP.git" pnnx
```

然后转换运行时会用到的普通 YOLO 和障碍物 YOLOE：

- `model/yolo-seg.pt` → `model/yolo-seg_ncnn_model`
- `model/trafficlight.pt` → `model/trafficlight_ncnn_model`
- `model/yoloe-11l-seg.pt` → `model/yoloe-11l-seg_ncnn_model`

可以直接用命令行导出，不需要额外写仓库脚本：

如果你更关心**和当前运行时完全兼容的目录结构**，最直接的命令行方式就是用 Ultralytics 自带的 NCNN 导出入口，它会直接生成本仓库可用的 `_ncnn_model` 目录：

```bash
uv run yolo export model=model/yolo-seg.pt format=ncnn imgsz=640
uv run yolo export model=model/trafficlight.pt format=ncnn imgsz=640
uv run yolo export model=model/yoloe-11l-seg.pt format=ncnn imgsz=640
```

导出成功后通常会得到类似目录：

```bash
model/yolo-seg_ncnn_model
model/trafficlight_ncnn_model
model/yoloe-11l-seg_ncnn_model
```

然后把环境变量切到这些目录：

```bash
BLIND_PATH_MODEL=model/yolo-seg_ncnn_model
TRAFFIC_LIGHT_MODEL=model/trafficlight_ncnn_model
```

补充说明：

- 导出目录中应包含 `.param` 和 `.bin` 文件。
- `_ncnn_model` 目录属于导出产物，默认已加入 `.gitignore`，不要直接提交到仓库。
- 如果你的模型对输入尺寸敏感，请用训练/部署时一致的 `--imgsz`。

完整顺序可以概括为：**下载 `.pt` → 执行 `uv run yolo export ... format=ncnn` → 得到 `_ncnn_model` 目录 → 启动 `uv run python app_main.py`**。

补充：

- 运行时普通 YOLO 会优先走 `AIGLASS_NCNN_DEVICE=auto`，也就是优先启用 Vulkan。
- 如果机器上同时有多个 Vulkan 设备，程序会优先选择 NCNN 默认 GPU，并结合设备类型做自动选择。
- 如果 Vulkan 不可用，程序会自动回退到 CPU，不需要单独改代码。

### 语音映射回退

- 默认会读取 `voice/map.zh-CN.json` 建立预录语音映射。
- 如果映射文件缺失、损坏，或读出来为空，系统会回退为按 `voice/*.wav` 文件名建立基础映射。
- 这意味着像 `红灯`、`绿灯`、`黄灯`、`已停止导航。` 这类与文件名一致的固定提示，在映射文件异常时仍可继续播放。

### 调整性能参数

根据硬件性能调整：

```python
# yolomedia.py
HAND_DOWNSCALE = 0.8    # 手部检测降采样（越小越快，精度降低）
HAND_FPS_DIV = 1        # 手部检测抽帧（2=隔帧，3=每3帧）

# workflow_blindpath.py  
FEATURE_PARAMS = dict(
    maxCorners=600,      # 光流特征点数（越少越快）
    qualityLevel=0.001,  # 特征点质量
    minDistance=5        # 特征点最小间距
)
```

## 🛠️ 开发文档

### 添加新的语音指令

1. 在 `app_main.py` 的 `start_ai_with_text_custom()` 函数中添加：

```python
# 检查新指令
if "新指令关键词" in user_text:
    # 执行自定义逻辑
    print("[CUSTOM] 新指令被触发")
    await ui_broadcast_final("[系统] 新功能已启动")
    return
```

2. 如需修改指令过滤规则：

```python
# 修改 allowed_keywords 列表
allowed_keywords = ["帮我看", "帮我找", "你的新关键词"]
```

### 调试文本指令

前端监控页提供调试输入框，也可以直接请求接口：

```bash
curl -X POST http://localhost:8081/api/debug_text \
  -H 'Content-Type: application/json' \
  -d '{"text":"开始过马路"}'
```

适合在不接麦克风或不想等待 ASR 时直接验证状态切换、过马路流程和物品查找入口。

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

2. **查看帧率瓶颈**：

```python
# yolomedia.py
PERF_DEBUG = True  # 打印处理时间
```

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
