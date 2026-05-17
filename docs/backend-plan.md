# 后端开发计划 — 建筑施工现场安全隐患AI识别系统

## 技术栈

| 组件 | 技术 |
|------|------|
| 框架 | FastAPI |
| 数据库 | SQLite + SQLAlchemy |
| 检测引擎 | YOLO (ultralytics) + OpenCV |
| 报告生成 | python-docx |
| 实时通信 | WebSocket |
| 异步HTTP | httpx |

## 现有可复用模块（hazard_detector/）

| 模块 | 可复用内容 | 复用方式 |
|------|-----------|---------|
| `utils.py` | `Utils` 类 — bbox 归一化、重叠率计算、driver 判断、危险距离判断、安全锥多边形检测、电线杆区域构建、帧编码（JPEG/PNG）、文件监听、Redis 管理 | 直接复制/导入到新项目，修复 `danger_detector.py` 中的 `from src.utils import Utils` 错误导入 |
| `danger_detector.py` | `DangerDetector` 类 — 违规检测规则引擎 | 需要适配新模型类别映射（移除电线杆逻辑，新增 NO-Mask 检测） |
| `live_stream_detection.py` | `LiveStreamDetector` 类 — YOLO 推理 + 目标跟踪 | 提取 `generate_detections()` 和跟踪逻辑，改为支持上传文件 |
| `stream_capture.py` | `StreamCapture` 类 — 异步帧捕获 + 自动重连 | 本地视频文件不需要此模块，但可借鉴其 AsyncGenerator 模式 |
| `model_fetcher.py` | `ModelFetcher` 类 — 模型自动更新 | 后续可选功能 |
| `monitor_logger.py` | `LoggerConfig` 类 — 日志配置 | 直接复用 |
| `net/net_client.py` | `NetClient` 类 — HTTP + WebSocket 客户端 | 本项目为服务端，不需要此类，但可借鉴其 WebSocket 设计 |
| `violation_sender.py` | `ViolationSender` 类 — 违规上传 | 本项目内部处理，不需要 |
| `frame_sender.py` | `BackendFrameSender` 类 — 帧发送 | 本项目内部处理，不需要 |

---

## Step 1: 项目结构设计与环境搭建

### 目标
搭建后端项目骨架，配置依赖和基础结构。

### 目录结构
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置管理（路径、模型、数据库）
│   ├── database.py          # SQLAlchemy 数据库连接
│   ├── models/              # SQLAlchemy 数据模型
│   │   ├── __init__.py
│   │   ├── detection.py     # 检测记录模型
│   │   └── violation.py     # 违规记录模型
│   ├── schemas/             # Pydantic 请求/响应模型
│   │   ├── __init__.py
│   │   ├── detection.py
│   │   └── violation.py
│   ├── api/                 # 路由
│   │   ├── __init__.py
│   │   ├── upload.py        # 图片/视频上传
│   │   ├── detection.py     # 检测接口
│   │   ├── history.py       # 历史记录查询
│   │   └── report.py        # 报告生成
│   ├── core/                # 核心业务逻辑
│   │   ├── __init__.py
│   │   ├── detector.py      # YOLO 检测器封装（复用 live_stream_detection.py）
│   │   ├── danger_rules.py  # 违规判断规则引擎（复用 danger_detector.py）
│   │   └── streamer.py      # WebSocket 视频流处理
│   ├── services/            # 业务服务层
│   │   ├── __init__.py
│   │   ├── detection_service.py
│   │   ├── violation_service.py
│   │   └── report_service.py
│   └── utils/               # 工具函数
│       ├── __init__.py
│       └── bbox_utils.py    # 从 hazard_detector/utils.py 提取
├── models/                  # YOLO 模型文件（放置你的 .pt 模型）
│   └── best.pt
├── uploads/                 # 上传文件存储
├── violations/              # 违规截图存储
├── reports/                 # 生成的报告存储
├── requirements.txt
├── .env
└── run.py                   # 启动脚本
```

### 依赖清单
```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
ultralytics>=8.0.0
opencv-python>=4.8.0
numpy>=1.24.0
sqlalchemy>=2.0.0
python-multipart>=0.0.9
python-dotenv>=1.0.0
shapely>=2.0.0
scikit-learn>=1.3.0
python-docx>=1.1.0
aiofiles>=23.2.0
```

### 建议操作
1. 创建 `backend/` 目录及上述结构
2. 将 `hazard_detector/utils.py` 中的 `Utils` 类复制到 `backend/app/utils/bbox_utils.py`
3. 编写 `requirements.txt`
4. 创建 `.env` 配置文件
5. 编写 `app/config.py` 读取环境变量
6. 编写 `app/database.py` 初始化 SQLite 连接
7. 编写 `app/main.py` 最简 FastAPI 入口

### 验证方式
```bash
cd backend
pip install -r requirements.txt
python run.py
# 访问 http://localhost:8000/docs 确认 Swagger UI 正常
```

---

## Step 2: YOLO检测核心模块

### 目标
封装 YOLO 模型加载与推理，提供统一检测接口。

### 核心类: `app/core/detector.py`

**复用来源**: `hazard_detector/live_stream_detection.py` 的 `LiveStreamDetector`

```python
class YOLODetector:
    def __init__(self, model_path: str, device: str = "cpu")
    def detect_image(self, image: np.ndarray) -> list[DetectionResult]
    def detect_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list[DetectionResult]]
    def detect_video_stream(self, video_path: str) -> AsyncGenerator[FrameResult]
