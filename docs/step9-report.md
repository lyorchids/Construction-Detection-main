# Step 9: 违规截图存储 + 历史记录页 — 完成报告

## 执行时间
2026-04-07

## 完成内容

### 1. 后端：违规截图存储 (`app/core/streamer.py`)
- 检测过程中自动截取违规帧并保存为 JPEG 到 `violations/` 目录
- 截图去重（每 30 帧同一违规类型只保存一次）
- 违规记录写入数据库（violation_type, frame_number, timestamp, screenshot_path）
- 视频检测完成后自动创建检测记录（detection_records 表）
- WebSocket 结束时发送 `complete` 事件（含 record_id）

### 2. 前端：历史记录页 (`src/views/History.vue`)
- 检测记录表格（文件名、类型、时间、目标数、违规数、时长）
- 分页（每页 10/20/50/100）
- 按文件类型筛选（图片/视频）
- 违规数红色高亮
- 删除确认对话框

### 3. 前端：检测详情页 (`src/views/Detail.vue`)
- 检测基本信息展示
- 违规截图网格展示（响应式布局）
- 截图显示违规类型、帧号、时间戳

### 4. 前端：报告页占位 (`src/views/Report.vue`)
- 占位页面，后续 Step 11 实现 DOCX 报告生成

### 5. 类型检查
`npx vue-tsc --noEmit` 通过，无类型错误。

## 下一步
进入 **Step 10: 首页仪表盘**（统计图表）。
