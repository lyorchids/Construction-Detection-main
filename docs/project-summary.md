# 建筑施工现场安全隐患AI识别系统 — 项目总结

## 项目概述
基于 YOLO 模型的建筑施工现场安全隐患 AI 识别系统，实现视频/图片实时检测、违规场景标注、安全隐患报告生成。

## 技术架构

### 后端 (backend/)
| 组件 | 技术 |
|------|------|
| 框架 | FastAPI |
| 数据库 | SQLite + SQLAlchemy |
| 检测引擎 | YOLO (ultralytics) + OpenCV |
| 实时通信 | WebSocket |
| 报告生成 | python-docx |

### 前端 (frontend/)
| 组件 | 技术 |
|------|------|
| 框架 | Vue 3 + TypeScript |
| 构建工具 | Vite |
| UI 组件库 | Element Plus |
| 状态管理 | Pinia |
| 路由 | Vue Router 4 |
| 图表 | ECharts |

## 功能清单

| 功能 | 状态 | 说明 |
|------|------|------|
| 图片上传检测 | ✅ | 支持 JPG/PNG/BMP/WebP |
| 视频上传检测 | ✅ | 支持 MP4/AVI/MOV/MKV/FLV |
| YOLO 目标检测 | ✅ | 11 类目标识别 |
| 违规规则引擎 | ✅ | 6 种违规检测规则 |
| WebSocket 实时推送 | ✅ | 逐帧检测 + 标注推送 |
| 检测画面标注 | ✅ | Canvas 2D 绘制边界框 |
| 违规弹窗提醒 | ✅ | 前端 ElMessage 提醒 |
| 违规截图存储 | ✅ | 自动截取 + 去重 |
| 检测记录存储 | ✅ | SQLite 持久化 |
| 历史记录查询 | ✅ | 分页 + 筛选 |
| 检测详情查看 | ✅ | 违规截图网格展示 |
| 首页仪表盘 | ✅ | 统计卡片 + ECharts |
| DOCX 报告生成 | ✅ | 按日期范围生成 |
| 报告下载 | ✅ | 浏览器下载 |

## 检测类别（模型）

| ID | 类别 | 说明 |
|----|------|------|
| 0 | Hardhat | 安全帽 |
| 1 | Mask | 口罩 |
| 2 | NO-Hardhat | 未戴安全帽 |
| 3 | NO-Mask | 未戴口罩 |
| 4 | NO-Safety Vest | 未穿反光背心 |
| 5 | Person | 人员 |
| 6 | Safety Cone | 安全锥 |
| 7 | Safety Vest | 反光背心 |
| 8 | Machinery | 机械 |
| 9 | Utility Pole | 电线杆 |
| 10 | Vehicle | 车辆 |

## 违规检测规则

| 规则 | 触发条件 |
|------|----------|
| 未戴安全帽 | NO-Hardhat 与 Person 重叠 > 50% |
| 未戴口罩 | NO-Mask 与 Person 重叠 > 50% |
| 未穿反光背心 | NO-Safety Vest 与 Person 重叠 > 50% |
| 人员靠近机械 | Person 与 Machinery 距离 < 阈值 |
| 人员靠近车辆 | Person 与 Vehicle 距离 < 阈值 |
| 人员进入安全锥管控区 | Person 在安全锥聚类多边形内 |
| 人员进入电线杆管控区 | Person 在电线杆管控区域内 |
| 机械靠近电线杆 | Machinery/Vehicle 与 Utility Pole 距离 < 阈值 |

## 目录结构

```
backend/
├── app/
│   ├── api/           # 路由（upload, history, detection, report）
│   ├── core/          # 核心逻辑（detector, danger_rules, streamer）
│   ├── models/        # SQLAlchemy 数据模型
│   ├── schemas/       # Pydantic 响应模型
│   ├── services/      # 业务服务层
│   ├── utils/         # 工具函数
│   ├── config.py
│   ├── database.py
│   └── main.py
├── models/            # YOLO 模型
├── uploads/           # 上传文件
├── violations/        # 违规截图
├── reports/           # 生成的报告
├── requirements.txt
└── run.py

frontend/
├── src/
│   ├── api/           # API 调用
│   ├── components/    # 组件（DetectionCanvas）
│   ├── router/        # 路由配置
│   ├── stores/        # Pinia 状态管理
│   ├── views/         # 页面（Home, Upload, LiveDetect, History, Detail, Report）
│   ├── App.vue
│   └── main.ts
└── package.json
```

## 启动方式

### 后端
```bash
cd backend
pip install -r requirements.txt
python run.py
# 访问 http://localhost:8000/docs
```

### 前端
```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

## 注意事项

1. **模型文件**：需将 `.pt` 模型放置在 `backend/models/best.pt`
2. **NumPy 版本**：必须 `<2` 以兼容 torch 1.12
3. **greenlet**：Windows 下需安装预编译版本 `pip install greenlet --only-binary :all:`
4. **类别映射**：已在 `detector.py` 和 `danger_rules.py` 中统一配置
