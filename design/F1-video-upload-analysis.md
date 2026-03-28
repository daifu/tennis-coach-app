# F1 — Video Upload & Analysis: Design Document

**Feature**: F1 — Video Upload & Analysis
**PRD Version**: 0.2
**Date**: 2026-03-21
**Status**: Draft

---

## 1. Overview

F1 is the entry point for all analysis in TennisCoach AI. It covers the full lifecycle from a user uploading a video clip to the system delivering extracted pose data and stroke phases ready for downstream comparison (F2) and coaching (F3/F4).

**Scope for MVP (Phase 1):**
- Shot types: serve and forehand only
- Stroke type: manual selection by user (auto-detection is post-MVP per decision D1)
- Max video length: 60 seconds
- Supported formats: MP4, MOV
- Processing: asynchronous with status notification

---

## 2. User Flow

```
User taps "Analyze My Stroke"
  → Selects shot type (Serve | Forehand)
  → Selects reference pro player (5 available in MVP)
  → Uploads video (drag-and-drop or file picker)
  → Sees processing screen with progress indicator
  → Receives notification when analysis is complete
  → Navigates to report page (F3/F4 output)
```

### 2.1 Camera Guidance Screen
Before the file picker opens, a guidance modal is shown with:
- Optimal angle: side-on view
- Camera height: hip height
- Distance from player: 10–15 feet
- A warning is shown post-upload if the video angle appears suboptimal (flagged by pose confidence score)

---

## 3. Architecture

### 3.1 Components

```
┌─────────────────────────────────────────────────────┐
│  Next.js Frontend                                   │
│  - Upload UI (drag-drop + file picker)              │
│  - Camera guidance modal                           │
│  - Processing status screen (polling / WebSocket)  │
└───────────────┬────────────────────────────────────┘
                │ HTTPS multipart or presigned S3 URL
┌───────────────▼────────────────────────────────────┐
│  FastAPI Backend                                    │
│  - POST /analysis/upload                           │
│  - GET  /analysis/{job_id}/status                  │
│  - Enqueues job after S3 upload confirmed           │
└───────────────┬────────────────────────────────────┘
                │ Job queue (Supabase DB or Redis)
┌───────────────▼────────────────────────────────────┐
│  Modal.com Serverless GPU Worker                   │
│  - Pulls job from queue                            │
│  - Runs MediaPipe BlazePose                        │
│  - Runs stroke phase detector                      │
│  - Calls C++ normalizer via pybind11               │
│  - Writes results to PostgreSQL                    │
│  - Updates job status → triggers notification      │
└────────────────────────────────────────────────────┘
```

### 3.2 Storage

| Data | Store | Notes |
|---|---|---|
| Raw video file | AWS S3 | Encrypted at rest; deleted after 90 days (Free) / 1 year (Pro) |
| Per-frame keypoints (33 × N frames) | PostgreSQL (Supabase) | JSONB or normalized float array |
| Stroke phase boundaries | PostgreSQL | Frame index ranges for each phase |
| Job status & metadata | PostgreSQL | `analysis_jobs` table |

---

## 4. API Design

### 4.0 GET `/api/v1/pro-players`

Returns the catalog for the player picker. Called when the upload page loads.

**Auth**: Required (Supabase JWT)

**Query params**:

| Param | Type | Notes |
|---|---|---|
| `shot_type` | enum | Optional. If provided, filters to players who have reference data for that shot type. |

**Response** `200 OK`:
```json
{
  "players": [
    {
      "id": "uuid",
      "name": "Carlos Alcaraz",
      "gender": "atp",
      "thumbnail_url": "https://...",
      "shot_types": ["serve", "forehand"]
    }
  ]
}
```

Only players with `is_active = true` are returned.

### 4.1 POST `/api/v1/analysis/upload`

Initiates an analysis job.

**Auth**: Required (Supabase JWT)

**Request** (multipart/form-data):

| Field | Type | Required | Notes |
|---|---|---|---|
| `video` | file | Yes | MP4 or MOV, max 60s, max ~150MB |
| `shot_type` | enum | Yes | `serve` \| `forehand` (MVP) |
| `pro_player_id` | string | Yes | References pro player library |

**Response** `202 Accepted`:
```json
{
  "job_id": "uuid",
  "status": "queued",
  "estimated_wait_seconds": 30
}
```

**Error responses**:

