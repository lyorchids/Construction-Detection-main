# 前端开发计划 — 建筑施工现场安全隐患AI识别系统

## 技术栈

| 组件 | 技术 |
|------|------|
| 框架 | Vue 3 + TypeScript |
| 构建工具 | Vite |
| UI 组件库 | Element Plus |
| 状态管理 | Pinia |
| 路由 | Vue Router 4 |
| HTTP 客户端 | Axios |
| 视频播放 | 原生 Canvas + WebSocket |
| 图表 | ECharts |

---

## Step 1: 前端项目初始化

### 目标
搭建 Vue3 + TypeScript 项目骨架。

### 目录结构
```
frontend/
├── public/
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/
│   │   └── index.ts
│   ├── stores/
│   │   ├── index.ts
│   │   └── detection.ts
│   ├── api/
│   │   ├── index.ts           # Axios 实例配置
│   │   ├── upload.ts          # 上传接口
│   │   ├── detection.ts       # 检测接口
│   │   ├── history.ts         # 历史记录接口
│   │   └── report.ts          # 报告接口
│   ├── views/
│   │   ├── Home.vue           # 首页/仪表盘
│   │   ├── Upload.vue         # 上传检测页
│   │   ├── LiveDetect.vue     # 实时检测页
│   │   ├── History.vue        # 历史记录页
│   │   ├── Detail.vue         # 检测详情页
│   │   └── Report.vue         # 报告页
│   ├── components/
│   │   ├── UploadArea.vue     # 文件上传组件
│   │   ├── DetectionCanvas.vue # 检测画面标注组件
│   │   ├── ViolationAlert.vue # 违规弹窗组件
│   │   ├── RecordList.vue     # 记录列表组件
│   │   ├── RecordCard.vue     # 记录卡片组件
│   │   └── ReportViewer.vue   # 报告预览组件
│   ├── types/
│   │   ├── detection.ts       # 检测相关类型
│   │   ├── violation.ts       # 违规相关类型
│   │   └── api.ts             # API 响应类型
│   ├── utils/
│   │   ├── format.ts          # 格式化工具
│   │   └── websocket.ts       # WebSocket 封装
│   └── assets/
│       └── styles/
│           └── main.scss      # 全局样式
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── .env
```

### 依赖清单
```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "axios": "^1.6.0",
    "element-plus": "^2.5.0",
    "@element-plus/icons-vue": "^2.3.0",
    "echarts": "^5.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "typescript": "^5.3.0",
    "vite": "^5.1.0",
    "vue-tsc": "^1.8.0",
    "sass": "^1.70.0"
  }
}
```

### 建议操作
1. 使用 `npm create vite@latest frontend -- --template vue-ts` 创建项目
2. 安装上述依赖
3. 配置 `vite.config.ts`（代理后端 API）
4. 配置 `tsconfig.json`（严格模式）
5. 创建上述目录结构
6. 配置 Vue Router 和 Pinia

### 验证方式
```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173 确认页面正常
```

---

## Step 2: 类型定义与 API 层

### 目标
定义 TypeScript 类型，封装 Axios API 调用。

### 核心类型
```typescript
// types/detection.ts
interface DetectionResult {
  bbox: [number, number, number, number]
  confidence: number
  class_id: number
  class_name: string
}

interface ViolationRecord {
  type: string
  count: number
  bboxes: Array<[number, number, number, number]>
}

interface FrameData {
  type: 'frame'
  frame_number: number
  timestamp: number
  image: string  // base64
  detections: DetectionResult[]
  violations: ViolationRecord[]
}

// types/api.ts
interface DetectionRecord {
  id: number
  filename: string
  file_type: 'image' | 'video'
  detect_time: string
  total_objects: number
  violation_count: number
  duration: number
}

interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
```

### API 封装
```typescript
// api/index.ts
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// api/upload.ts
export function uploadImage(file: File): Promise<{ file_id: number }>
export function uploadVideo(file: File): Promise<{ file_id: number }>

// api/history.ts
export function getRecords(params: PageParams): Promise<PaginatedResponse<DetectionRecord>>
export function getRecordDetail(id: number): Promise<DetectionRecord>
export function getViolations(recordId: number): Promise<ViolationRecord[]>
```

### 建议操作
1. 编写所有类型定义
2. 封装 Axios 实例（拦截器、错误处理）
3. 编写所有 API 调用函数

