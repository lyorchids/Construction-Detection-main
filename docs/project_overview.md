# 建筑施工现场安全隐患AI识别系统 — 项目概览

---

## 1、项目简介

**建筑施工现场安全隐患AI识别系统**是一个基于计算机视觉和深度学习技术的智能化安全管理平台，旨在通过AI实时检测建筑工地中的各类安全隐患，提升施工现场的安全管理水平。

项目利用 YOLO（You Only Look Once）目标检测算法，对施工现场上传的图片和视频进行实时分析，自动识别以下安全隐患：

- **劳保用品违规佩戴**：未戴安全帽、未穿反光背心、未佩戴口罩
- **区域管控违规**：人员闯入锥形桶管控区
- **机械作业危险**：施工机械靠近电线杆作业
- **火灾烟雾隐患**：明火与烟雾检测

系统提供完整的 Web 前端管理界面，支持图片检测、视频流实时检测、历史记录查询、AI 智能分析报告生成、Word 报告导出、案例库管理等全链路功能。

项目基于 FastAPI + Vue 3 + Element Plus + SQLite 技术栈构建，轻量级部署，适合施工现场本地化部署或云端部署。

---

## 2、技术栈

### 前端（Frontend）

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue 3 | ^3.5.32 | 前端框架 (Composition API + `<script setup>`) |
| TypeScript | ~6.0.2 | 类型安全 |
| Vite | ^5.4.21 | 构建工具与开发服务器 |
| Element Plus | ^2.13.6 | UI 组件库 |
| Pinia | ^3.0.4 | 状态管理（检测状态） |
| Vue Router | ^4.6.4 | 前端路由 |
| Axios | ^1.14.0 | HTTP 请求 |
| ECharts | ^6.0.0 | 数据可视化图表 |
| Sass | ^1.99.0 | CSS 预处理器 |

### 后端（Backend）

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | ≥3.10 | 运行环境 |
| FastAPI | ≥0.110.0 | Web API 框架 |
| Uvicorn | ≥0.29.0 | ASGI 服务器 |
| Ultralytics | ≥8.0.0 | YOLO 模型推理 |
| OpenCV | ≥4.8.0 | 图像/视频处理 |
| NumPy | ≥1.24.0 | 数值计算 |
| SQLAlchemy | ≥2.0.0 | ORM 数据库操作 |
| Shapely | ≥2.0.0 | 地理空间几何计算 |
| scikit-learn | ≥1.3.0 | HDBSCAN 聚类（锥桶区域检测） |
| python-docx | ≥1.1.0 | Word 报告生成 |
| OpenAI | ≥1.0.0 | AI 大模型 API 调用 |
| NetworkX | — | 图论算法（电线杆 MST 构建） |
| aiofiles | ≥23.2.0 | 异步文件操作 |

### 数据存储

| 技术 | 用途 |
|------|------|
| SQLite | 本地数据库（文件型，无需额外部署） |

### AI 大模型支持

| 平台 | 说明 |
|------|------|
| 阿里云通义千问 (DashScope) | 默认配置，模型 `qwen3.7-max` |
| DeepSeek | 兼容 OpenAI 格式的 API |
| 任何 OpenAI 兼容 API | 可配置 |

---

## 3、系统功能

### 3.1 首页大盘（Dashboard）

- **概览统计**：今日检测次数、今日违规数、总检测次数、总违规数
- **违规类型分布**：ECharts 环形饼图展示各类违规占比
- **检测趋势**：ECharts 折线图展示近7天违规趋势
- **违规卡片**：按违规类型聚合展示 Top 6 违规统计

**接口**：`GET /api/v1/stats`

---

### 3.2 图片检测

- **上传图片**：支持 JPG/PNG/BMP/WebP，最大 10MB
- **模型选择**：可选择 PPE 检测模型和/或 Fire 检测模型
- **置信度调节**：可为每个模型独立设置置信度阈值（5%~95%）
- **注解模式**：
  - **全部标注**：显示所有检测到的目标
  - **配置标注**：仅标注违规目标（未戴安全帽、未穿反光背心等）
