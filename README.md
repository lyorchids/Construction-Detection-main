# 🏗️ 施工现场安全隐患检测系统 (Construction Hazard Detection)

基于 YOLO 目标检测的施工现场安全智能监控系统，支持图片/视频上传检测、违规实时分析、AI 智能报告、历史案例库管理等全流程功能。适用于施工现场安全管理人员进行日常巡检、违规记录和安全教育培训。

## ✨ 功能特性

### 🎯 检测识别
  - **目标检测**：基于 YOLO 模型，识别 11 类目标（安全帽、口罩、人员、机械、车辆、锥形桶、电线杆等）
  - **违规判定**：七大违规规则引擎，实时检测 PPE 穿戴、机械/车辆近身、管控区闯入等违规行为
  - **图片检测**：上传单张图片进行检测 + 标注可视化
  - **视频检测**：上传视频文件逐帧检测 + WebSocket 流式推送

### 📊 数据管理
- **检测记录**：记录每次检测的统计信息、违规详情
- **历史查询**：支持按时间、文件类型分页检索所有检测记录
- **统计数据**：首页仪表盘展示总检测次数、违规趋势、违规分布
  
### 📋 案例库管理
- **案例创建**：支持手动创建案例和从检测记录一键生成案例
- **案例分类**：按类型（未戴头盔/危险操作/其他）和严重等级（低/中/高/严重）分类
- **案例编辑**：支持更新案例标题、描述、处置建议、处理过程等
- **案例检索**：按类型/严重等级/关键词筛选
- **种子数据**：系统启动时自动初始化 10 个预设案例

### ⚙️ 检测配置管理
- **配置模板**：支持创建图片/视频两类检测配置模板，预设模型选择、违规规则开关、置信度阈值
- **折叠式配置卡**：图片/视频检测页使用折叠卡片展示配置摘要，展开后可编辑全部参数
- **旧配置兼容**：自动将旧版 `detect_no_safety_vest_or_helmet` 配置迁移为三个独立开关
- **视频专属参数**：检测间隔（0.5-10秒滑条）、保存违规截图开关

### 🎬 视频检测优化
- **ByteTrack 跟踪**：Ultralytics 内置 ByteTrack 为每个目标分配唯一 ID，跨帧持续跟踪
- **每人状态机**：每人的每种违规类型独立状态机（SAFE→WARN→ACTIVE），累计 N 帧后才触发，防止单帧误检
- **违规去重**：同一人同一违规触发后进入 30s 冷却期，不重复记录
- **固定时间间隔检测**：可配置 0.5-10 秒检测间隔，非检测帧复用缓存检测结果（框、多边形持续显示）
- **并行检测**：PPE 和火灾模型串行执行（GPU 并行收益仅 ~9%，实测 55ms 内完成，无需线程复杂度）

### 🤖 AI 智能分析
- **违规报告**：调用 DeepSeek / 通义千问等 AI 模型生成标准违规分析报告
- **报告内容**：基本信息、检测概况、违规详情、安全评估、总体建议
- **单条分析**：对某条检测记录进行深入 AI 分析
- **范围分析**：对指定日期范围内的所有记录进行综合分析

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────┐
│                    Frontend                      │
│              Vue 3 + Element Plus                │
│         Axios ←→ WebSocket ←→ ECharts            │
└──────────────────┬──────────────────────────────┘
                   │ HTTP / WS