| Status | Code | Condition |
|---|---|---|
| 400 | `INVALID_FORMAT` | File is not MP4/MOV |
| 400 | `VIDEO_TOO_LONG` | Duration > 60 seconds |
| 400 | `INVALID_SHOT_TYPE` | Unrecognized shot type |
| 400 | `PLAYER_SHOT_TYPE_UNAVAILABLE` | Chosen pro has no reference data for the selected shot type |
| 402 | `UPLOAD_LIMIT_REACHED` | Free tier: 3 uploads/month exhausted |
| 413 | `FILE_TOO_LARGE` | Exceeds server-side size cap |

### 4.2 GET `/api/v1/analysis/{job_id}/status`

Polls job progress. Used when WebSocket is unavailable.

**Response**:
```json
{
  "job_id": "uuid",
  "status": "queued | processing | complete | failed",
  "progress_pct": 65,
  "stage": "pose_extraction",
  "report_id": "uuid | null"
}
```

`stage` values: `queued` → `pose_extraction` → `phase_detection` → `normalization` → `complete`

### 4.3 WebSocket `/ws/analysis/{job_id}`

Real-time status push. Sends the same payload shape as the polling endpoint whenever stage or progress changes. Falls back gracefully to polling if WebSocket is unavailable.

---

## 5. Video Upload Flow

Two strategies depending on file size:

### 5.1 Direct Upload via API (files ≤ 50MB)
1. Client sends multipart POST to FastAPI
2. FastAPI streams file directly to S3
3. FastAPI creates `analysis_jobs` row and enqueues job
4. Returns `job_id` to client

### 5.2 Presigned S3 URL (files > 50MB)
1. Client calls `POST /api/v1/analysis/presign` with file metadata
2. FastAPI creates a pending `analysis_jobs` row and returns a presigned S3 PUT URL + `job_id`
3. Client uploads directly to S3
4. Client calls `POST /api/v1/analysis/{job_id}/confirm` to trigger job queue
5. FastAPI verifies the S3 object exists, then enqueues

**Target**: < 5s for a 50MB upload on a standard connection (per §5.4 of PRD).

---

## 6. Processing Pipeline (Modal Worker)

Each step maps to §5.2 of the PRD.

```
Step 1 — Download video from S3
Step 2 — Validate video (duration, codec, frame count)
Step 3 — Pose extraction: MediaPipe BlazePose
          → 33 keypoints × N frames (x, y, z, visibility)
          → Flag low-confidence frames (visibility < threshold)
          → If >30% frames are low-confidence: mark job with WARNING_POOR_ANGLE
Step 4 — Stroke phase detection
          → Segment clip into: preparation → loading → contact → follow-through
          → MVP heuristic: velocity-based keypoint analysis (wrist + elbow)
Step 5 — Normalize keypoints
          → Torso-scale normalization via C++ `keypoint_normalizer` module
Step 6 — Persist results
          → Write keypoints + phase boundaries to PostgreSQL
          → Update job status to "complete"
          → Emit WebSocket / set polling flag
```

### 6.1 FFmpeg Preprocessing (Before Pose Extraction)

All uploaded videos are unconditionally transcoded to H.264 MP4 before MediaPipe runs. This handles HEVC/H.265 from iOS recordings and any other codec variation without detection logic. Transcoding via FFmpeg adds ~2–4s per clip, well within the 90s processing budget.

```
ffmpeg -i input.mov -c:v libx264 -preset fast -crf 23 -an output.mp4
```

Audio is stripped (`-an`) as it is not used in analysis.

### 6.2 Failure Handling

| Failure | Behavior |
|---|---|
| No person detected | Job fails with `NO_PLAYER_DETECTED`; user shown guidance to re-upload |
| FFmpeg transcode failure | Job fails with `TRANSCODE_FAILED`; user prompted to re-upload in MP4 format |
| Worker timeout (> 120s) | Job retried once; if second attempt fails, status = `failed` |
| Modal GPU unavailable | Job stays `queued`; retried when capacity available |

---

## 7. Database Schema

### `pro_players`

Shared catalog consumed by F1 (player picker UI, upload validation) and F2 (reference pose templates). F1 only reads this table — population and pose template management are owned by F2.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | TEXT | e.g. `"Carlos Alcaraz"` |
| `gender` | VARCHAR | `atp` \| `wta` |
| `thumbnail_url` | TEXT | S3 URL for player photo shown in picker |
| `shot_types` | TEXT[] | Shot types with available reference data e.g. `["serve", "forehand"]` |
| `is_active` | BOOL | Toggles picker visibility without deleting; set false when reference data is incomplete |

**MVP seed data**: 5 players × 2 shot types (serve + forehand). The `<ProPlayerPicker>` in F1 filters by `shot_types` to ensure only players with reference data for the selected shot type are shown, preventing a job from entering the pipeline with no valid comparison target.