- **违规规则配置**：可开关各项违规检测规则
- **检测结果**：Canvas 实时渲染检测框，违规目标红色高亮，锥形桶管控区黄色半透明覆盖
- **违规告警面板**：展示违规类型、次数及详情

**接口**：`POST /api/v1/image/detect`

---

### 3.3 视频检测（WebSocket 实时流）

- **视频上传**：支持 MP4/AVI/MOV/MKV/FLV，最大 200MB
- **WebSocket 实时推流**：服务端逐帧读取视频，按配置间隔执行检测，实时推送检测结果到前端
- **实时画布渲染**：与图片检测相同的 Canvas 渲染机制
- **违规标记时间轴**：在视频时间轴上标记违规帧（红色圆点）
- **检测配置**：
  - 模型选择（PPE / Fire）
  - 检测间隔（0.5s ~ 10s，可选逐帧检测）
  - 违规规则启用/禁用
  - 是否保存违规截图
- **暂停/继续/停止**：支持流控
- **实时统计**：检测帧数、总目标数、违规数

**更多详情**：
- 视频检测完成后自动删除原始视频文件（节省存储）
- 违规截图自动保存到 `backend/violations/` 目录
- 检测记录自动写入数据库

**接口**：`WebSocket /ws/video/detect/{file_path}`

---

### 3.4 历史记录

- **分页查询**：支持页码和每页数量
- **多维筛选**：
  - 文件类型筛选（图片/视频）
  - 日期范围筛选
- **记录列表**：展示文件名、类型、检测时间、总目标数、违规数、各类违规计数
- **单条详情**：跳转详情页查看完整检测结果
- **违规类型统计**：每条记录含违规类型聚合计数
- **删除记录**：同时删除关联的违规记录和截图文件

**接口**：
- `GET /api/v1/records`
- `GET /api/v1/records/{id}`
- `GET /api/v1/records/{id}/violations`
- `DELETE /api/v1/records/{id}`

---

### 3.5 记录详情

- **基本信息**：文件名、类型、检测时间、时长
- **违规截图**：展示检测时保存的违规场景截图
- **AI 智能分析**：
  - 点击"生成AI分析报告"调用大模型分析
  - 输出格式：报告标题、基本信息、检测概况、违规详情、安全评估、总体建议
  - 支持导出为 Word 文档（含截图）
- **入库案例**：将检测记录一键转为安全管理案例

**接口**：
- `POST /api/v1/report/ai-analysis`
- `POST /api/v1/report/ai-analysis/download`
- `POST /api/v1/cases/from-record/{id}`

---

### 3.6 AI 智能分析报告

- **单条记录分析**：对一条检测记录进行详细违规分析
- **时段分析**：对指定日期范围内的所有记录进行综合分析
- **报告结构**：
  - **基本信息**：报告编号、分析时间、文件/时段信息
  - **检测概况**：总违规数、风险等级（low/medium/high/critical）
  - **违规详情**：每类违规的数量、首次出现时间、严重程度、描述、建议
  - **安全评估**：AI 生成的总体评价、风险因素、核心发现
  - **总体建议**：分优先级的整改措施
  - **专家签名**
- **AI 降级**：当 AI 服务不可用时，自动使用模板生成带中文描述的离线报告，不阻塞功能
- **Word 导出**：支持导出为 `.docx` 格式，嵌入违规截图

**接口**：
- `POST /api/v1/report/generate`（普通报告）
- `POST /api/v1/report/ai-analysis`（AI 报告）
- `POST /api/v1/report/ai-analysis/download`（Word 下载）

---

### 3.7 案例库管理

- **案例列表**：分页展示所有案例，支持按类型、严重程度、关键词筛选
- **案例创建**：
  - 手动创建（填写标题、类型、严重程度、场景描述、建议措施）
  - 从检测记录一键生成（自动提取违规信息）