┌──────────────────▼──────────────────────────────┐
│                   Backend                        │
│              FastAPI + SQLAlchemy                │
│   ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│   │YOLODetector│ │Danger   │ │  AI Service    │  │
│   │(模型推理)  │ │Detector │ │(违规报告生成)  │  │
│   └──────────┘ └──────────┘ └────────────────┘  │
│   ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│   │CaseService│ │Detection │ │  ReportService │  │
│   │(案例管理) │ │Service   │ │ (Word报告导出) │  │
│   └──────────┘ └──────────┘ └────────────────┘  │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│                 Storage                          │
│  SQLite (detection.db) │ 文件系统 (uploads/)      │
│  ┌────────────┐ ┌───────────┐ ┌──────────────┐  │
│  │检测记录表   │ │违规记录表  │ │ 案例库表      │  │
│  └────────────┘ └───────────┘ └──────────────┘  │
└─────────────────────────────────────────────────┘
```

### 🎬 视频检测架构

```
┌──────────────────────────────────────────────────────────────┐
│                      视频流处理流水线                          │
├──────────────────────────────────────────────────────────────┤
│  帧输入 (每帧读取 + 编码 + WebSocket发送)                     │
│                                                              │
│  ┌──────────────────────────────────────────────────┐       │
│  │  检测门控 (固定时间间隔, 默认1秒)                   │       │
│  │  if time.now - last_detection >= interval:        │       │
│  │    → 执行PPE检测 (36ms) + Fire检测 (18ms)         │       │
│  │    → 更新状态机 + 违规判定                          │       │
│  │    → 更新检测结果缓存                               │       │
│  │  else:                                             │       │
│  │    → 复用缓存结果 (框、多边形持续显示)                │       │
│  └──────────────────────────────────────────────────┘       │
│                          │                                   │
│  ┌───────────────────────▼───────────────────────────┐      │
│  │  每人违规状态机                                    │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐        │      │
│  │  │ Person1  │  │ Person2  │  │ Person3  │  ...    │      │
│  │  │ SAFE→WARN│  │ ACTIVE   │  │ COOLDOWN│        │      │
│  │  │ →ACTIVE  │  │          │  │ →SAFE   │        │      │
│  │  └──────────┘  └──────────┘  └──────────┘        │      │
│  └───────────────────────┬───────────────────────────┘      │
│                          │                                   │
│  ┌───────────────────────▼───────────────────────────┐      │
│  │  输出: 帧数据 (image + cached_detections + violations)  │
│  │  每帧发送至前端 (Canvas持续渲染 + 多边形 + 违规标记)     │
│  └───────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────┘
```

### 检测时序示意 (30fps, 间隔 1s)

```
帧:    1   2   3  ...  30   31   32  ...  60   61   62
时间:  0   33  66  ...  1000 1033 1066 ... 2000 2033 2066 ms
      [===== PPE+Fire检测 =====]   [===== PPE+Fire检测 =====]
      (55ms)                         (55ms)
      ↓ 缓存更新                      ↓ 缓存更新
      [========= 复用缓存检测框 ==========]
      每帧发送 (视频流畅播放, 检测框持续显示)
```

### 性能数据 (GPU: CUDA, 模型: yolo26l + fire_smoke)

| 指标 | 值 |
|------|----|
| PPE 检测耗时 | 36.5ms ±0.7ms |
| Fire 检测耗时 | 18.8ms ±0.6ms |
| 串行总耗时 | 55.3ms ±0.8ms |
| 并行总耗时 (ThreadPoolExecutor) | 50.5ms ±1.4ms |
| 并行收益 | ~9% (GPU CUDA 自动串行化, 收益可忽略) |

### 状态机参数

| 参数 | 值 | 说明 |
|------|----|------|
| `VIOLATION_MIN_FRAMES` | 10 | 连续违规帧数达标后才触发 |
| `RECOVER_FRAMES` | 15 | 连续合规帧数后退出违规状态 |
| `COOLDOWN_SECONDS` | 30 | 同一人同一违规触发后冷却时间 |

## 🛠️ 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| **后端框架** | FastAPI | Python 异步 Web 框架 |
| **数据库** | SQLite + SQLAlchemy 2.0 | ORM + 本地文件存储 |
| **目标检测** | Ultralytics YOLO | 模型推理（YOLO v8/v11） |
| **图像处理** | OpenCV, NumPy | 图像读取、标注绘制 |
| **AI 分析** | OpenAI SDK | DeepSeek / 通义千问等兼容 API |
| **前端框架** | Vue 3 + TypeScript | Composition API |
| **UI 组件** | Element Plus | 表单、表格、弹窗等 |
| **图表** | ECharts 6 | Home 页统计图表 |
| **HTTP** | Axios | 前端请求封装 |
| **构建** | Vite | 开发构建工具 |

## 🚀 快速开始

### 环境要求
- Python 3.9+
- Node.js 18+
- (可选) CUDA 支持的 GPU

### 1. 安装后端

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  (Windows)

# 安装依赖
pip install -r backend/requirements.txt

# 额外依赖（未在 requirements.txt 中）
pip install httpx aiofiles python-docx
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`:

```env
AI_API_KEY=sk-your-api-key              # AI API Key（用于AI分析报告）
AI_BASE_URL=https://api.deepseek.com/v1  # AI API 地址
AI_MODEL=deepseek-chat                    # AI 模型名称
DEVICE=cuda:0                             # 检测设备 (cuda:0 或 cpu)
```

