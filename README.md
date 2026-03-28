# TennisCoach AI

A web application that analyzes tennis video footage, compares your biomechanics against top ATP/WTA professional players, and delivers personalized coaching feedback.

---

## What it does

Upload a short video of your serve or forehand, choose a pro player to compare against, and receive:

- A **similarity score** (0–100%) showing how closely your mechanics match the pro
- A **phase-by-phase breakdown** — preparation, loading, contact, follow-through
- **AI coaching feedback** in plain language: what's wrong, why it matters, and a specific drill to fix it

---

## Current Status

**Phase 1 MVP — In development**

| Feature | Status |
|---|---|
| F1 — Video upload & pose extraction | In development |
| F2 — Pro player comparison (DTW alignment) | Planned |
| F3 — Biomechanical analysis report | Planned |
| F4 — AI coaching feedback (Gemini) | Planned |
| F5 — User account & history | Planned |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router) + Tailwind CSS + TypeScript |
| Backend API | FastAPI (Python 3.11) |
| ML Inference | Modal.com (serverless GPU/CPU) |
| Pose Estimation | MediaPipe BlazePose |
| Temporal Alignment | DTW — C++17 core module via pybind11 |
| LLM Coaching | Google Gemini 2.5 Flash |
| Database | PostgreSQL (Supabase) |
| Auth | Supabase Auth |
| File Storage | AWS S3 |
| Payments | Stripe |

---

## Project Structure

```
tennis-coach-app/
├── frontend/               Next.js web app
│   └── src/
│       ├── app/
│       │   └── analyze/
│       │       ├── new/            Upload page
│       │       └── [job_id]/
│       │           └── status/     Processing status page
│       ├── components/analyze/     UI components
│       ├── lib/api.ts              API client
│       └── types/analysis.ts      Shared TypeScript types
│
├── backend/                FastAPI backend
│   └── app/
│       ├── api/v1/         Route handlers
│       ├── core/           Supabase client, S3 client, JWT auth
│       ├── schemas/        Pydantic request/response models
│       └── services/       Business logic (quota, job queue)
│
├── worker/                 Modal.com processing worker
│   └── worker.py           Full video analysis pipeline
│
├── core/                   C++ performance modules
│   └── src/
│       ├── keypoint_normalizer   Torso-scale normalization
│       ├── joint_angle_calculator  Per-frame 3D angle computation
│       ├── dtw_aligner           Dynamic Time Warping alignment
│       ├── similarity_scorer     0–100 similarity score
│       └── bindings.cpp          pybind11 Python bindings
│
├── supabase/
│   ├── migrations/         SQL schema migrations
│   └── seed/               Seed data (pro player catalog)
│
└── design/
    └── F1-video-upload-analysis.md   Feature design document
```