- **案例编辑**：更新案例信息
- **案例删除**：删除案例
- **案例详情**：展示完整案例信息

**接口**：
- `GET /api/v1/cases`
- `POST /api/v1/cases`
- `POST /api/v1/cases/from-record/{id}`
- `GET /api/v1/cases/{id}`
- `PUT /api/v1/cases/{id}`
- `DELETE /api/v1/cases/{id}`

---

### 3.8 检测配置管理

- **配置模板**：支持图片检测和视频检测两种配置模板
- **模型配置**：
  - PPE 模型（安全PPE检测）— 可配置置信度阈值和危险规则
  - Fire 模型（火情烟雾检测）— 可配置置信度阈值
- **危险规则**：
  - 未戴安全帽
  - 未佩戴口罩
  - 未穿反光背心
  - 进入锥形桶管控区
  - 机械靠近电线杆
- **视频参数**：检测间隔（0.5s~10s）、保存违规截图开关
- **预置配置**：
  - PPE标准检测
  - 全面检测（PPE + 火情）
  - 标准视频检测
  - 快速视频检测

**接口**：
- `GET /api/v1/profiles`
- `POST /api/v1/profiles`
- `GET /api/v1/profiles/{id}`
- `PUT /api/v1/profiles/{id}`
- `DELETE /api/v1/profiles/{id}`

---

### 3.9 模型管理

- **模型注册中心**：读取 `backend/config/models.json` 注册可用模型
- **支持模型**：
  - `ppe`：安全PPE检测模型（yolo26l.pt），检测11类目标
  - `fire`：火情烟雾检测模型（fire_smoke.pt），检测火焰和烟雾

**接口**：`GET /api/v1/models`

---

