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