### `analysis_jobs`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK | References `users` |
| `shot_type` | VARCHAR | `serve`, `forehand` |
| `pro_player_id` | UUID FK | References `pro_players` |
| `video_s3_key` | TEXT | S3 object key |
| `status` | VARCHAR | `queued`, `processing`, `complete`, `failed` |
| `stage` | VARCHAR | Current processing stage |
| `progress_pct` | INT | 0–100 |
| `warning_code` | VARCHAR | Optional: `WARNING_POOR_ANGLE`, etc. |
| `error_code` | VARCHAR | Optional: failure reason |
| `report_id` | UUID FK | Populated on completion; references `analysis_reports` |
| `created_at` | TIMESTAMPTZ | |
| `completed_at` | TIMESTAMPTZ | |

### `analysis_keypoints`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `job_id` | UUID FK | |
| `frame_index` | INT | |
| `keypoints` | JSONB | Array of 33 `{x, y, z, visibility}` objects |
| `phase` | VARCHAR | `preparation`, `loading`, `contact`, `follow_through` |

---

## 8. Frontend Components

### 8.1 Upload Page (`/analyze/new`)

- **`<ShotTypeSelector>`** — toggle between Serve / Forehand (MVP)
- **`<ProPlayerPicker>`** — scrollable grid of 5 MVP pro players
- **`<CameraGuideModal>`** — shown before file picker; shows placement diagram
- **`<VideoDropzone>`** — drag-and-drop + file picker; client-side validates format and duration before upload
- **`<UploadProgressBar>`** — shows upload progress via XHR `onprogress`

### 8.2 Processing Status Page (`/analyze/{job_id}/status`)

- Shown immediately after upload completes
- Polls `GET /analysis/{job_id}/status` every 3 seconds (or subscribes via WebSocket)
- Displays current stage as a labeled stepper
- Estimated wait shown based on tier (< 90s Free, < 30s Pro)
- On completion: auto-redirects to report page

### 8.3 Client-Side Validation (before upload)

| Check | Rule |
|---|---|
| File type | Accept `.mp4`, `.mov` only |
| File size | Warn if > 100MB (estimated proxy for duration) |
| Duration | Read via `<video>` element `duration` property; reject if > 60s |

---

## 9. Tier Enforcement

| Limit | Free | Pro |
|---|---|---|
| Uploads/month | 3 | Unlimited |
| Processing priority | Standard queue | Priority queue (separate Modal pool) |
| Shot types available | Serve only | All (Forehand in MVP Phase 1) |

Tier checks are enforced in FastAPI at the `POST /analysis/upload` endpoint before S3 upload begins. Free-tier upload count is tracked in the `users` table (`free_uploads_this_month`, reset monthly via cron).

---

## 10. Performance Targets

Drawn from PRD §5.4:

| Metric | Target |
|---|---|
| Video upload (50MB) | < 5s |
| Analysis turnaround — Free | < 90s end-to-end |
| Analysis turnaround — Pro | < 30s end-to-end |
| Keypoint normalizer (C++ module) | < 20ms |
| Status polling interval | 3s |

---

## 11. Security & Privacy

- All video uploads transferred over HTTPS only
- S3 objects stored with server-side encryption (AES-256)
- S3 objects are private; never publicly accessible — served only via presigned URLs with short TTL (15 min)
- Videos not used for model training without explicit user opt-in
- Free tier: videos deleted from S3 after 90 days; Pro tier: 1 year
- User can trigger immediate deletion via account settings (GDPR/CCPA)
- `user_id` verified via Supabase JWT on every API call; users can only access their own jobs

---

## 12. Decisions & Open Questions

### 12.1 Resolved

| # | Decision | Rationale |
|---|---|---|
| D-F1-1 | **Unconditional FFmpeg transcode to H.264 before pose extraction** | iOS records HEVC by default; detecting codec first adds complexity with no benefit. Transcode cost (~2–4s) fits comfortably within the 90s budget. |
| D-F1-2 | **Polling (3s interval) as default; WebSocket deferred** | Zero infra overhead for MVP. 90s/30s wait times make real-time updates low-priority. Add WebSocket when user feedback identifies it as a pain point. |
| D-F1-3 | **Phase detection via velocity-based wrist/elbow heuristic (MVP)** | Sufficient for serve and forehand; avoids building a separate classifier. Review trigger: if user-reported phase errors exceed 15% after 100 sessions, prioritize a learned classifier. |
| D-F1-4 | **`WARNING_POOR_ANGLE` threshold: avg visibility < 0.6 on 6 critical keypoints for > 30% of frames** | Based on MediaPipe BlazePose visibility semantics. Critical keypoints: both shoulders, both hips, dominant wrist, dominant elbow. Calibrate after first 50 real uploads. |
| D-F1-5 | **`<ProPlayerPicker>` filters by `shot_types`; API validates `pro_player_id` × `shot_type` match** | Prevents jobs entering the pipeline with no valid reference target. |