## 4、系统架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                       用户浏览器                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                Vue 3 + Element Plus                    │  │
│  │  ┌──────┐  ┌───────────┐  ┌────────┐  ┌──────────┐  │  │
│  │  │Home  │  │ImageDetect│  │VideoDet│  │ History  │  │  │
│  │  │      │  │           │  │  ect    │  │          │  │  │
│  │  ├──────┤  ├───────────┤  ├────────┤  ├──────────┤  │  │
│  │  │Detail│  │CaseList/  │  │Profiles│  │Upload    │  │  │
│  │  │      │  │Create/Det │  │        │  │          │  │  │
│  │  └──────┘  └───────────┘  └────────┘  └──────────┘  │  │
│  │                                                       │  │
│  │   ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │  │
│  │   │ Pinia    │  │ Vue Router   │  │ Axios / WS    │  │  │
│  │   │ 状态管理  │  │ 路由管理      │  │ HTTP + WebSocket│ │
│  │   └──────────┘  └──────────────┘  └───────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP REST + WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI 后端服务                           │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    API 路由层                          │  │
│  │  ┌──────────┐ ┌────────┐ ┌────────┐ ┌────────────┐  │  │
│  │  │ upload/  │ │ image_ │ │ video_ │ │  history/  │  │  │
│  │  │          │ │ detect │ │ detect │ │            │  │  │
│  │  ├──────────┤ ├────────┤ ├────────┤ ├────────────┤  │  │
│  │  │ report/  │ │ cases/ │ │profiles│ │  models/   │  │  │
│  │  │          │ │        │ │        │ │            │  │  │
│  │  └──────────┘ └────────┘ └────────┘ └────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    核心服务层                          │  │
│  │  ┌────────────────┐  ┌─────────────────────────────┐ │  │
│  │  │  YOLODetector  │  │     DangerDetector          │ │  │
│  │  │  - 模型加载     │  │  - 未戴安全帽检测            │ │  │
│  │  │  - 图片推理     │  │  - 未穿背心检测              │ │  │
│  │  │  - 视频帧推理   │  │  - 口罩检测                  │ │  │
│  │  │  - ByteTrack   │  │  - 锥桶管控区检测            │ │  │
│  │  │  - 运动检测     │  │  - 机械靠近电线杆检测        │ │  │
│  │  └────────────────┘  └─────────────────────────────┘ │  │
│  │  ┌────────────────┐  ┌─────────────────────────────┐ │  │
│  │  │  Annotator     │  │     VideoStreamer           │ │  │
│  │  │  - 画框标注     │  │  - WebSocket 推流           │  │  │
│  │  │  - 中文标签渲染 │  │  - 实时检测                  │  │  │
│  │  │  - 区域覆盖     │  │  - 帧间隔控制               │  │  │
│  │  └────────────────┘  └─────────────────────────────┘ │  │
│  │  ┌────────────────┐  ┌─────────────────────────────┐ │  │
│  │  │  AIService     │  │     ModelRegistry           │ │  │
│  │  │  - AI报告生成   │  │  - 模型注册管理             │ │  │
│  │  │  - 提示词构建   │  │  - 多模型支持               │ │  │
│  │  │  - 响应解析     │  │  - 惰性加载                 │ │  │
│  │  └────────────────┘  └─────────────────────────────┘ │  │
│  │  ┌────────────────┐  ┌─────────────────────────────┐ │  │
│  │  │  ReportSvc     │  │     CaseService             │ │  │
│  │  │  - Word报告    │  │  - 案例库CRUD               │ │  │
│  │  │  - 截图嵌入    │  │  - 从记录生成案例            │ │  │
│  │  └────────────────┘  └─────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │              BboxUtils (工具层)                  │ │  │
│  │  │  - 坐标归一化 / IoU / NMS / 驾驶员检测           │ │  │
│  │  │  - 锥桶聚类 / 多边形构建 / 管控区人数统计         │ │  │
│  │  │  - 电线杆聚类 / MST / 外切线 / 缓冲区域构建      │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    数据层                              │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │  │
│  │  │DetectionRec │  │  Violation   │  │  Case      │  │  │
│  │  │ord (检测记录)│  │  (违规明细)  │  │  (案例)    │  │  │
│  │  ├──────────────┤  ├──────────────┤  ├────────────┤  │  │
│  │  │ViolationCoun│  │DetectionProf │  │  SQLite    │  │  │
│  │  │t (违规聚合)  │  │ile (检测配置) │  │  数据库    │  │  │
│  │  └──────────────┘  └──────────────┘  └────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────┐  ┌────────────┐  ┌─────────┐  ┌─────────┐  │
│  │ 上传图片/ │  │ 违规截图   │  │ Word    │  │ YOLO    │  │
│  │ 视频文件  │  │ 文件       │  │ 报告文件 │  │ 模型文件 │  │
│  └───────────┘  └────────────┘  └─────────┘  └─────────┘  │
│   uploads/      violations/     reports/    models/        │
└─────────────────────────────────────────────────────────────┘
```

### 架构说明

| 层次 | 说明 |
|------|------|
| **前端展示层** | Vue 3 SPA，Element Plus UI，ECharts 图表，Canvas 实时渲染检测结果 |
| **API 路由层** | FastAPI 路由分发，包括 RESTful API 和 WebSocket 端点 |
| **核心服务层** | YOLO 检测引擎、危险规则引擎、视频流推流引擎、AI 报告引擎 |
| **数据持久层** | SQLite 数据库 + 文件系统（图片/视频/截图/报告/模型） |

### 关键设计点

1. **多模型并行检测**：`ModelRegistry` 管理多个 YOLO 模型实例，支持 PPE 和 Fire 模型同时运行，结果合并后统一处理
2. **WebSocket 实时推流**：`VideoStreamer` 按配置间隔执行检测，非检测帧重用缓存结果，帧率控制保证实时播放
3. **危险规则引擎**：`DangerDetector` 基于 Shapely 几何计算和 HDBSCAN 聚类，不依赖额外模型即可检测违规
4. **AI 报告优雅降级**：AI 服务不可用时自动使用固定模板生成中文报告，不阻塞功能
5. **自动清理**：视频检测完成后自动删除原始视频文件，节省磁盘空间

---

## 5、数据库设计

### 5.1 实体关系图（文字描述）

```
DetectionRecord (1) ──── (N) Violation
DetectionRecord (1) ──── (N) ViolationCount
DetectionRecord (1) ──── (N) Case
DetectionProfile       (独立表)
```

### 5.2 表结构

#### detection_records（检测记录表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键，自增 |
| filename | VARCHAR(255) | 文件名 |
| file_type | VARCHAR(20) | 文件类型：`image` / `video` |
| file_path | VARCHAR(500) | 文件存储路径 |
| detect_time | DATETIME | 检测时间 |
| total_objects | INTEGER | 检测到的目标总数 |
| violation_count | INTEGER | 违规数 |
| duration | FLOAT | 视频时长（秒），图片为0 |

**关联**：
- `violations`：一对多，级联删除
- `violation_counts`：一对多，级联删除
- `cases`：一对多，级联删除

---

#### violations（违规明细表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键，自增 |
| record_id | INTEGER FK | 关联 `detection_records.id` |
| violation_type | VARCHAR(100) | 违规类型（见违规类型枚举） |
| frame_number | INTEGER | 违规帧号（仅视频） |
| timestamp | FLOAT | 违规时间戳（秒，仅视频） |
| bbox | JSON | 违规目标边界框 [x1,y1,x2,y2] |
| confidence | FLOAT | 置信度 |
| screenshot_path | VARCHAR(500) | 违规截图路径 |
| created_at | DATETIME | 创建时间 |

---

#### violation_counts（违规聚合计数表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键，自增 |
| record_id | INTEGER FK | 关联 `detection_records.id` |
| violation_type | VARCHAR(100) | 违规类型 |
| count | INTEGER | 该类型违规计数 |

**约束**：`UNIQUE(record_id, violation_type)`

---

#### cases（案例表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键，自增 |
| title | VARCHAR(200) | 案例标题 |
| case_type | VARCHAR(50) | 案例类型 |
| severity | VARCHAR(20) | 严重程度：`low` / `medium` / `high` |
| scene_description | TEXT | 场景描述 |
| recommended_actions | TEXT | 建议措施 |
| process_info | TEXT | 处理过程 |
| images | JSON | 关联图片路径列表 |
| source_record_id | INTEGER FK | 来源检测记录ID |
| source_filename | VARCHAR(255) | 来源文件名 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

#### detection_profiles（检测配置表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键，自增 |
| name | VARCHAR(100) | 配置名称 |
| type | VARCHAR(20) | 类型：`image` / `video` |
| description | TEXT | 描述 |
| config | JSON | 详细配置（模型开关、阈值、危险规则等） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

`config` JSON 结构示例：

```json
{
  "models": {
    "ppe": {
      "enabled": true,
      "threshold": 0.25,
      "danger_rules": {
        "detect_no_hardhat": true,
        "detect_no_mask": true,
        "detect_no_safety_vest": true,
        "detect_in_restricted_area": true,
        "detect_machinery_close_to_pole": false
      }
    },
    "fire": {
      "enabled": false,
      "threshold": 0.25
    }
  },
  "frame_interval": 10,
  "save_screenshots": true
}
```

### 5.3 违规类型枚举

| 类型 Key | 显示名称 | 严重程度 | 说明 |
|----------|----------|----------|------|
| `warning_no_hardhat` | 未戴安全帽 | high | 人员未佩戴安全帽 |
| `warning_no_mask` | 未佩戴口罩 | low | 人员未佩戴口罩 |
| `warning_no_safety_vest` | 未穿反光背心 | low | 人员未穿反光背心 |
| `warning_people_in_controlled_area` | 进入锥形桶管控区 | high | 人员闯入管控区域 |
| `detect_machinery_close_to_pole` | 机械靠近电线杆 | high | 机械/车辆靠近电线杆 |
| `warning_fire` | 检测到火焰 | critical | 明火检测 |
| `warning_smoke` | 检测到烟雾 | high | 烟雾检测 |

### 5.4 YOLO 类别映射（PPE 模型）

| ID | 标签 | 说明 |
|----|------|------|
| 0 | Hardhat | 安全帽 |
| 1 | Mask | 口罩 |
| 2 | NO-Hardhat | 未戴安全帽 |
| 3 | NO-Mask | 未戴口罩 |
| 4 | NO-Safety Vest | 未穿反光背心 |
| 5 | Person | 人员 |
| 6 | Safety Cone | 锥形桶 |
| 7 | Safety Vest | 反光背心 |
| 8 | Machinery | 机械 |
| 9 | Utility Pole | 电线杆 |
| 10 | Vehicle | 车辆 |

火灾烟雾模型
0: Fire – Images containing visible flames or areas where a fire is clearly present.
1: Smoke – Images with visible smoke, either in the early stages of fire development or from environmental factors.

---

## 6、运行环境

### 6.1 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|----------|----------|
| CPU | 4 核 | 8 核及以上 |
| 内存 | 8GB | 16GB+ |
| GPU | NVIDIA GPU 4GB+（可选，加速推理） | NVIDIA GPU 8GB+（如 RTX 3060+） |
| 磁盘 | 10GB 可用空间 | 50GB+（存储检测结果和报告） |
| 操作系统 | Windows 10+ / Linux / macOS | 同左 |

### 6.2 软件要求

| 软件 | 版本要求 |
|------|----------|
| Python | ≥3.10 |
| Node.js | ≥18 |
| npm | ≥9 |

### 6.3 开发环境

```bash
# 克隆项目
git clone <repository-url>
cd Construction-Hazard-Detection