```

### 数据格式
```python
@dataclass
class DetectionResult:
    bbox: list[float]        # [x1, y1, x2, y2]
    confidence: float
    class_id: int
    class_name: str
    track_id: int | None     # 视频跟踪时使用
    is_moving: bool          # 视频跟踪时使用
```

### 类别映射（你的模型）
```python
CLASS_NAMES = {
    0: 'Hardhat',
    1: 'Mask',
    2: 'NO-Hardhat',
    3: 'NO-Mask',
    4: 'NO-Safety Vest',
    5: 'Person',
    6: 'Safety Cone',
    7: 'Safety Vest',
    8: 'machinery',
    9: 'vehicle',
}
```

### 建议操作
1. 从 `LiveStreamDetector` 提取 `generate_detections()` 逻辑
2. 实现模型加载（支持 `.pt` 和 `.onnx`）
3. 实现单张图片检测
4. 实现视频逐帧检测生成器（AsyncGenerator 模式，参考 `StreamCapture.execute_capture()`）
5. 添加跟踪功能（`model.track`）

### 验证方式
- 传入测试图片，输出检测结果
- 传入测试视频，逐帧输出检测结果

---

## Step 3: 违规判断逻辑层

### 目标
基于检测结果，判断是否存在安全隐患。

### 核心类: `app/core/danger_rules.py`

**复用来源**: `hazard_detector/danger_detector.py` 的 `DangerDetector`

### 需要修改的地方
1. **修复导入**: 将 `from src.utils import Utils` 改为 `from app.utils.bbox_utils import Utils`
2. **类别 ID 适配**: 原代码使用 `d[5] == 10` 表示 vehicle，新模型使用 `d[5] == 9`
3. **移除电线杆逻辑**: 模型无电线杆类别，移除 `check_pole_restricted_area()` 和 `check_machinery_near_utility_pole()`
4. **新增 NO-Mask 检测**: 添加 `NO-Mask` (ID 3) 与 `Person` 重叠判断

### 检测规则
| 规则 | 触发条件 | 返回警告键 |
|------|----------|-----------|
| 未戴安全帽 | `NO-Hardhat`(2) 与 `Person`(5) 重叠 > 0.5 | `warning_no_hardhat` |
| 未戴口罩 | `NO-Mask`(3) 与 `Person`(5) 重叠 > 0.5 | `warning_no_mask` |
| 未穿反光背心 | `NO-Safety Vest`(4) 与 `Person`(5) 重叠 > 0.5 | `warning_no_safety_vest` |
| 人员靠近机械 | `Person`(5) 与 `machinery`(8) 距离 < 阈值 | `warning_close_to_machinery` |
| 人员靠近车辆 | `Person`(5) 与 `vehicle`(9) 距离 < 阈值 | `warning_close_to_vehicle` |
| 人员进入安全锥管控区 | `Person`(5) 在安全锥聚类多边形内 | `warning_people_in_controlled_area` |

### 建议操作
1. 复制 `danger_detector.py` 到 `backend/app/core/danger_rules.py`
2. 修复导入路径
3. 修改类别 ID 映射
4. 移除电线杆相关方法
5. 添加 `NO-Mask` 检测逻辑
6. 复用 `Utils` 类中的 `is_driver()`, `is_dangerously_close()`, `overlap_percentage()` 等方法

### 验证方式
- 构造模拟检测数据，验证各规则是否正确触发

---

## Step 4: FastAPI后端基础

### 目标
实现文件上传接口和静态文件服务。

### API 端点
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/upload/image` | 上传图片 |
| POST | `/api/v1/upload/video` | 上传视频 |
| GET | `/uploads/{filename}` | 获取上传文件 |
| GET | `/violations/{filename}` | 获取违规截图 |

### 建议操作
1. 实现 `app/api/upload.py` 路由
2. 配置静态文件目录
3. 添加文件大小限制和格式校验
4. 实现文件唯一命名（UUID）

