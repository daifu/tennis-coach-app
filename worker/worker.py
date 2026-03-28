"""
TennisCoach AI — Modal.com Serverless Worker
F1: Video processing pipeline

Pipeline:
  1. Download video from S3
  2. FFmpeg transcode → H.264 MP4
  3. MediaPipe BlazePose — extract 33 keypoints/frame
  4. Stroke phase detection (velocity-based heuristic)
  5. Keypoint normalization (C++ module via pybind11)
  6. Persist keypoints + phases to PostgreSQL
  7. Update job status
"""

import modal
import os

# ---------------------------------------------------------------------------
# Modal app definition
# ---------------------------------------------------------------------------

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libgl1")
    .pip_install_from_requirements("/requirements.txt")
    # C++ core module — built from source during image build
    # .run_commands("cd /core && pip install pybind11 cmake && cmake -B build && cmake --build build --config Release")
)

app = modal.App("tennis-coach-worker", image=image)

# ---------------------------------------------------------------------------
# Helper: update job status in Supabase
# ---------------------------------------------------------------------------

def _update_job(sb, job_id: str, **kwargs):
    sb.table("analysis_jobs").update(kwargs).eq("id", job_id).execute()


def _set_stage(sb, job_id: str, stage: str, progress_pct: int):
    _update_job(sb, job_id, stage=stage, progress_pct=progress_pct, status="processing")


# ---------------------------------------------------------------------------
# Step 1+2: Download from S3 and transcode via FFmpeg
# ---------------------------------------------------------------------------

def download_and_transcode(s3_key: str, tmp_dir: str) -> str:
    import boto3, subprocess

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    raw_path = os.path.join(tmp_dir, "input_raw")
    s3.download_file(os.environ["S3_BUCKET_NAME"], s3_key, raw_path)

    out_path = os.path.join(tmp_dir, "input.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_path, "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an", out_path],
        check=True,
        capture_output=True,
    )
    return out_path


# ---------------------------------------------------------------------------
# Step 3: Pose extraction with MediaPipe BlazePose
# ---------------------------------------------------------------------------

def extract_keypoints(video_path: str) -> tuple[list[list[float]], list[float], int]:
    """
    Returns:
        frames_xyz: list of per-frame flattened keypoints [N][99]  (33 kp × x,y,z)
        frames_vis: list of per-frame mean visibility scores [N]
        fps: video fps
    """
    import cv2
    import mediapipe as mp
    import numpy as np

    mp_pose = mp.solutions.pose
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    frames_xyz: list[list[float]] = []
    frames_vis: list[float] = []

    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        smooth_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = pose.process(rgb)

            if result.pose_world_landmarks:
                lm = result.pose_world_landmarks.landmark
                xyz = []
                vis_list = []
                for pt in lm:
                    xyz.extend([pt.x, pt.y, pt.z])
                    vis_list.append(pt.visibility)
                frames_xyz.append(xyz)
                frames_vis.append(float(np.mean(vis_list)))
            else:
                # No person detected in this frame — append zeros
                frames_xyz.append([0.0] * 99)
                frames_vis.append(0.0)

    cap.release()
    return frames_xyz, frames_vis, fps


# ---------------------------------------------------------------------------
# Step 3b: Poor angle detection
# ---------------------------------------------------------------------------

CRITICAL_KP_INDICES = [11, 12, 23, 24, 14, 16]  # shoulders, hips, dominant elbow, wrist

def check_poor_angle(frames_xyz: list[list[float]], frames_vis: list[float]) -> bool:
    """Returns True if video appears filmed from a poor angle."""
    if not frames_xyz:
        return True
    low_confidence_frames = sum(1 for v in frames_vis if v < 0.6)
    return (low_confidence_frames / len(frames_vis)) > 0.30


# ---------------------------------------------------------------------------
# Step 4: Stroke phase detection (velocity-based heuristic)
# ---------------------------------------------------------------------------

WRIST_R = 16   # right wrist BlazePose index
ELBOW_R = 14   # right elbow

def detect_stroke_phases(
    frames_xyz: list[list[float]], fps: float, shot_type: str
) -> dict[int, str]:
    """
    Returns a dict mapping frame_index -> phase name.
    Phases: preparation | loading | contact | follow_through

    Heuristic: uses wrist velocity to segment phases.
      - preparation: wrist velocity < low_thresh
      - loading: wrist velocity rising (unit turn / backswing)
      - contact: wrist velocity at peak
      - follow_through: wrist velocity declining after peak
    """
    import numpy as np

    if len(frames_xyz) < 4:
        return {i: "preparation" for i in range(len(frames_xyz))}

    # Extract right wrist (x,y) across frames
    wrist_pos = np.array([[f[WRIST_R*3], f[WRIST_R*3+1]] for f in frames_xyz])
    velocity = np.linalg.norm(np.diff(wrist_pos, axis=0), axis=1) * fps
    velocity = np.concatenate([[0], velocity])  # pad to match frame count

    # Smooth velocity
    kernel_size = max(3, int(fps * 0.1))
    kernel = np.ones(kernel_size) / kernel_size
    smoothed = np.convolve(velocity, kernel, mode="same")

    peak_idx = int(np.argmax(smoothed))
    low_thresh = float(np.percentile(smoothed, 25))
    high_thresh = float(np.percentile(smoothed, 75))

    phases = {}
    for i, v in enumerate(smoothed):
        if i < peak_idx * 0.3:
            phases[i] = "preparation"
        elif i < peak_idx * 0.7:
            phases[i] = "loading"
        elif i <= peak_idx + int(fps * 0.1):
            phases[i] = "contact"
        else:
            phases[i] = "follow_through"

    return phases


