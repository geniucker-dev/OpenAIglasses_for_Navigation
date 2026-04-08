# 更新日志

本文档记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 新增
- 首次开源发布
- 完整的 GitHub 文档（README, CONTRIBUTING, LICENSE 等）
- Docker 支持
- 环境变量配置模板

### 修改
- 优化了 README 文档结构
- 改进了代码注释
- 更新 README/AGENTS/PROJECT_STRUCTURE，统一当前传输架构说明（WebSocket + HTTP + UDP 混合链路）
- 记录 2026-04 的 ESP32 ⇄ 服务端传输链路复盘与协议评估结论
- 更新 README/AGENTS/static/AGENTS/PROJECT_STRUCTURE，补充调试输入框、MPS 推理、状态保留与语音映射回退说明
- 安装文档改为：默认 `uv sync` 只同步核心依赖，PyTorch / Ultralytics / CLIP 改为用 `uv pip --torch-backend=auto` 单独安装
- 更新 README/AGENTS/PROJECT_STRUCTURE，明确普通 YOLO 需先下载 `.pt` 再导出 `_ncnn_model`，并补充 `uv run yolo export ... format=ncnn` 转换步骤
- `.gitignore` 新增忽略 `model/*_ncnn_model/` 导出产物，避免提交生成的 NCNN 模型目录

### 修复
- 标注文档中过时的安装方式与目录结构描述，改为当前仓库实际状态
- 过马路分割与红绿灯检测文档改为当前 MPS / CPU 自动选择实现
- 标注文档中过时的“macOS 上缺少 GPU 加速支持”描述，改为 Apple Silicon 上支持 MPS
- 同步相机断线重连后状态保持、语音映射回退、前端手机端布局调整等最近修复

## [1.0.0] - 2025-01-XX

### 新增
- 🚶 盲道导航系统
  - 实时盲道检测与分割
  - 智能语音引导
  - 障碍物检测与避障
  - 急转弯检测与提醒
  - 光流稳定算法

- 🚦 过马路辅助
  - 斑马线识别与方向检测
  - 红绿灯颜色识别
  - 对齐引导系统
  - 安全提醒

- 🔍 物品识别与查找
  - YOLO-E 开放词汇检测
  - MediaPipe 手部引导
  - 实时目标追踪
  - 抓取动作检测

- 🎙️ 实时语音交互
  - 阿里云 Paraformer ASR
  - Qwen-Omni-Turbo 多模态对话
  - 智能指令解析
  - 上下文感知

- 📹 视频与音频处理
  - WebSocket 实时推流
  - 音视频同步录制
  - IMU 数据融合
  - 多路音频混音

- 🎨 可视化与交互
  - Web 实时监控界面
  - IMU 3D 可视化
  - 状态面板
  - 中文友好界面

### 技术栈
- FastAPI + WebSocket
- YOLO11 / YOLO-E
- MediaPipe
- PyTorch + CUDA
- OpenCV
- DashScope API

### 已知问题
- [ ] 在低端 GPU 上可能出现卡顿
- [ ] 部分中文字体在 Linux 上显示不正确

---

## 版本说明

### 主版本（Major）
- 不兼容的 API 更改

### 次版本（Minor）
- 向后兼容的新功能

### 修订版本（Patch）
- 向后兼容的问题修复

---

[未发布]: https://github.com/yourusername/aiglass/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yourusername/aiglass/releases/tag/v1.0.0
