# Web监控前端 (static/)

## OVERVIEW

浏览器实时监控界面。原生JS + Three.js IMU 3D可视化。无构建工具，直接服务静态文件。

## STRUCTURE

```
static/
├── main.js           # 主入口：WebSocket连接、UI更新
├── vision.js         # 视频流：JPEG帧接收、Canvas渲染
├── visualizer.js     # IMU 3D：Three.js姿态渲染
├── vision_renderer.js # 渲染器工具
├── vision.css        # 样式
└── models/           # 3D模型文件（IMU可视化）
```

## WHERE TO LOOK

| 任务 | 文件 |
|------|------|
| WebSocket连接 | `main.js` |
| 视频流渲染 | `vision.js` |
| IMU 3D可视化 | `visualizer.js` |
| 样式修改 | `vision.css` |
| 调试输入框/按钮 | `main.js` + `templates/index.html` |

## CONVENTIONS

- **无** `package.json`，无npm/yarn构建
- 无TypeScript，无ESLint/Prettier
- 直接被 `templates/index.html` 引用: `<script type="module" src="/static/main.js">`

## WEBSOCKET ENDPOINTS

| 端点 | 用途 | 数据格式 |
|------|------|----------|
| `/ws/viewer` | 视频流订阅 | Binary (JPEG) |
| `/ws_ui` | UI状态推送 | JSON |
| `/ws` | IMU数据 | JSON |

## AUTO-RECONNECT

- `/ws/viewer` 和 `/ws_ui` 断开后自动重连（延迟 1.2 秒）
- 手动重连按钮 (`#btnReconnect`) 仍然保留，与自动重连互不冲突
- 重连逻辑位于 `scheduleReconnect()` 函数
- 使用 `camReconnectTimer` 和 `uiReconnectTimer` 避免重复重连

## DEBUG INPUT

- Web 监控页提供调试输入框，可直接向后端 `/api/debug_text` 发送文本指令，绕过 ASR 便于调试状态机。
- 适合验证 `开始过马路`、`停止导航`、`帮我找一下红牛` 这类指令，而不必等待语音识别链路。

## MOBILE LAYOUT

- IMU 面板已从视频覆盖层改为视频下方的独立区域，避免手机端遮挡画面。
- Canvas 渲染按原始宽高比等比缩放，使用留黑边而不是拉伸，避免 4:3 画面在手机端变形。

## STATUS BADGES

- `#camStatus` 与 `#asrStatus` 的文本和颜色都由 `static/main.js` 里的 `applyCameraStatus()` / `applyAsrStatus()` 更新。
- 这两个 badge 主要跟随 `/ws_ui` 推送的 `CAMERA_STATUS:` 和 `ASR_STATUS:`，**不是**直接跟随视频帧本身。
- 因此如果底层 ESP32 ⇄ 服务端媒体链路抖动，即使画面 FPS 看起来改善了，badge 仍可能在 `waiting/live` 之间跳动。

## CHAT PANEL SCROLLING

- AI 回复面板（`#chatContainer`）是唯一滚动容器，`max-height` 由 CSS flex 布局链约束。
- 新消息到达时自动 `scrollTop = scrollHeight` 滚到底部。
- 桌面端 `.chat` 面板 `max-height: calc(100vh - 32px)`，移动端 `max-height: 70vh`。
- 最终文本框不再随消息增加无限变长。