### 验证方式
- 启动后端，测试 API 调用是否正常
- 使用浏览器 DevTools 确认请求/响应格式正确

---

## Step 3: 文件上传组件

### 目标
实现图片/视频上传界面。

### 组件: `components/UploadArea.vue`

### 功能
- 拖拽上传
- 点击选择文件
- 文件格式校验（jpg/png/mp4/avi）
- 文件大小限制（图片 10MB，视频 200MB）
- 上传进度条
- 上传成功后跳转到检测页

### UI 布局
```
┌─────────────────────────────────┐
│     拖拽文件到此处或点击上传      │
│         📁                      │
│   支持: JPG, PNG, MP4, AVI      │
└─────────────────────────────────┘
```

### 建议操作
1. 使用 Element Plus `el-upload` 组件
2. 实现拖拽和点击上传
3. 添加文件校验
4. 显示上传进度
5. 上传成功后触发检测

### 验证方式
- 上传合法文件，确认成功
- 上传非法格式/超大文件，确认拦截

---

## Step 4: 检测画面标注组件

### 目标
在 Canvas 上绘制检测框和违规标注。

### 组件: `components/DetectionCanvas.vue`

### Props
```typescript
interface Props {
  image: string        // base64 图像
  detections: DetectionResult[]
  violations: ViolationRecord[]
  showLabels: boolean  // 是否显示标签
}
```

### 绘制规则
| 类别 | 框颜色 | 标签 |
|------|--------|------|
| Person | 绿色 | `Person (0.95)` |
| Hardhat | 蓝色 | `Hardhat` |
| NO-Hardhat | 红色 | `⚠ 未戴安全帽` |
| NO-Mask | 橙色 | `⚠ 未戴口罩` |
| NO-Safety Vest | 橙色 | `⚠ 未穿反光背心` |
| Safety Cone | 黄色 | `Safety Cone` |
| machinery | 紫色 | `Machinery` |
| vehicle | 青色 | `Vehicle` |

### 建议操作
1. 使用 Canvas 2D API 绘制
2. 监听 image prop 变化，重绘画面
3. 绘制边界框 + 标签 + 置信度
4. 违规目标使用红色边框 + 警告图标
5. 优化绘制性能（避免频繁重绘）

### 验证方式
- 传入模拟检测数据，确认标注正确显示

---

## Step 5: 违规弹窗组件

### 目标
检测到违规时弹出提醒。

### 组件: `components/ViolationAlert.vue`

### 功能
- 检测到新违规时弹出通知
- 显示违规类型、数量、时间
- 自动消失（5秒）
- 可手动关闭
- 防抖（同一违规不重复弹窗）

### UI 示例
```
┌────────────────────────────┐
│ ⚠️ 检测到安全隐患            │
│ 未戴安全帽: 2 人            │
│ 人员靠近机械: 1 次          │
│ [查看详情] [关闭]           │
└────────────────────────────┘
```

### 建议操作
1. 使用 Element Plus `ElNotification`
2. 实现违规去重逻辑
3. 添加音效提醒（可选）
4. 点击"查看详情"跳转到记录详情

### 验证方式
- 模拟违规数据，确认弹窗正确触发

---

## Step 6: 实时检测页

### 目标
实现视频逐帧检测的实时展示。

### 页面: `views/LiveDetect.vue`

### 功能
- 选择已上传视频或新上传视频
- 建立 WebSocket 连接
- 接收逐帧数据并渲染
- 实时显示检测框和违规标注
- 播放控制（暂停/继续/停止）
- 显示检测统计（帧数、违规数）

### UI 布局
```
┌─────────────────────────────────┬──────────────┐
│                                 │  检测统计     │
│     DetectionCanvas             │  帧号: 120    │
│     (实时渲染)                   │  违规: 3     │
│                                 │  时间: 4.0s  │
│                                 │              │
│                                 │  [暂停]      │
└─────────────────────────────────┴──────────────┘
```

### WebSocket 封装
```typescript
// utils/websocket.ts
class DetectionWebSocket {
  connect(fileId: number): void
  onFrame(callback: (data: FrameData) => void): void
  onError(callback: (error: Event) => void): void
  pause(): void
  resume(): void
  close(): void
}
```

### 建议操作
1. 实现 WebSocket 连接管理
2. 接收 base64 图像并渲染到 Canvas
3. 叠加检测框和违规标注
4. 实现播放控制
5. 处理断线重连

### 验证方式
- 上传视频后点击检测，确认画面实时显示

