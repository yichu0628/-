# 流光 Glance Web

这是一个重构后的网页版任务助手：

- 前端：原生 `HTML + CSS + JavaScript`
- 后端：`Node.js + Express`
- 存储：本地 JSON 文件
- 启动方式：统一使用 `start_dev.ps1` 或 `start_dev.sh`

当前网页版本保留并增强了最核心的几块能力：

- 任务池管理：新增、完成、删除
- 任务编辑：支持修改内容、截止时间、优先级
- 搜索筛选：按状态、优先级和关键词快速过滤
- 截图录入：上传截图并生成任务
- 活动流记录：记录最近的关键操作
- 候选任务整理：根据活动流推导后续待办
- 今日日程摘要：根据任务与活动生成轻量安排建议
- 数据导入导出：支持 JSON 备份、恢复、合并导入

## 当前结构

```text
.
├── backend/
│   ├── logger.js
│   ├── server.js
│   ├── store.js
│   └── services/
│       ├── activityService.js
│       ├── insightService.js
│       ├── screenshotService.js
│       ├── stateService.js
│       └── taskService.js
├── data/                    # 运行后自动生成 web-data.json
├── test/
│   └── web_backend.test.js
├── index.html               # 网页前端入口
├── package.json
├── .env.example
├── start_dev.ps1
├── start_dev.sh
└── README.md
```

## 与桌面版的差异

浏览器环境不支持以下桌面特性，因此当前网页版做了等价替换：

- 桌面悬浮窗：改为浏览器管理台页面
- 全局截图热键：改为页面内手动上传截图
- 前台窗口持续监听：改为活动流与手动录入
- 语音助手：当前未迁入网页版本
- MQTT 硬件同步：当前未迁入网页版本

如果后续需要继续迁移，可以在现有 Node.js 后端上继续补：

- OCR / LLM 截图识别
- 浏览器端语音输入
- WebSocket 实时推送
- 用户登录与云端同步

## 启动方式

### Windows

```powershell
./start_dev.ps1
```

### Linux/macOS

```bash
./start_dev.sh
```

脚本会自动执行：

1. `pnpm install`
2. `pnpm start`

默认访问地址：

- [http://localhost:3000](http://localhost:3000)

## 环境变量

参考 `.env.example`：

```env
PORT=3000
GLANCE_DATA_FILE=./data/web-data.json
GLANCE_LLM_API_KEY=your_llm_api_key
GLANCE_TTS_API_KEY=your_tts_api_key
GLANCE_MQTT_BROKER=broker.emqx.io
GLANCE_MQTT_PORT=1883
```

说明：

- `PORT`：Node.js 服务端口
- `GLANCE_DATA_FILE`：本地 JSON 数据文件位置
- 其余历史变量暂时保留，便于后续继续接回原能力

## 云端部署

### 方案 A：推荐，整站直接部署到 Render

这个仓库当前是一个 Node.js + Express 的前后端一体项目：

- `index.html` 和 `demo.html` 由 `backend/server.js` 直接托管
- 前端体验页 `demo.html` 默认请求同域名下的 `/api/*`
- 因此如果你只想最快上线，最稳妥的方式是整个仓库直接部署到 Render

Render 配置建议：

- Build Command：`pnpm install --frozen-lockfile`
- Start Command：`pnpm start`
- 环境变量：至少配置 `GLANCE_DATA_FILE=./data/web-data.json`

部署完成后，可直接访问：

- 首页：`https://你的服务.onrender.com/`
- 体验页：`https://你的服务.onrender.com/demo`

### 方案 B：Vercel 部署前端，Render 部署后端

如果你一定要拆成 Vercel + Render，请按下面方式：

1. 先把后端部署到 Render，确认 `https://你的服务.onrender.com/api/health` 可访问
2. 修改根目录 `config.js`
3. 将 `apiBase` 改成你的 Render 地址，例如 `https://你的服务.onrender.com`
4. 提交并推送代码，Vercel 会自动重新部署静态前端

示例：

```js
window.GLANCE_CONFIG = {
  apiBase: 'https://your-backend.onrender.com',
};
```

说明：

- `index.html` 是展示首页
- `demo.html` 是真实业务页面
- `vercel.json` 已配置为 `cleanUrls`，所以线上可直接访问 `/demo`
- 不要再把所有路径重写到 `index.html`，否则 `demo` 页面和接口链路都会异常

## API 概览

- `GET /api/dashboard`：获取首页完整数据
- `GET /api/tasks`：获取任务列表，支持状态/优先级/关键词过滤
- `POST /api/tasks`：新增任务
- `PATCH /api/tasks/:taskId`：更新任务
- `POST /api/tasks/:taskId/toggle`：切换完成状态
- `POST /api/tasks/clear-completed`：清理已完成任务
- `DELETE /api/tasks/:taskId`：删除任务
- `GET /api/activities`：获取活动流
- `POST /api/activities`：新增活动记录
- `GET /api/candidates`：获取候选任务
- `GET /api/digest`：获取今日日程摘要
- `GET /api/export`：导出全部数据
- `POST /api/import`：导入全部数据
- `POST /api/analyze-screenshot`：录入截图并生成任务

## 自测

```bash
pnpm test
```

## 说明

- 旧的 Python 桌面代码仍保留在仓库中，便于后续逐步迁移。
- 当前截图任务生成仍是启发式版本，优先保证网页链路完整；后续可以把原来的识别能力接入到 `backend/services/screenshotService.js`。
- 后端源码现在统一收拢在 `backend/` 目录下，方便后续继续拆分控制器、服务和数据层。
