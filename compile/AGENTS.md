# ESP32固件 (compile/)

## OVERVIEW

XIAO ESP32S3 Sense 客户端固件。Arduino框架 + PlatformIO构建，负责视频/音频采集、IMU数据、WebSocket通信。

## STRUCTURE

```
compile/
├── compile.ino            # 主程序：setup()/loop()
├── camera_pins.h          # 摄像头引脚定义
├── ICM42688.cpp/h         # IMU驱动（6轴传感器）
├── platformio.ini         # PlatformIO 配置
└── .gitignore             # 忽略 .pio/ 构建目录
```

## HARDWARE

| 组件 | 型号 | 说明 |
|------|------|------|
| 主板 | XIAO ESP32S3 Sense | 8MB PSRAM, 8MB Flash |
| 摄像头 | OV2640/OV3660 | 1600x1200 / 2048x1536 |
| IMU | ICM42688 | SPI连接 |
| 麦克风 | PDM | GPIO41/42 |
| LED | GPIO21 | 用户指示灯 (LOW=ON) |

## LED STATUS INDICATOR

| LED 状态 | 含义 |
|---------|------|
| **灭** | WiFi 未连接 |
| **闪烁** | WiFi 已连接，等待服务器 |
| **常亮** | 服务器已连接（正常工作） |

## WHERE TO LOOK

| 任务 | 文件 |
|------|------|
| 修改WiFi配置 | `compile.ino` (顶部常量 `WIFI_SSID`, `WIFI_PASS`) |
| 修改服务器地址 | `compile.ino` (顶部常量 `SERVER_HOST`, `SERVER_PORT`) |
| 摄像头设置 | `compile.ino` → `camera_pins.h` |
| IMU数据读取 | `ICM42688.cpp` |
| LED状态控制 | `compile.ino` (`STATUS_LED_PIN`, `wifi_connected`, `server_connected`) |

## CONVENTIONS

### 硬编码配置
- WiFi SSID/密码硬编码在 `.ino` 顶部
- 服务器地址/端口硬编码
- **修改后需重新烧录**

### 当前传输端点
- 视频上行: `/ws/camera`（JPEG over WebSocket）
- 音频上行: `/ws_audio`（PCM16 over WebSocket）
- 音频下行: `/stream.wav`（HTTP WAV）
- IMU: UDP端口 `12345`

## BUILD

### 使用 PlatformIO (推荐)

```bash
# 安装 PlatformIO
uv add --dev platformio

# 编译
cd compile && uv run pio run

# 烧录 (连接 ESP32 后)
cd compile && uv run pio run --target upload

# 查看串口日志
screen /dev/tty.usbmodem* 115200
```

### 使用 Arduino IDE

1. 安装 ESP32 开发板支持 (版本 2.0.8+)
2. 选择开发板: `XIAO_ESP32S3`
3. 上传 `compile.ino`

## TROUBLESHOOTING

### 端口找不到
- 按 BOOT 按钮两次进入下载模式
- 检查 USB 线是否支持数据传输

### 编译错误
- 确保使用 `pioarduino/platform-espressif32` 平台
- 检查 `platformio.ini` 配置

### Camera 已连接但网页一直停在 waiting
- 先看串口是否出现 `[WS-CAM] open`，确认 `/ws/camera` 已完成握手
- 再看首帧日志：`[CAM-SEND] first frame sent (...)`
- 若长时间没有首帧，重点看：
  - `[CAM-SEND] WARNING: no first frame within ...`：说明 websocket 已开，但首帧一直没成功送出
  - `[CAM-CAP] captured=..., queue=..., fail=...`：判断是否是 `esp_camera_fb_get()` 采集失败
  - `[CAM-SEND] ERROR: WebSocket send failed ...`：判断是否是大 JPEG 帧发送失败/连接不稳定
- 当前固件已对 camera websocket 操作加串行互斥，避免 `loop()` 中的 `connect/poll` 与发送任务并发访问同一个 `WebsocketsClient`

### ASR 已连接但无语音识别结果
- 检查串口是否出现 `[WS-AUD] open`，确认 `/ws_audio` 已完成握手
- 检查 `run_audio_stream` 标志是否为 true（应在连接成功后自动设置）
- 若音频发送失败，固件会连续重试 3 次后才触发重连，避免偶发抖动
- 当前固件已对音频 websocket 操作加串行互斥 (`aud_ws_mutex`)，避免与 camera 相同的并发访问问题
- 关键变量：
  - `aud_ws_ready`: WebSocket 是否已连接
  - `run_audio_stream`: 是否正在上传音频数据
  - `aud_consecutive_send_fail_count`: 连续发送失败计数（>=3 时触发重连）

### waiting / live 状态框一直跳
- 先确认这通常不是浏览器本地渲染问题，而是 ESP32 ⇄ 服务端链路本身在抖动。
- 相机侧重点检查：
  - `[CAM-SEND] ERROR: WebSocket send failed ...`
  - `[CAM-SEND] ERROR: too many consecutive failures, closing websocket`
  - `[WS-CAM] closed ...` / `[WS-CAM] connected`
- 音频侧重点检查：
  - `[WS-AUD] closed`
  - 服务端是否反复打印 `[AUDIO] START received`
  - 是否收到了服务端发回的 `RESTART`
- 当前代码含义：
  - **camera**：连续 3 次发送失败会主动关闭 websocket 并重连
  - **audio**：连续 3 次发送失败会主动关闭 websocket 并重连；每次重连成功后会重新发送 `START`

## TRANSPORT NOTES

- 当前音频上行是 **16kHz / 16-bit / mono PCM**，并非 Opus。
- 若只看理论最终效果，弱网下视频更适合“允许丢当前帧、不要阻塞后续新帧”的方案；但在 ESP32-S3 级别平台上，协议还要服从资源与实现成熟度。
- 目前最值得额外评估的替代方向是：
  - 视频上行：**MJPEG/HTTP** 或更偏实时语义的 **RTP/UDP**
  - 音频上行：保留 **PCM over WebSocket** 作为现实基线；若未来引入编解码与自适应，再评估 Opus / WebRTC 类方案

## NOTES

- 开发板: Seeed Studio XIAO ESP32S3 Sense
- 摄像头型号: OV2640 或 OV3660
- IMU: ICM42688 (SPI连接)
- 需要 PlatformIO 平台: `https://github.com/pioarduino/platform-espressif32.git`
