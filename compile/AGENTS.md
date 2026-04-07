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

### WebSocket端点
- 视频: `/ws/camera`
- 音频: `/ws_audio`
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

## NOTES

- 开发板: Seeed Studio XIAO ESP32S3 Sense
- 摄像头型号: OV2640 或 OV3660
- IMU: ICM42688 (SPI连接)
- 需要 PlatformIO 平台: `https://github.com/pioarduino/platform-espressif32.git`