# ---------------------------------------------------------------------------
# Step 5: Keypoint normalization
# ---------------------------------------------------------------------------

def normalize_frames(frames_xyz: list[list[float]]) -> list[list[float]]:
    """
    Calls the C++ tennis_core module if available, otherwise falls back to
    a pure-Python implementation for development/testing.
    """
    try:
        import tennis_core  # compiled C++ pybind11 module
        return tennis_core.normalize_keypoints(frames_xyz)
    except ImportError:
        return _normalize_python_fallback(frames_xyz)


def _normalize_python_fallback(frames_xyz: list[list[float]]) -> list[list[float]]:
    import math
    LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP = 11, 12, 23, 24
    COORDS = 3
    result = []
    for frame in frames_xyz:
        def kp(idx, c): return frame[idx * COORDS + c]
        ox = (kp(LEFT_HIP, 0) + kp(RIGHT_HIP, 0)) * 0.5
        oy = (kp(LEFT_HIP, 1) + kp(RIGHT_HIP, 1)) * 0.5
        oz = (kp(LEFT_HIP, 2) + kp(RIGHT_HIP, 2)) * 0.5
        dx = kp(LEFT_SHOULDER, 0) - kp(LEFT_HIP, 0)
        dy = kp(LEFT_SHOULDER, 1) - kp(LEFT_HIP, 1)
        dz = kp(LEFT_SHOULDER, 2) - kp(LEFT_HIP, 2)
        scale = math.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
        normalized = [
            (frame[i*COORDS+c] - [ox,oy,oz][c]) / scale
            for i in range(33) for c in range(3)
        ]
        result.append(normalized)
    return result


# ---------------------------------------------------------------------------
# Step 6: Persist to PostgreSQL
# ---------------------------------------------------------------------------

def persist_results(
    sb,
    job_id: str,
    normalized_frames: list[list[float]],
    phase_map: dict[int, str],
) -> None:
    rows = []
    for i, frame in enumerate(normalized_frames):
        kps = [
            {"x": frame[j*3], "y": frame[j*3+1], "z": frame[j*3+2]}
            for j in range(33)
        ]
        rows.append({
            "job_id": job_id,
            "frame_index": i,
            "keypoints": kps,
            "phase": phase_map.get(i, "preparation"),
        })
        # Batch insert every 100 rows to stay within Supabase payload limits
        if len(rows) == 100:
            sb.table("analysis_keypoints").insert(rows).execute()
            rows = []
    if rows:
        sb.table("analysis_keypoints").insert(rows).execute()


# ---------------------------------------------------------------------------
# Main Modal function — polls for queued jobs
# ---------------------------------------------------------------------------

@app.function(
    secrets=[
        modal.Secret.from_name("tennis-coach-secrets"),
    ],
    timeout=180,
    retries=1,
)
def process_job(job_id: str) -> None:
    import tempfile
    from supabase import create_client

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    try:
        # Fetch job
        result = sb.table("analysis_jobs").select("*").eq("id", job_id).single().execute()
        job = result.data
        if not job:
            return

        _set_stage(sb, job_id, "pose_extraction", 10)

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Steps 1–2: Download + transcode
            video_path = download_and_transcode(job["video_s3_key"], tmp_dir)

            # Step 3: Pose extraction
            frames_xyz, frames_vis, fps = extract_keypoints(video_path)

            if not frames_xyz or all(sum(f) == 0 for f in frames_xyz):
                _update_job(sb, job_id, status="failed", error_code="NO_PLAYER_DETECTED", stage="pose_extraction", progress_pct=0)
                return

        # Check poor angle
        warning_code = None
        if check_poor_angle(frames_xyz, frames_vis):
            warning_code = "WARNING_POOR_ANGLE"

        _set_stage(sb, job_id, "phase_detection", 50)

        # Step 4: Phase detection
        phase_map = detect_stroke_phases(frames_xyz, fps, job["shot_type"])

        _set_stage(sb, job_id, "normalization", 70)

        # Step 5: Normalize
        normalized = normalize_frames(frames_xyz)

        # Step 6: Persist
        persist_results(sb, job_id, normalized, phase_map)

        # Mark complete
        update_kwargs = {
            "status": "complete",
            "stage": "complete",
            "progress_pct": 100,
        }
        if warning_code:
            update_kwargs["warning_code"] = warning_code

        import datetime
        update_kwargs["completed_at"] = datetime.datetime.utcnow().isoformat()

        _update_job(sb, job_id, **update_kwargs)

    except Exception as exc:
        _update_job(sb, job_id,
            status="failed",
            error_code="WORKER_ERROR",
            stage="failed",
            progress_pct=0,
        )
        raise


@app.function(
    secrets=[modal.Secret.from_name("tennis-coach-secrets")],
    schedule=modal.Period(seconds=10),
)
def poll_queued_jobs() -> None:
    """Polls Supabase every 10s for queued jobs and dispatches them."""
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    result = sb.table("analysis_jobs").select("id").eq("status", "queued").limit(10).execute()
    for row in result.data:
        process_job.spawn(row["id"])