---

## Step 7: 历史记录页

### 目标
展示检测历史记录，支持筛选和分页。

### 页面: `views/History.vue`

### 功能
- 检测记录列表（表格或卡片）
- 分页
- 按日期范围筛选
- 按违规类型筛选
- 按文件类型筛选
- 点击查看详情
- 删除记录

### 表格列
| 列 | 说明 |
|----|------|
| 文件名 | 原始文件名 |
| 类型 | 图片/视频 |
| 检测时间 | 格式化时间 |
| 目标数 | 检测到的目标总数 |
| 违规数 | 违规数量（红色高亮） |
| 操作 | 查看/删除 |

### 建议操作
1. 使用 Element Plus `el-table` 或 `el-card`
2. 实现分页和筛选
3. 添加加载状态
4. 实现删除确认对话框

### 验证方式
- 确认列表正确显示，分页和筛选正常工作

---

## Step 8: 检测详情页

### 目标
展示单次检测的详细信息。

### 页面: `views/Detail.vue`

### 功能
- 检测基本信息（文件名、时间、类型）
- 图片：显示标注后的检测结果
- 视频：可重新播放 WebSocket 检测或查看预渲染结果
- 违规列表（类型、数量、截图）
- 点击违规截图查看大图

### UI 布局
```
┌─────────────────────────────────┐
│ 检测详情                         │
│ 文件: test.mp4 | 时间: 2024-... │
├─────────────────────────────────┤
│ [检测画面]                       │
├─────────────────────────────────┤
│ 违规记录                         │
│ ┌─────┐ ┌─────┐ ┌─────┐       │
│ │截图1│ │截图2│ │截图3│  ...   │
│ └─────┘ └─────┘ └─────┘       │
└─────────────────────────────────┘
```

### 建议操作
1. 从路由参数获取记录 ID
2. 请求详情 API
3. 渲染检测画面和违规截图
4. 实现截图放大预览

### 验证方式
- 从历史记录点击进入，确认详情正确显示

---

## Step 9: 首页仪表盘

### 目标
展示系统概况和统计图表。

### 页面: `views/Home.vue`

### 内容
- 今日检测次数
- 今日违规总数
- 违规类型分布（饼图）
- 近7天检测趋势（折线图）
- 最近检测记录（列表）

### 建议操作
1. 使用 ECharts 绘制图表
2. 请求统计 API（后端需提供）
3. 响应式布局

### 验证方式
- 确认图表数据正确，布局适配不同屏幕

---

## Step 10: 报告页

### 目标
查看和下载报告。

### 页面: `views/Report.vue`

### 功能
- 选择时间范围
- 选择违规类型
- 点击生成报告
- 显示生成进度
- 下载 DOCX 文件

### UI 布局
```
┌─────────────────────────────────┐
│ 生成安全隐患报告                  │
│ 时间范围: [开始日期] - [结束日期] │
│ 违规类型: [全部 ▼]               │
│              [生成报告]          │
├─────────────────────────────────┤
│ 历史报告列表                     │
│ 报告_2024-01-15.docx  [下载]    │
│ 报告_2024-01-14.docx  [下载]    │
└─────────────────────────────────┘
```

### 建议操作
1. 使用 Element Plus 日期选择器
2. 调用报告生成 API
3. 实现文件下载
4. 显示生成进度

### 验证方式
- 选择时间范围生成报告，确认下载成功

---

## Step 11: 全局状态管理

### 目标
使用 Pinia 管理全局状态。

### Store 设计
```typescript
// stores/detection.ts
interface DetectionState {
  currentRecord: DetectionRecord | null
  isDetecting: boolean
  violations: ViolationRecord[]
  wsConnected: boolean
}
```

### 建议操作
1. 创建 detection store
2. 创建 ui store（侧边栏、主题等）
3. 组件间状态共享

### 验证方式
- 确认跨组件状态同步正确

---

## Step 12: 样式优化与响应式

### 目标
完善 UI 样式，适配不同屏幕。

### 建议操作
1. 定义全局 SCSS 变量（颜色、间距）
2. 实现暗色主题（可选）
3. 响应式布局（移动端适配）
4. 动画过渡效果
5. 加载骨架屏

### 验证方式
- 在不同分辨率下测试页面显示

---

## 执行顺序

```
Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6
  → Step 7 → Step 8 → Step 9 → Step 10 → Step 11 → Step 12
```

每步完成后需确认成功，再继续下一步。
