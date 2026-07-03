# Construction Hazard Detection — 施工现场安全隐患检测系统

基于 YOLO 目标检测的施工现场安全智能监控系统，支持图片/视频上传检测、违规实时分析、AI 智能报告、案例库管理等全流程功能，适用于施工现场安全管理人员进行日常巡检、违规记录和安全教育培训。

---

## Features

### Detection & Recognition

- **Multi-Model Detection** — Dual YOLO models (PPE detection + fire/smoke detection) recognizing hardhats, masks, personnel, machinery, vehicles, safety cones, utility poles, fire, and smoke
- **7 Violation Rules** — Real-time violation detection engine covering PPE compliance, restricted area intrusion, machinery near utility poles, fire, and smoke
- **Image Detection** — Upload single images for detection with annotated visualization
- **Video Detection** — Upload video files for frame-by-frame detection with WebSocket streaming, configurable detection intervals, and automatic video cleanup after processing
- **Detection Profiles** — Save and load detection configuration templates (model selection, threshold, danger rule toggles) for quick reuse

### Data Management

- **Detection Records** — Complete record of every detection session with statistics, violation details, and screenshots
- **History Query** — Paginated record list with date range and file type filtering
- **Statistics Dashboard** — Home page with total counts, 7-day trends, and violation type distribution (ECharts)
- **Violation Screenshots** — Automatic screenshot capture for each violation type, embedded in reports

### Safety Case Management

- **Auto Case Creation** — One-click case generation from detection records
- **Case Classification** — By type (no hardhat / dangerous operation / other) and severity (low / medium / high / critical)
- **Case CRUD** — Full create, read, update, delete with keyword search and filters
- **Seed Data** — 10 preset safety cases auto-initialized on first startup

### AI-Powered Analysis

- **AI Violation Report** — Generate structured violation analysis reports using DeepSeek / Qwen / OpenAI-compatible APIs
- **Report Structure** — Basic info + detection summary + violation details (templated descriptions/suggestions) + safety assessment (overall evaluation / risk factors / key findings) + overall recommendations
- **Single Record Analysis** — Time-dimension analysis of a single detection record
- **Date Range Analysis** — Comprehensive analysis across multiple records with daily trends and recurring violation patterns
- **Offline Fallback** — Graceful degradation to template-based reports when AI service is unavailable
- **Word Export** — One-click .docx download with embedded violation screenshots

### Real-Time Video Processing

- **ByteTrack Integration** — Ultralytics built-in ByteTrack assigns unique IDs to each target for cross-frame tracking
- **Throttled Detection** — Configurable detection interval (0.5–10s); non-detection frames reuse cached results
- **Sequential Model Execution** — PPE and fire models run sequentially (GPU parallelism yields only ~9% gain)
- **Cached Frame Display** — Detection boxes and polygons persist between detection intervals for smooth playback

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend                          │
│              Vue 3 + TypeScript                      │
│         Axios ←→ WebSocket ←→ ECharts               │
└───────────────────┬─────────────────────────────────┘
                    │ HTTP / WebSocket
┌───────────────────▼─────────────────────────────────┐
│                   Backend                            │
│              FastAPI + SQLAlchemy                    │
│   ┌────────────┐ ┌────────────┐ ┌────────────────┐  │
│   │ YOLO       │ │ Danger     │ │  AI Service    │  │
│   │ Detector   │ │ Detector   │ │ (报告生成)     │  │
│   └────────────┘ └────────────┘ └────────────────┘  │
│   ┌────────────┐ ┌────────────┐ ┌────────────────┐  │
│   │ Case       │ │ Detection  │ │  Report        │  │
│   │ Service    │ │ Service    │ │  Service       │  │
│   └────────────┘ └────────────┘ └────────────────┘  │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│                 Storage                              │
│  SQLite │ Uploads │ Violation Screenshots │ Reports  │
│  ┌──────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐ │
│  │Detection │ │Violation│ │Violation │ │ Cases    │ │
│  │Records   │ │Counts   │ │Details   │ │          │ │
│  └──────────┘ └────────┘ └──────────┘ └──────────┘ │
└─────────────────────────────────────────────────────┘
```

### Video Detection Pipeline

```
 Frame Input (read + encode + WebSocket send)
     │
     ▼
 ┌─────────────────────────────────────────┐
 │ Detection Gate (fixed interval, default 0.5s) │
 │ if time.now - last_detection >= interval:     │
 │   → Run PPE model (36ms) + Fire model (18ms)  │
 │   → Run DangerDetector (violation rules)       │
 │   → Update cached warnings + polygons          │
 │ else:                                          │
 │   → Reuse cached results                       │
 └─────────────────────┬─────────────────────────┘
                       │
 ┌─────────────────────▼─────────────────────────┐
 │ Output: frame data (image + detections +       │
 │ violations + cone polygons)                    │
 │ Sent every frame (smooth playback)             │
 └───────────────────────────────────────────────┘
