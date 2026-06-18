# AGENTS.md — Construction Hazard Detection

## Project Overview

Python-based construction site hazard detection system using YOLO object detection. Two parallel modules:
- **`hazard_detector/`** — Full production module (streaming, Redis, WebSocket, notifications)
- **`esay_detector/`** — Simplified standalone module for local inference

## Build / Run Commands

### Install dependencies
```bash
pip install -r requirements.txt
# Also needed (not in requirements.txt):
pip install aiohttp httpx requests python-dotenv sahi schedule speedtest-cli streamlink redis watchdog openai
```

### 环境变量配置 (backend/.env)
```bash
# 复制配置示例文件
cp backend/.env.example backend/.env

# 编辑 .env 填入配置
AI_API_KEY=sk-your-api-key           # AI API Key
AI_BASE_URL=https://api.deepseek.com/v1  # 或其他兼容OpenAI的API
AI_MODEL=deepseek-chat             # 模型名称
DEVICE=cuda:0                   # 检测设备 (cuda:0 或 cpu)
```

### Run entry points
```bash
# 主程序入口 (后端API)
python backend/run.py

# 前端开发服务器
cd frontend && npm run dev

# Local image/video/camera detection
python esay_detector/run.py --input <path> --model <path> --type auto

# Single image demo
python esay_detector/detector.py --image <path> --model <path>

# Danger detector demo (no model needed, uses mock data)
python hazard_detector/danger_detector.py

# Live stream detection
python hazard_detector/live_stream_detection.py --url <rtsp_url> --model_key yolo26n --use_ultralytics

# Stream capture test
python hazard_detector/stream_capture.py --url <rtsp_url>

# Model fetcher (background scheduler)
python hazard_detector/model_fetcher.py
```

### Testing
**No test framework exists.** There are zero test files. To add tests, use `pytest`:
```bash
pip install pytest
pytest                          # run all tests
pytest tests/test_utils.py      # run single test file
pytest tests/test_utils.py -k test_overlap  # run single test by name
```

### Linting / Formatting
**No linter or formatter is configured.** Recommended additions:
```bash
pip install ruff
ruff check .                    # lint
ruff format .                   # format
```

## Code Style Conventions

### Imports
- `from __future__ import annotations` at top of every file
- Standard library imports first, then third-party, then local — each group separated by a blank line
- Use explicit multi-line imports for shapely/geometries (one per line, no commas on same line):
  ```python
  from shapely.geometry import LineString
  from shapely.geometry import Point
  from shapely.geometry import Polygon
  ```

### Type Hints
- Full type annotations on all function signatures and return types
- Use modern union syntax: `str | None` (not `Optional[str]`)
- Inline type annotations on variables when not obvious: `cx: float = (left + right) / 2.0`
- Generic types use builtin syntax: `list[float]`, `dict[str, int]`, `tuple[float, float, float]`

### Naming Conventions
- **Classes**: `PascalCase` — `Utils`, `DangerDetector`, `LocalDetector`, `RedisManager`
- **Functions/methods**: `snake_case` — `detect_danger`, `normalise_bbox`, `is_driver`
- **Constants**: `UPPER_SNAKE_CASE` — `CIRCLE_BUFFER_SEGMENTS`, `CLASS_NAMES`
- **Private methods**: prefix with `_` — `_extract_utility_poles`, `_cluster_utility_poles`
- **British English spelling**: `normalise`, `initialises`, `normalised` (follow existing convention)

### Formatting
- 4-space indentation (no tabs)
- Line length: ~79 chars (implicit from existing code); break long lines with parens
- Trailing commas in multi-line lists/dicts
- Blank lines: 2 between top-level classes/functions, 1 between methods in a class

### Docstrings
- Google-style triple-quoted docstrings on all public methods and classes
- Include `Args:`, `Returns:`, and optionally `Notes:` sections
- Single-line docstrings acceptable for trivial private methods

### Error Handling
- Catch broad `Exception` in utility/IO methods; log with `logging.error()` and return safe defaults
- Never let exceptions propagate from frame encoding, Redis ops, or network calls
- Use `logging.error(f"...: {e}")` pattern for error messages

### Class Design
- Utility methods are `@staticmethod` on a `Utils` class (no instances)
- Detector classes accept configuration via `__init__` parameters
- Detection data format: `list[list[float]]` where each inner list is `[x1, y1, x2, y2, conf, cls_id, ...]`

### Class ID Mapping (YOLO model)
| ID | Label |
|----|-------|
| 0 | Hardhat |
| 2 | NO-Hardhat |
| 4 | NO-Safety Vest |
| 5 | Person |
| 6 | Safety Cone |
| 8 | Machinery |
| 9 | Utility Pole |
| 10 | Vehicle |

### 违规类型 (Violation Types)
| 类型Key | 说明 |
|--------|-------|
| warning_no_hardhat | 未戴安全帽 |
| warning_no_safety_vest | 未穿反光背心 |
| warning_people_in_controlled_area | 进入锥形桶管控区 |
| warning_people_in_utility_pole_controlled_area | 进入电线杆管控区 |

## API Endpoints

### 后端 API (FastAPI)
| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/v1/upload/image` | POST | 上传图片 |
| `/api/v1/upload/video` | POST | 上传视频 |
| `/api/v1/image/detect` | POST | 图片危险检测 |
| `/api/v1/records` | GET | 分页查询记录 |
| `/api/v1/records/{id}` | GET | 单条记录详情 |
| `/api/v1/records/{id}/violations` | GET | 违规列表 |
| `/api/v1/stats` | GET | 统计数据 |
| `/api/v1/report/generate` | POST | 生成Word报告 |
| `/api/v1/report/ai-analysis` | POST | AI智能分析报告 |
| `/ws/video/detect/{path}` | WebSocket | 视频流检测 |

### 前端路由 (Vue Router)
| 路由 | 组件 | 说明 |
|------|------|------|
| `/` | Home.vue | 首页统计 |
| `/image-detect` | ImageDetect.vue | 图片检测 |
| `/video-detect` | VideoDetect.vue | 视频检测 |
| `/history` | History.vue | 历史记录 |
| `/detail/:id` | Detail.vue | 记录详情+AI分析 |
| `/report` | Report.vue | 报告生成 |

## 新增功能说明

### AI智能报告生成
- 调用通义千问/DeepSeek等AI模型生成标准违规分析报告
- 支持单条记录分析或日期范围分析
- 报告格式：基本信息、检测概况、违规详情、安全评估、总体建议
- 支持导出为txt文本文件

### 配置AI服务 (backend/.env)
```bash
AI_API_KEY=sk-your-api-key       # AI API Key
AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # 阿里云通义千问
AI_MODEL=qwen3-max         # 模型名称
DEVICE=cuda:0             # GPU设备
```

### Key Notes for Agents
- **No `pyproject.toml`, `setup.py`, or package config** — this is a script collection, not an installable package
- **`requirements.txt` is incomplete** — many implicit deps (aiohttp, httpx, redis, watchdog, etc.)
- **Some files have stale imports** — `hazard_detector/danger_detector.py` imports `from src.utils import Utils` (should be `from utils import Utils`); `frame_sender.py` has similar issues
- **`hazard_detector/__init__.py` is empty** — modules are run as scripts, not imported as a package
- **Two duplicate `Utils` classes** exist in `hazard_detector/utils.py` and `esay_detector/utils.py` — keep them in sync when modifying