### 3. 下载模型

将 YOLO 模型文件（如 `yolo26l.pt`）放入 `backend/models/` 目录。

### 4. 启动后端

```bash
cd backend
python run.py
```

API 服务启动于 `http://localhost:8000`

### 5. 安装启动前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器启动于 `http://localhost:5173`

> **注意**：`npm run build` 会因 vue-tsc 类型检查报错（预存在文件类型问题），请使用 `npx vite build` 进行生产构建。

## 📖 API 文档

服务启动后访问 `http://localhost:8000/docs` 查看 Swagger 文档。

### 核心 API 一览

#### 上传
| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/v1/upload/image` | 上传图片（jpg/jpeg/png/bmp/webp, ≤10MB） |
| POST | `/api/v1/upload/video` | 上传视频（mp4/avi/mov/mkv/flv, ≤200MB） |

#### 检测
| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/v1/image/detect` | 图片危险检测（返回标注 base64 + 违规列表） |

#### 历史记录
| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/v1/records` | 分页查询检测记录（支持 file_type/start_date/end_date 过滤） |
| GET | `/api/v1/records/{id}` | 单条记录详情 |
| GET | `/api/v1/records/{id}/violations` | 违规列表 |
| DELETE | `/api/v1/records/{id}` | 删除记录 |
| GET | `/api/v1/stats` | 统计数据 |

#### 案例库
| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/v1/cases` | 手动创建案例 |
| POST | `/api/v1/cases/from-record/{id}` | 从检测记录一键生成案例 |
| GET | `/api/v1/cases` | 分页查询案例（支持 case_type/severity/keyword 过滤） |
| GET | `/api/v1/cases/{id}` | 案例详情 |
| PUT | `/api/v1/cases/{id}` | 更新案例 |
| DELETE | `/api/v1/cases/{id}` | 删除案例 |

#### 检测配置
| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/v1/profiles` | 获取所有配置模板（支持 type 过滤） |
| POST | `/api/v1/profiles` | 创建配置模板 |
| GET | `/api/v1/profiles/{id}` | 获取单条配置详情 |
| PUT | `/api/v1/profiles/{id}` | 更新配置模板 |
| DELETE | `/api/v1/profiles/{id}` | 删除配置模板 |

#### 报告
| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/v1/report/generate` | 生成 Word 报告 |
| POST | `/api/v1/report/ai-analysis` | AI 智能分析报告 |
| GET | `/api/v1/report/download/{filename}` | 下载报告文件 |

## 🖥️ 前端页面

| 路由 | 页面 | 功能 |
|------|------|------|
| `/` | Home.vue | 首页统计仪表盘（ECharts 图表） |
| `/image-detect` | ImageDetect.vue | 图片上传与检测 |
| `/video-detect` | VideoDetect.vue | 视频上传与检测（固定间隔 + 缓存框 + 加载动画） |
| `/history` | History.vue | 检测历史记录列表 |
| `/detail/:id` | Detail.vue | 记录详情 + AI 分析 |
| `/cases` | CaseList.vue | 案例库列表（筛选/搜索） |
| `/cases/create` | CaseCreate.vue | 创建案例（手动/从记录） |
| `/cases/:id` | CaseDetail.vue | 案例详情（查看/编辑） |
| `/profiles` | DetectionProfiles.vue | 检测配置模板管理（CRUD） |

## ⚠️ 违规检测规则

| 类型Key | 说明 | 判定逻辑 |
|---------|------|----------|
| `warning_no_hardhat` | 未戴安全帽 | Person 与 NO-Hardhat 高度重叠 |
| `warning_no_mask` | 未戴口罩 | 检测到 NO-Mask 目标 |
| `warning_no_safety_vest` | 未穿反光背心 | Person 与 NO-Safety Vest 高度重叠 |
| `warning_close_to_machinery` | 靠近机械 | Person 与 Machinery 距离过近 |
| `warning_close_to_vehicle` | 靠近车辆 | Person 与 Vehicle 距离过近 |
| `warning_people_in_controlled_area` | 进入锥形桶管控区 | Person 进入 Safety Cone 围成的多边形区域 |
| `warning_people_in_utility_pole_controlled_area` | 进入电线杆管控区 | Person 进入 Utility Pole 的圆形缓冲区 |