### 12.2 Open

- [ ] **Phase detection accuracy post-launch**: After 100+ real sessions, measure phase boundary error rate. If > 15% user-reported issues, scope a lightweight stroke segmentation classifier.
- [ ] **Poor angle threshold calibration**: Initial threshold (visibility < 0.6, > 30% of frames) is a starting point. Revisit after first 50 uploads with real court footage.

---

## 13. Infrastructure Costs & Alternatives

> Estimates based on MVP scale: ~500 users, ~1,000 video analyses/month, ~50 GB video storage.

### 13.1 AWS S3 — Video Storage

| Dimension | Rate |
|---|---|
| Storage (first 50 TB) | $0.023/GB/month |
| Inbound uploads | Free |
| Outbound egress (first 100 GB/month) | Free |
| Outbound egress (next 9.9 TB) | $0.09/GB |
| PUT/POST requests | $0.005/1,000 |

**Estimated monthly cost: ~$1–$5/month** at 50 GB storage + moderate egress. If users regularly stream/re-download their videos, egress can push to ~$9/month at 200 GB.

**Alternatives:**

| Service | Storage | Egress | Est. Monthly | Key Trade-off |
|---|---|---|---|---|
| **Cloudflare R2** | $0.015/GB | **$0 (free)** | ~$0.75–$1.50 | Zero egress fees — dramatically cheaper at scale. No native CDN without Workers. |
| **Backblaze B2** | $0.006/GB | Free via Cloudflare CDN | ~$0.25–$0.30 | Cheapest storage. Free egress through Cloudflare partnership. Less S3 feature parity. |
| **Wasabi** | $0.007/GB | $0 | ~$0.35 | 90-day minimum billing period — penalizes frequent deletion (e.g. Free-tier 90-day cleanup). |

**Recommendation:** Start with S3 for ecosystem familiarity. Migrate to **Cloudflare R2** when monthly egress consistently exceeds 100 GB — the zero-egress model becomes a meaningful saving.

---

### 13.2 Modal.com — Serverless GPU Inference

| GPU | Rate/second | Hourly |
|---|---|---|
| CPU (per core) | $0.000054/sec | — |
| T4 | $0.000164/sec | ~$0.59 |
| A10G | $0.000306/sec | ~$1.10 |
| A100 40GB | $0.001036/sec | ~$3.73 |

Free tier: **$30/month** in compute credits on all accounts.

**Estimated monthly cost: $0/month** — MediaPipe BlazePose runs efficiently on CPU. At 1,000 videos × 60 sec average = 60,000 CPU-seconds × $0.000054 = ~$3.24/month, well within the $30 free credit. Even on A10G GPU: 60,000 sec × $0.000306 = ~$18.36/month — still within free tier.

**Alternatives:**

| Service | GPU Rate/sec | Est. Monthly (60K sec) | Key Trade-off |
|---|---|---|---|
| **RunPod Serverless** | ~$0.000190/sec (A10G equiv.) | ~$11.40 | Cheaper raw rates; no comparable free credit. Better value at high volume (100K+ sec/month). |
| **Replicate** | ~$0.000225/sec (T4) | ~$13.50 | Simpler deployment for pre-built models; higher per-second rate. |
| **AWS Lambda (CPU)** | $0.0000167/GB-sec | **~$0** (400K GB-sec free tier) | No GPU; cold starts 5–15s for heavy Python deps. Free tier covers this scale entirely. |

**Recommendation:** Modal for MVP — the $30 free credit makes it effectively free, and the developer experience for ML workloads is superior. Revisit RunPod if monthly GPU spend exceeds $50 consistently.

---

### 13.3 Supabase — PostgreSQL + Auth

| Plan | Price | Included |
|---|---|---|
| Free | $0 | 500 MB DB, 50K MAUs; **pauses after 1 week inactivity** |
| Pro | $25/month | 8 GB DB, 100K MAUs, no pausing |
| Team | $599/month | SOC 2, team roles |

**Estimated monthly cost: $25/month (Pro).** Free plan is technically sufficient at 500 users but project pausing makes it unsuitable for production.

**Alternatives:**