# 后端依赖安装
pip install -r backend/requirements.txt
pip install aiohttp httpx requests python-dotenv sahi schedule speedtest-cli streamlink redis watchdog openai networkx

# 前端依赖安装
cd frontend
npm install

# 环境变量配置
cp backend/.env.example backend/.env
# 编辑 backend/.env 填入 AI API Key 等信息
```

### 6.4 运行命令

```bash
# 启动后端 (端口 8000)
python backend/run.py

# 启动前端开发服务器 (端口 5173)
cd frontend && npm run dev

# 生产构建
cd frontend && npm run build
```

### 6.5 环境变量配置（backend/.env）

```env
AI_API_KEY=sk-your-api-key           # AI API Key (通义千问/DeepSeek)
AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # AI API 地址
AI_MODEL=qwen3.7-max-2026-05-17      # 模型名称
DEVICE=cuda:0                         # 检测设备 (cuda:0 或 cpu)
```

---

## 7、核心流程介绍

### 7.1 图片检测流程

```
用户上传图片 → 后端接收保存 → 读取图片为 OpenCV Mat
  → 按所选模型依次推理 (YOLO detect_image)
    → [PPE 模型]: 检测 11 类目标 → DangerDetector 规则引擎分析
      ├── 未戴安全帽检查 (class_id=2)
      ├── 未穿反光背心检查 (class_id=4)
      ├── 锥桶管控区检查 (class_id=6 聚类构建多边形 → 人员是否在多边形内)
      └── 机械靠近电线杆检查 (class_id=8/10 + class_id=9 几何距离计算)
    → [Fire 模型]: 检测火焰/烟雾 → 直接映射为违规类型
  → 合并所有模型的检测结果 → NMS 去重
  → 标注违规标签 → 绘制检测框标注图 (draw_annotations)
  → 保存检测记录和违规记录到数据库
  → 保存违规截图到 violations/
  → 返回检测结果 (base64 图片 + 检测框 + 违规列表) 到前端
  → 前端 Canvas 渲染标注