### 验证方式
- 使用 Swagger UI 或 curl 上传图片/视频
- 确认文件正确保存到 `uploads/` 目录

---

## Step 5: SQLite数据库设计与实现

### 目标
设计数据库模型，实现检测记录的存储与查询。

### 数据模型

**detection_records 表**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| filename | VARCHAR | 原始文件名 |
| file_type | VARCHAR | image / video |
| file_path | VARCHAR | 存储路径 |
| detect_time | DATETIME | 检测时间 |
| total_objects | INTEGER | 检测到的目标总数 |
| violation_count | INTEGER | 违规数量 |
| duration | FLOAT | 视频时长（图片为0） |

**violations 表**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| record_id | INTEGER FK | 关联检测记录 |
| violation_type | VARCHAR | 违规类型 |
| frame_number | INTEGER | 视频帧号（图片为0） |
| timestamp | FLOAT | 视频时间戳 |
| bbox | JSON | 违规目标边界框 |
| confidence | FLOAT | 置信度 |
| screenshot_path | VARCHAR | 违规截图路径 |
| created_at | DATETIME | 创建时间 |

### API 端点
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/records` | 获取检测记录列表（分页） |
| GET | `/api/v1/records/{id}` | 获取单条记录详情 |
| GET | `/api/v1/records/{id}/violations` | 获取某记录的违规列表 |
| DELETE | `/api/v1/records/{id}` | 删除记录及关联数据 |

### 建议操作
1. 编写 `app/models/` 下的 SQLAlchemy 模型
2. 编写 `app/schemas/` 下的 Pydantic 模型
3. 实现 CRUD 操作
4. 实现分页和筛选

### 验证方式
- 手动插入测试数据，验证查询接口返回正确

---

## Step 6: WebSocket视频流推送

### 目标
实现视频逐帧检测并通过 WebSocket 推送到前端。

### 核心流程
```
前端请求 → 后端打开视频 → 逐帧检测 → 编码JPEG → WebSocket推送 → 前端渲染
```

### WebSocket 端点
```
WS /ws/detect/{file_id}
```

### 推送数据格式
```json
{
  "type": "frame",
  "frame_number": 120,
  "timestamp": 4.0,
  "image": "base64_encoded_jpeg",
  "detections": [
    {"bbox": [x1,y1,x2,y2], "class_id": 5, "class_name": "Person", "confidence": 0.95}
  ],
  "violations": [
    {"type": "warning_no_hardhat", "bbox": [x1,y1,x2,y2], "count": 1}
  ]
}
```

### 建议操作
1. 实现 `app/core/streamer.py` 视频流处理
2. 复用 `Utils.encode_frame()` 进行 JPEG 编码
3. 复用 `StreamCapture` 的 AsyncGenerator 模式
4. 实现 WebSocket 端点
5. 控制推送帧率（目标30fps）
6. 处理客户端断开连接

### 验证方式
- 使用 wscat 或前端测试连接
- 确认能收到逐帧数据

---

## Step 7: 违规截图存储

### 目标
检测到违规时自动截取当前帧并保存。

### 建议操作
1. 在检测流程中识别违规帧
2. 截取当前帧保存为 JPEG 到 `violations/` 目录
3. 记录截图路径到数据库
4. 实现截图去重（同一违规不重复截图）

### 验证方式
- 上传含违规的视频，确认违规截图正确生成

---

## Step 8: DOCX报告生成

### 目标
按时间段生成安全隐患报告。

### 报告内容
1. 报告标题与生成时间
2. 检测概况（总检测次数、总违规数）
3. 违规类型统计（表格 + 数量）
4. 违规时间分布
5. 典型违规截图（带标注）
6. 详细违规记录列表

### API 端点
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/report/generate` | 生成报告（可选时间范围） |
| GET | `/api/v1/report/{report_id}/download` | 下载报告 |

### 建议操作
1. 使用 `python-docx` 创建报告模板
2. 实现数据统计查询
3. 嵌入违规截图到报告
4. 支持按日期范围筛选

### 验证方式
- 调用接口生成报告，打开 DOCX 确认内容正确

---

## Step 9: 整合测试与优化

### 目标
端到端测试，性能调优。

### 测试项
1. 图片上传 → 检测 → 存储 → 查询 完整流程
2. 视频上传 → WebSocket流推送 → 前端展示
3. 违规截图生成与关联
4. 报告生成内容准确性
5. 并发上传处理
6. 大视频文件内存占用

### 优化方向
- 模型推理速度（ONNX 转换、batch 处理）
- WebSocket 推送帧率稳定性
- 数据库查询性能（索引）
- 内存泄漏检查

---

## 执行顺序

```
Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6 → Step 7 → Step 8 → Step 9
```

每步完成后需确认成功，再继续下一步。