### YOLO 类别映射

| ID | 标签 | 说明 |
|----|------|------|
| 0 | Hardhat | 安全帽 |
| 1 | Mask | 口罩 |
| 2 | NO-Hardhat | 未戴安全帽（人头） |
| 3 | NO-Mask | 未戴口罩 |
| 4 | NO-Safety Vest | 未穿反光背心 |
| 5 | Person | 人员 |
| 6 | Safety Cone | 锥形桶 |
| 7 | Safety Vest | 反光背心 |
| 8 | Machinery | 机械设备 |
| 9 | Utility Pole | 电线杆 |
| 10 | Vehicle | 车辆 |

## 💡 AI 分析服务

### 配置 AI

编辑 `backend/.env` 配置 AI 服务：

```env
AI_API_KEY=sk-your-api-key
AI_BASE_URL=https://api.deepseek.com/v1        # DeepSeek
# 或
AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # 阿里云通义千问
AI_MODEL=deepseek-chat                          # 或 qwen3-max 等
```

### 分析报告结构

AI 分析报告包含以下结构化字段：

- **基本信息**：报告编号、时间、文件名、检测类型、检测时长、目标总数
- **检测概况**：违规总数、风险等级、违规率
- **违规详情**：每条违规的类型、数量、首次出现时间、严重等级、描述、整改建议
- **安全评估**：PPE 合规率、近距作业合规率、管控区合规率
- **总体建议**：综合安全建议
- **专家签名**：AI 安全专家署名

## 📁 项目结构

```
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI 路由层
│   │   │   ├── upload.py      # 文件上传
│   │   │   ├── image_detect.py # 图片检测
│   │   │   ├── video_detect.py # 视频检测
│   │   │   ├── history.py     # 历史记录
│   │   │   ├── report.py      # 报告生成
│   │   │   ├── cases.py       # 案例库
│   │   │   └── ws.py          # WebSocket
│   │   ├── core/              # 核心检测引擎
│   │   │   ├── detector.py     # YOLO 模型推理（含内置 ByteTrack 跟踪）
│   │   │   ├── danger_rules.py # 7 大危险判定规则引擎
│   │   │   ├── violation_state.py # 每人违规状态机（SAFE/WARN/ACTIVE/COOLDOWN）
│   │   │   ├── streamer.py    # 视频流检测（固定时间间隔 + 状态机去重 + 结果缓存）
│   │   │   └── annotator.py   # 标注绘制
│   │   ├── models/            # SQLAlchemy 数据模型
│   │   │   ├── detection.py   # 检测记录/违规
│   │   │   └── case.py        # 案例库
│   │   ├── schemas/           # Pydantic 数据模式
│   │   │   ├── detection.py   # 检测相关
│   │   │   └── case.py        # 案例相关
│   │   ├── services/          # 业务逻辑层
│   │   │   ├── detection_service.py  # 检测记录服务
│   │   │   ├── ai_service.py         # AI 分析服务
│   │   │   ├── report_service.py     # Word 报告服务
│   │   │   ├── case_service.py       # 案例库服务
│   │   │   └── seed_cases.py         # 案例种子数据
│   │   ├── config.py          # 配置管理
│   │   ├── database.py        # 数据库连接
│   │   └── main.py            # FastAPI 应用入口
│   ├── uploads/               # 上传文件存储
│   ├── violations/            # 违规截图存储
│   ├── reports/               # 报告文件存储
│   ├── models/                # YOLO 模型文件
│   └── run.py                 # 启动脚本
├── frontend/
│   ├── src/
│   │   ├── views/             # 页面组件
│   │   ├── api/               # API 封装
│   │   ├── router/            # Vue Router 配置
│   │   ├── store/             # Pinia 状态管理
│   │   └── components/        # 公共组件
│   └── package.json
├── docs/
│   └── datasets.md            # 开源数据集推荐
└── README.md
```

## 📦 训练数据

`docs/datasets.md` 收集了针对施工安全场景的 16+ 个开源数据集链接，覆盖：

- 施工安全 PPE 检测
- 火灾/烟雾检测
- 高处坠落检测
- 人员打斗检测

推荐使用 YOLOv11 分别训练两个模型（高分辨率 PPE 检测 + 标准分辨率危险区域检测）。

## 📜 许可

本项目为内部安全管理系统，仅供学习和参考使用。