```

### 7.2 视频流检测流程

```
用户上传视频 → 后端接收保存 → 前端发起 WebSocket 连接
  → 前端发送 start 指令 (含模型选择、阈值、间隔等配置)
  → 服务端 VideoStreamer 打开视频文件
  → 循环:
    ├── 读取下一帧
    ├── 判断是否到检测间隔时间
    ├── [是] 执行检测:
    │   ├── 多模型并行推理 (detect_frame with ByteTrack)
    │   ├── DangerDetector 危险规则分析
    │   ├── 违规计数 (记录每种违规类型的最大并发数)
    │   ├── 保存违规截图 (首次出现的违规类型)
    │   └── 缓存检测结果
    ├── [否] 使用缓存的上次检测结果
    ├── 编码帧为 JPEG base64
    ├── 封装 WebSocket 消息 (帧数据 + 检测框 + 违规列表)
    └── 推送至前端
  → 视频结束 → 发送 complete 消息
  → 写入数据库 (检测记录 + 违规明细 + 违规计数)
  → 删除原始视频文件
```

### 7.3 锥桶管控区域检测流程

```
从检测结果中提取 Safety Cone (class_id=6)
  → 计算每个锥桶的中心点坐标
  → 使用 HDBSCAN 对锥桶中心点进行聚类
  → 对每个聚类 (至少3个点):
    → 使用 MultiPoint.convex_hull 构建凸多边形
    → 多边形即为管控区域
  → 遍历所有 Person (class_id=5):
    → 计算人员中心点
    → 判断是否在任一管控多边形内 (Shapely Point.contains)
  → 输出: 管控多边形列表 + 违规人员计数