---

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.11+
- A [Supabase](https://supabase.com) project
- An [AWS](https://aws.amazon.com) account with an S3 bucket
- A [Modal](https://modal.com) account
- (Optional) CMake + pybind11 to build C++ modules

---

### 1. Database setup

Apply migrations to your Supabase project in order:

```bash
# Using the Supabase CLI
supabase db push

# Or manually in the Supabase SQL editor — run in order:
supabase/migrations/001_pro_players.sql
supabase/migrations/002_analysis_jobs.sql
supabase/migrations/003_users_upload_quota.sql

# Then seed the pro player catalog
supabase/seed/001_pro_players.sql
```

---

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Supabase, AWS, and Modal credentials

uvicorn app.main:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

**Required environment variables** (see `backend/.env.example`):

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (server-side only) |
| `SUPABASE_JWT_SECRET` | JWT secret for token verification |
| `AWS_ACCESS_KEY_ID` | AWS credentials for S3 |
| `AWS_SECRET_ACCESS_KEY` | |
| `S3_BUCKET_NAME` | Bucket for video storage |

---

### 3. Frontend

```bash
cd frontend
npm install

cp .env.local.example .env.local
# Edit .env.local with your API URL and Supabase public keys

npm run dev
# App available at http://localhost:3000
```

**Required environment variables** (see `frontend/.env.local.example`):

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend URL (default: `http://localhost:8000`) |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase public anon key |

---

### 4. Worker

The Modal worker processes videos asynchronously. It polls Supabase for queued jobs every 10 seconds.

```bash
cd worker
pip install modal

# Authenticate with Modal
modal token new

# Create a Modal secret with all required env vars
modal secret create tennis-coach-secrets \
  SUPABASE_URL=... \
  SUPABASE_SERVICE_ROLE_KEY=... \
  AWS_ACCESS_KEY_ID=... \
  AWS_SECRET_ACCESS_KEY=... \
  S3_BUCKET_NAME=...

# Deploy the worker
modal deploy worker.py

# Or run locally for development
modal run worker.py
```

---

### 5. C++ Core (optional for MVP)

The C++ modules accelerate pose normalization, DTW alignment, and similarity scoring. The Python worker includes a pure-Python fallback so you can develop without building them.

To build:

```bash
cd core
pip install pybind11 cmake
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
# Produces tennis_core.so — place on PYTHONPATH for the worker
```

---

## API Reference

Base URL: `http://localhost:8000/api/v1`

All endpoints require a Supabase JWT in the `Authorization: Bearer <token>` header.

| Method | Path | Description |
|---|---|---|
| `GET` | `/pro-players` | List pro players; filter with `?shot_type=serve` |
| `POST` | `/analysis/upload` | Upload video and start analysis job |
| `POST` | `/analysis/presign` | Get a presigned S3 URL for large file uploads |
| `POST` | `/analysis/{job_id}/confirm` | Confirm a presigned upload and trigger processing |
| `GET` | `/analysis/{job_id}/status` | Poll job status and progress |
| `GET` | `/health` | Health check |

Interactive API docs are available at `/docs` when the backend is running.

---

## Video Processing Pipeline

```
User uploads video (MP4 or MOV)
  → S3 storage
  → Modal worker picks up job
      1. Download video from S3
      2. FFmpeg transcode → H.264 MP4 (handles iOS HEVC automatically)
      3. MediaPipe BlazePose — 33 keypoints × N frames
      4. Stroke phase detection (velocity-based heuristic)
      5. Keypoint normalization (C++ module)
      6. Persist keypoints + phases to PostgreSQL
      7. Update job status → frontend polls for completion
```

Processing targets: < 90 seconds (free tier) / < 30 seconds (pro tier).

---

## User Tiers

| | Free | Pro ($9.99/month) |
|---|---|---|
| Uploads/month | 3 | Unlimited |
| Shot types | Serve only | Serve + Forehand (MVP) |
| Pro players | 2 | All 5 (MVP) / 20 (Phase 2) |
| Report history | Last 5 | Full |
| Processing priority | Standard | Priority |

---

## Roadmap

**Phase 1 — MVP (current)**
- Web app with serve and forehand analysis
- 5 pro players
- C++ DTW + angle modules
- Gemini coaching feedback

**Phase 2 — Expansion**
- All 4 shot types (backhand, volley)
- 20 pro players (top-10 ATP + top-10 WTA)
- YOLOv8-Pose upgrade
- Skeleton overlay visualization
- Progress charts

**Phase 3 — Mobile**
- React Native iOS + Android
- On-device inference (Core ML / TFLite)
- Real-time overlay

---

## Infrastructure Costs (estimated at 500 users)

| Service | ~Monthly Cost |
|---|---|
| AWS S3 | $3–9 |
| Modal.com | $0 (free credit covers MVP scale) |
| Supabase Pro | $25 |
| Gemini 2.5 Flash | ~$2 |
| Stripe fees | ~$330 |
| **Total** | **~$360–366** |

See `design/F1-video-upload-analysis.md §13` for full cost breakdown and alternatives.

---

## Design Documents

- [`design/F1-video-upload-analysis.md`](design/F1-video-upload-analysis.md) — Video upload & analysis feature design