```

### Performance (GPU: CUDA, Models: yolo26l + fire_smoke)

| Metric | Value |
|--------|-------|
| PPE Inference | 36.5ms ±0.7ms |
| Fire Inference | 18.8ms ±0.6ms |
| Sequential Total | 55.3ms ±0.8ms |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.9+, FastAPI, SQLAlchemy 2.0 |
| **Database** | SQLite |
| **Object Detection** | Ultralytics YOLO (v8/v11) |
| **Image Processing** | OpenCV, NumPy, Pillow |
| **Geometric Analysis** | Shapely, scikit-learn |
| **AI Analysis** | OpenAI SDK (DeepSeek / Qwen compatible) |
| **Report Generation** | python-docx |
| **Frontend** | Vue 3 + TypeScript (Composition API) |
| **UI** | Element Plus |
| **Charts** | ECharts 6 |
| **HTTP** | Axios |
| **Build** | Vite |

---

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- (Optional) CUDA-capable GPU

### 1. Backend Installation

```bash
# Create virtual environment (optional)
python -m venv venv
# source venv/bin/activate  (Linux/Mac)
# venv\Scripts\activate     (Windows)

# Install dependencies
pip install -r backend/requirements.txt
pip install httpx aiofiles python-docx
```

### 2. Configure Environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

```env
AI_API_KEY=sk-your-api-key
AI_BASE_URL=https://api.deepseek.com/v1
AI_MODEL=deepseek-chat
DEVICE=cuda:0
```

### 3. Download Models

Place YOLO model files (e.g., `yolo26l.pt`, `fire_smoke.pt`) into `backend/models/`.

### 4. Start Backend

```bash
cd backend
python run.py
```

API server starts at `http://localhost:8000`

### 5. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend dev server starts at `http://localhost:5173`

---

## API Endpoints

API documentation available at `http://localhost:8000/docs` (Swagger UI).

### Upload

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/v1/upload/image` | Upload image (jpg/jpeg/png/bmp/webp, ≤10MB) |
| POST | `/api/v1/upload/video` | Upload video (mp4/avi/mov/mkv/flv, ≤200MB) |

### Detection

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/v1/image/detect` | Image hazard detection (returns annotated base64 + violations) |
| WS | `/ws/video/detect/{path}` | WebSocket video detection (actions: start/pause/resume/stop) |

### Records & History

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/v1/records` | Paginated records (filters: file_type, start_date, end_date) |
| GET | `/api/v1/records/{id}` | Single record detail |
| GET | `/api/v1/records/{id}/violations` | Violation list for a record |
| DELETE | `/api/v1/records/{id}` | Delete record and associated screenshots |
| GET | `/api/v1/stats` | Statistics (totals, today, 7-day trends, violation distribution) |

### Safety Cases

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/v1/cases` | Create a case manually |
| POST | `/api/v1/cases/from-record/{id}` | Auto-create case from detection record |
| GET | `/api/v1/cases` | Paginated cases (filters: case_type, severity, keyword) |
| GET | `/api/v1/cases/{id}` | Case detail |
| PUT | `/api/v1/cases/{id}` | Update case |
| DELETE | `/api/v1/cases/{id}` | Delete case |

### Reports & AI Analysis

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/v1/report/generate` | Generate Word report (optional start_date/end_date) |
| POST | `/api/v1/report/ai-analysis` | AI analysis (record_id for single, or start_date/end_date for range) |
| POST | `/api/v1/report/ai-analysis/download` | Download AI report as .docx with screenshots |
| GET | `/api/v1/report/download/{filename}` | Download generated report |

### Detection Profiles

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/v1/profiles` | List profiles (optional type filter) |
| POST | `/api/v1/profiles` | Create profile |
| GET | `/api/v1/profiles/{id}` | Get profile detail |
| PUT | `/api/v1/profiles/{id}` | Update profile |
| DELETE | `/api/v1/profiles/{id}` | Delete profile |

