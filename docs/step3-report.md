# Step 3: 违规判断逻辑层 — 完成报告

## 执行时间
2026-04-07

## 完成内容

### 1. 工具函数模块 (`app/utils/bbox_utils.py`)
从 `hazard_detector/utils.py` 提取并精简了 `Utils` 类，包含：
- `normalise_bbox()` / `normalise_data()` — 边界框坐标归一化
- `overlap_percentage()` — 两个边界框重叠率计算（IoU）
- `is_driver()` — 判断人员是否为驾驶员
- `is_dangerously_close()` — 判断人员是否靠近机械/车辆
- `detect_polygon_from_cones()` — 安全锥聚类生成管控区域多边形
- `calculate_people_in_controlled_area()` — 统计管控区域内人员数量
- `polygons_to_coords()` — 多边形坐标转换（用于前端渲染）
- `encode_frame()` — 帧编码（JPEG/PNG）
- 电线杆相关工具方法（保留供后续扩展）

### 2. 违规检测规则引擎 (`app/core/danger_rules.py`)
基于 `hazard_detector/danger_detector.py` 重构，主要改动：
- **修复导入**: `from app.utils.bbox_utils import Utils`
- **类别 ID 适配**: 新模型 vehicle ID 为 9（原为 10）
- **移除电线杆逻辑**: 模型无电线杆类别
- **新增 NO-Mask 检测**: 添加 `NO-Mask`(ID 3) 与 `Person` 重叠判断
- **检测规则**:
  | 规则 | 触发条件 | 警告键 |
  |------|----------|--------|
  | 未戴安全帽 | `NO-Hardhat`(2) 与 `Person`(5) 重叠 > 0.5 | `warning_no_hardhat` |
  | 未戴口罩 | `NO-Mask`(3) 与 `Person`(5) 重叠 > 0.5 | `warning_no_mask` |
  | 未穿反光背心 | `NO-Safety Vest`(4) 与 `Person`(5) 重叠 > 0.5 | `warning_no_safety_vest` |
  | 人员靠近机械 | `Person`(5) 与 `machinery`(8) 距离 < 阈值 | `warning_close_to_machinery` |
  | 人员靠近车辆 | `Person`(5) 与 `vehicle`(9) 距离 < 阈值 | `warning_close_to_vehicle` |
  | 人员进入安全锥管控区 | `Person`(5) 在安全锥聚类多边形内 | `warning_people_in_controlled_area` |

### 3. 测试验证
```
=== DangerDetector Test ===
Warnings: {
  'warning_no_hardhat': {'count': 1},
  'warning_no_mask': {'count': 1},
  'warning_no_safety_vest': {'count': 1}
}
All assertions passed!

=== Empty Data Test ===
Empty data test passed!

=== All tests completed ===
```

### 4. 安装额外依赖
- `networkx` — 电线杆区域构建所需（MST 算法）

## 下一步
进入 **Step 4: FastAPI后端基础**（文件上传接口）。