```

### 7.4 机械靠近电线杆检测流程

```
从检测结果提取 Utility Pole (class_id=9)
  → 对每个电线杆:
    ├── 计算高度 = bottom - top
    ├── 底部圆心 = ((left+right)/2, bottom)，半径 = 0.35 * 高度
    └── 构建圆形危险区域 (Shapely Point.buffer)
  → 遍历所有 Machinery/Vehicle (class_id=8/10):
    ├── 筛选: 机械顶部在电线杆高度 2/3 以下
    └── 判断机械底部线段与圆形危险区的距离 ≤ 0
  → 输出: 违规机械数量 + 位置
```

### 7.5 AI 智能报告生成流程

```
用户请求 AI 分析
  → 从数据库获取检测记录和违规明细
  → 聚合分析: 违规类型计数、严重程度分布、每日趋势、首次出现时间
  → 构建固定模板的违规详情 (描述+建议)
  → 构建基础报告框架
  → [AI 可用]: 
    ├── 构建提示词 (Prompt) — 将检测数据格式化为结构化文本
    ├── 调用 AI API (OpenAI 兼容接口)
    ├── 解析 AI 返回的 JSON 响应
    └── 将 AI 生成的评估和建议填入报告
  → [AI 不可用]: 使用内置模板生成离线报告 (不阻塞)
  → 返回完整报告 → 前端展示
  → [Word 导出]: 使用 python-docx 生成 .docx 文件 (含截图)
```

### 7.6 多模型注册与调度流程

```
应用启动 → ModelRegistry 初始化
  → 读取 backend/config/models.json
  → 注册 PPE 模型 (path, device, classes, danger_rules)
  → 注册 Fire 模型 (path, device, classes, violation_types)
  → 提供 get_model(key) — 惰性加载模型实例
  → 提供 get_config(key) — 获取模型配置

检测请求时:
  → 根据前端选择的 models 列表 (如 ['ppe', 'fire'])
  → 遍历每个 model_key:
    ├── registry.get_model(model_key) → 获取/创建 YOLO 实例
    ├── registry.get_config(model_key) → 获取配置
    └── 执行推理 + 规则分析
  → 合并所有模型的结果
```
