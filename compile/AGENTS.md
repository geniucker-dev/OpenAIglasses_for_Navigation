# ESP32固件 (compile/)

## OVERVIEW

ESP32-CAM客户端固件。Arduino框架，负责视频/音频采集、IMU数据、WebSocket通信。

## STRUCTURE

```
compile/
├── compile.ino            # 主程序：setup()/loop()
├── camera_pins.h          # 摄像头引脚定义
├── ICM42688.cpp/h         # IMU驱动（6轴传感器）
└── ESP32_VIDEO_OPTIMIZATION.md  # 性能优化文档
```

## WHERE TO LOOK

| 任务 | 文件 |
|------|------|
| 修改WiFi配置 | `compile.ino` (顶部常量) |
| 摄像头设置 | `compile.ino` → `camera_pins.h` |
| IMU数据读取 | `ICM42688.cpp` |

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

```bash
# Arduino IDE
# 1. 安装ESP32开发板支持
# 2. 选择: ESP32-CAM
# 3. 上传 compile.ino
```

## NOTES

- 需安装ESP32-CAM驱动和Arduino ESP32核心
- 摄像头型号: OV2640
- IMU: ICM42688 (SPI连接)