### Models

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/v1/models` | List available detection models |

---

## Frontend Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | Home | Statistics dashboard with ECharts |
| `/image-detect` | ImageDetect | Image upload and hazard detection |
| `/video-detect` | VideoDetect | Video upload with WebSocket streaming |
| `/history` | History | Detection records list with filters |
| `/detail/:id` | Detail | Record detail + AI analysis + screenshots |
| `/cases` | CaseList | Safety case management |
| `/cases/create` | CaseCreate | Create new case |
| `/cases/:id` | CaseDetail | Case detail / edit |
| `/profiles` | DetectionProfiles | Detection profile management |

---

## Violation Detection Rules

| Type Key | Description | Detection Logic |
|----------|-------------|-----------------|
| `warning_no_hardhat` | Worker without hardhat | Person overlapping NO-Hardhat bounding box |
| `warning_no_mask` | Worker without mask | NO-Mask detected |
| `warning_no_safety_vest` | Worker without safety vest | Person overlapping NO-Safety Vest bounding box |
| `warning_people_in_controlled_area` | Person in cone-restricted zone | Person inside polygon formed by Safety Cones |
| `detect_machinery_close_to_pole` | Machinery near utility pole | Machinery/Vehicle within danger circle of Utility Pole |
| `warning_fire` | Fire detected | Fire model detects fire target |
| `warning_smoke` | Smoke detected | Fire model detects smoke target |

### Severity Levels

| Type | Severity |
|------|----------|
| `warning_no_hardhat` | High |
| `warning_no_mask` | Low |
| `warning_no_safety_vest` | Low |
| `warning_people_in_controlled_area` | High |
| `detect_machinery_close_to_pole` | High |
| `warning_fire` | Critical |
| `warning_smoke` | High |

### YOLO Class ID Mapping

| ID | Label | Description |
|----|-------|-------------|
| 0 | Hardhat | Safety helmet |
| 1 | Mask | Face mask |
| 2 | NO-Hardhat | Person without hardhat |
| 3 | NO-Mask | Person without mask |
| 4 | NO-Safety Vest | Person without safety vest |
| 5 | Person | Worker |
| 6 | Safety Cone | Traffic cone |
| 7 | Safety Vest | Safety vest (object) |
| 8 | Machinery | Construction machinery |
| 9 | Utility Pole | Power/utility pole |
| 10 | Vehicle | Vehicle |

---

## AI Analysis Service

### Configuration

```env
AI_API_KEY=sk-your-api-key
AI_BASE_URL=https://api.deepseek.com/v1          # DeepSeek
AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # Alibaba Qwen
AI_MODEL=deepseek-chat                            # or qwen3-max
```

### Report Structure

- **Basic Info**: Report ID, time, filename / analysis period, detection type, duration, total targets
- **Summary**: Total violations, risk level
- **Violation Details**: Type, count, first occurrence time, severity, description (template), suggestion (template)
- **Safety Assessment**: Overall evaluation, risk factors (list), key findings
- **Overall Suggestions**: Prioritized corrective actions
- **Expert Signature**: AI safety expert

> Violation descriptions and suggestions use built-in templates; AI only generates the safety assessment and overall suggestions, ensuring offline report generation capability.

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/                   # FastAPI route handlers
│   │   │   ├── upload.py          # File upload endpoints
│   │   │   ├── image_detect.py    # Image detection endpoint
│   │   │   ├── video_detect.py    # WebSocket video detection
│   │   │   ├── history.py         # Records, stats, violations
│   │   │   ├── report.py          # Reports + AI analysis
│   │   │   ├── cases.py           # Safety cases CRUD
│   │   │   ├── models.py          # Model listing
│   │   │   └── detection_profiles.py  # Detection profiles
│   │   ├── core/                  # Detection engine
│   │   │   ├── detector.py        # YOLO model inference
│   │   │   ├── danger_rules.py    # 7 violation rule detectors
│   │   │   ├── streamer.py        # Video WebSocket streaming
│   │   │   ├── annotator.py       # Frame annotation drawing
│   │   │   └── model_registry.py  # Model management
│   │   ├── models/                # SQLAlchemy models
│   │   │   ├── detection.py       # DetectionRecord, Violation
│   │   │   ├── violation_count.py # Aggregated violation counts
│   │   │   ├── case.py            # Safety case
│   │   │   └── detection_profile.py  # Detection profile
│   │   ├── schemas/               # Pydantic schemas
│   │   ├── services/              # Business logic
│   │   │   ├── detection_service.py    # Record CRUD + stats
│   │   │   ├── ai_service.py           # AI analysis (single/range)
│   │   │   ├── report_service.py       # Word document generation
│   │   │   ├── case_service.py         # Case CRUD + auto-create
│   │   │   ├── detection_profile_service.py  # Profile CRUD
│   │   │   └── seed_cases.py           # Seed data
│   │   ├── utils/
│   │   │   └── bbox_utils.py      # Geometry utilities
│   │   ├── config.py              # Environment configuration
│   │   ├── database.py            # SQLAlchemy engine/session
│   │   └── main.py                # FastAPI application entry
│   ├── models/                    # YOLO model files
│   ├── uploads/                   # Uploaded files
│   ├── violations/                # Violation screenshots
│   ├── reports/                   # Generated reports
│   ├── config/
│   │   └── models.json            # Model configurations
│   ├── migrate_violation_counts.py  # Data migration script
│   └── run.py                     # Server startup
├── frontend/
│   ├── src/
│   │   ├── views/                 # Vue page components
│   │   ├── api/                   # Axios API wrappers
│   │   ├── router/                # Vue Router
│   │   ├── stores/                # Pinia state
│   │   └── components/            # Shared UI components
│   └── package.json
├── esay_detector/                 # Standalone local detection
├── hazard_detector/                # Legacy full detection module
├── docs/
│   └── datasets.md                # Open dataset references
└── AGENTS.md                     # AI agent instructions
```

---

## License

本项目为内部安全管理系统，仅供学习和参考使用。