| Service | Est. Monthly | Key Trade-off |
|---|---|---|
| **Neon (Serverless Postgres)** | $0–$19/month | Postgres only — no built-in Auth/Storage/Realtime. Need to add Clerk (~$25+/month) or Auth.js for auth. Scales to zero with no pausing penalty. |
| **Firebase (Firestore + Auth)** | ~$0–$5/month | NoSQL only — poor fit for relational tennis coaching data. Auth is excellent and free. |
| **PlanetScale (MySQL/Vitess)** | $39/month | MySQL-compatible with schema branching; no built-in Auth. More expensive than Supabase at this scale. |

**Recommendation:** Supabase Pro at $25/month. The all-in-one platform (Postgres + Auth + Realtime + Storage) eliminates the need to integrate separate services, which matters for a solo project. Total value exceeds Neon + Clerk by a large margin.

---

### 13.4 Gemini 2.5 Flash API — LLM Coaching Feedback

| Token Type | Rate |
|---|---|
| Input | $0.30/1M tokens |
| Output | $2.50/1M tokens |

**Estimated monthly cost: ~$1.85/month** at 1,000 calls × 2,000 input + 500 output tokens each. Even at 10× scale (~$18.50/month) this remains negligible.

**Alternatives:**

| Model | Input/1M | Output/1M | Est. Monthly (1K calls) | Key Trade-off |
|---|---|---|---|---|
| **GPT-4o Mini** | $0.15 | $0.60 | ~$0.60 | Cheapest option. Strong short-output reasoning. Slightly less nuanced prose. |
| **Gemini 2.5 Flash-Lite** | $0.10 | $0.40 | ~$0.40 | Google's cheapest production model. Negligible quality difference at this volume. |
| **Claude Haiku 4.5** | $1.00 | $5.00 | ~$4.50 | Richest, most natural coaching language. 2–3× more expensive. Worth evaluating for output quality. |

**Recommendation:** The cost difference between all options is less than $5/month at MVP scale — choose based on **output quality**, not cost. Run a blind evaluation of 20 coaching outputs from each model against the PRD's 3-part feedback format before committing.

---

### 13.5 Stripe — Payment Processing

| Fee | Rate |
|---|---|
| Standard card processing | 2.9% + $0.30/transaction |
| Stripe Billing (subscriptions) | +0.7% |
| Effective rate | ~3.6% + $0.30 |
| International cards | +1.5% surcharge |
| Chargeback fee | $15 (non-refundable) |

**Estimated monthly cost:**
- 50 paying users (early stage): ~$33/month in fees on $499.50 revenue
- 500 paying users (MVP target): ~$330/month in fees on $4,995 revenue (~6.6% take rate)

**Alternatives:**

| Service | Rate | Est. per $9.99 sub | 500-user monthly fees | Key Trade-off |
|---|---|---|---|---|
| **Paddle** (MoR) | 5% + $0.50 | ~$1.00 | ~$500/month | Merchant of Record — handles all global VAT/GST/sales tax automatically. Worth ~$170/month premium if selling internationally. |
| **Lemon Squeezy** (MoR) | 5% + $0.50 | ~$1.00 | ~$500/month | Same MoR benefits as Paddle; simpler DX for solo founders. Stripe-owned. Better for straightforward subscription billing. |
| **Polar.sh** | 4% + Stripe fees | ~$0.96 | ~$480/month | Developer-focused; handles taxes; open-source friendly. Marginally cheaper than Paddle/LS. |

**Recommendation:** Use **Stripe** for domestic-first launch (cheapest per transaction). Switch to **Lemon Squeezy** before scaling internationally to eliminate tax compliance overhead — the ~$170/month premium at 500 users is cheaper than a tax lawyer.

---

### 13.6 Total Monthly Cost Summary

| Service | MVP Launch (~50 paying users) | MVP Target (~500 paying users) |
|---|---|---|
| AWS S3 | ~$1–$2 | ~$3–$9 |
| Modal.com | $0 (free credit) | $0 (free credit) |
| Supabase Pro | $25 | $25 |
| Gemini 2.5 Flash | ~$0.10 | ~$1.85 |
| Stripe (processing fees) | ~$33 | ~$330 |
| **Total** | **~$59–$60/month** | **~$360–$366/month** |
| MRR | ~$499 | ~$4,995 |
| Infra as % of MRR | ~12% | ~7.3% |

Infrastructure costs (excluding Stripe) are ~$26–$35/month regardless of user count at this scale. Stripe fees are the dominant cost and scale linearly with revenue.

---

## 14. Out of Scope (F1 specifically)

- Automatic stroke type detection (post-MVP, per decision D1)
- Backhand and volley shot types (Phase 2)
- Multi-angle video support (post-MVP)
- Real-time / live camera analysis (post-MVP)
- Ball detection or serve speed estimation (post-MVP)
