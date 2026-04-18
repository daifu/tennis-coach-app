"""
TennisCoach AI — Modal.com Serverless Worker

Pipeline:
  1.  Download video from S3
  2.  FFmpeg transcode → H.264 MP4
  3.  MediaPipe BlazePose — extract 33 keypoints/frame
  4.  Stroke phase detection (velocity-based heuristic)
  5.  Keypoint normalization (C++ module via pybind11)
  6.  Persist keypoints + phases to PostgreSQL
  7.  Load pro reference keypoints from DB
  8.  DTW alignment + similarity score (C++ via pybind11)
  9.  Joint angle calculation + per-phase deltas (C++ via pybind11)
  10. Gemini 2.5 Flash coaching feedback generation
  11. Persist analysis_report + coaching_feedback rows
  12. Update job with report_id
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
    .pip_install("google-generativeai==0.8.5")
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
# Step 7: Load pro reference keypoints from DB
# ---------------------------------------------------------------------------

def load_pro_reference_frames(
    sb,
    pro_player_id: str,
    shot_type: str,
) -> tuple[list[list[float]], dict[int, str]]:
    """
    Returns normalized pro frames and a phase_map matching frame_index -> phase.
    Fetches from pro_player_references table ordered by frame_index.
    """
    result = (
        sb.table("pro_player_references")
        .select("frame_index, keypoints, phase")
        .eq("pro_player_id", pro_player_id)
        .eq("shot_type", shot_type)
        .order("frame_index")
        .execute()
    )
    rows = result.data or []

    frames: list[list[float]] = []
    phase_map: dict[int, str] = {}
    for row in rows:
        kps = row["keypoints"]
        flat = []
        for pt in kps:
            flat.extend([pt["x"], pt["y"], pt["z"]])
        frames.append(flat)
        phase_map[row["frame_index"]] = row["phase"]

    return frames, phase_map


# ---------------------------------------------------------------------------
# Step 8+9: DTW alignment, similarity score, and joint angle deltas
# ---------------------------------------------------------------------------

def _calculate_joint_angles_python(frames: list[list[float]]) -> dict[str, list[float]]:
    """Pure-Python fallback for joint angle calculation (mirrors C++ logic)."""
    import math

    def kp(frame: list[float], idx: int) -> tuple[float, float, float]:
        return frame[idx * 3], frame[idx * 3 + 1], frame[idx * 3 + 2]

    def angle(a: tuple, vertex: tuple, b: tuple) -> float:
        v1 = (a[0] - vertex[0], a[1] - vertex[1], a[2] - vertex[2])
        v2 = (b[0] - vertex[0], b[1] - vertex[1], b[2] - vertex[2])
        dot = sum(v1[i] * v2[i] for i in range(3))
        m1 = math.sqrt(sum(x * x for x in v1))
        m2 = math.sqrt(sum(x * x for x in v2))
        if m1 < 1e-6 or m2 < 1e-6:
            return 0.0
        cos_a = max(-1.0, min(1.0, dot / (m1 * m2)))
        return math.acos(cos_a) * 180.0 / math.pi

    R_SHOULDER, R_ELBOW, R_WRIST = 12, 14, 16
    L_SHOULDER, L_ELBOW, L_WRIST = 11, 13, 15
    R_HIP, R_KNEE, R_ANKLE = 24, 26, 28

    result: dict[str, list[float]] = {
        "right_elbow": [],
        "left_elbow": [],
        "right_knee": [],
        "left_knee": [],
        "right_shoulder_abduction": [],
    }

    for frame in frames:
        result["right_elbow"].append(angle(kp(frame, R_SHOULDER), kp(frame, R_ELBOW), kp(frame, R_WRIST)))
        result["left_elbow"].append(angle(kp(frame, L_SHOULDER), kp(frame, L_ELBOW), kp(frame, L_WRIST)))
        result["right_knee"].append(angle(kp(frame, R_HIP), kp(frame, R_KNEE), kp(frame, R_ANKLE)))
        result["left_knee"].append(angle(kp(frame, R_HIP), kp(frame, R_KNEE), kp(frame, R_ANKLE)))
        result["right_shoulder_abduction"].append(angle(kp(frame, R_ELBOW), kp(frame, R_SHOULDER), kp(frame, R_HIP)))

    return result


def calculate_joint_angles(frames: list[list[float]]) -> dict[str, list[float]]:
    try:
        import tennis_core
        return tennis_core.calculate_joint_angles(frames)
    except ImportError:
        return _calculate_joint_angles_python(frames)


def _dtw_distance_python(user_frames: list[list[float]], pro_frames: list[list[float]]) -> float:
    import math
    n, m = len(user_frames), len(pro_frames)
    INF = float("inf")
    dp = [[INF] * m for _ in range(n)]

    def dist(a: list[float], b: list[float]) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    dp[0][0] = dist(user_frames[0], pro_frames[0])
    for i in range(1, n):
        dp[i][0] = dp[i - 1][0] + dist(user_frames[i], pro_frames[0])
    for j in range(1, m):
        dp[0][j] = dp[0][j - 1] + dist(user_frames[0], pro_frames[j])
    for i in range(1, n):
        for j in range(1, m):
            dp[i][j] = dist(user_frames[i], pro_frames[j]) + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
    return dp[n - 1][m - 1] / (n + m)


def compare_with_pro(
    user_frames: list[list[float]],
    user_phase_map: dict[int, str],
    pro_frames: list[list[float]],
    pro_phase_map: dict[int, str],
) -> tuple[float, dict, dict]:
    """
    Returns:
        similarity_score: 0–100 float
        joint_angles: {joint: {user_mean, pro_mean, delta_mean}} per phase
        phase_metrics: {phase: {similarity, joints}}
    """
    import math

    # Similarity score
    try:
        import tennis_core
        score = tennis_core.similarity_score(user_frames, pro_frames)
    except ImportError:
        dtw_dist = _dtw_distance_python(user_frames, pro_frames)
        score = max(0.0, min(100.0, 100.0 * math.exp(-1.0 * dtw_dist)))

    # Joint angles for both sequences
    user_angles = calculate_joint_angles(user_frames)
    pro_angles = calculate_joint_angles(pro_frames) if pro_frames else {}

    phases = ["preparation", "loading", "contact", "follow_through"]

    def frames_for_phase(phase_map: dict[int, str], angles: dict[str, list[float]], phase: str):
        indices = [i for i, p in phase_map.items() if p == phase and i < len(next(iter(angles.values()), []))]
        return indices

    joint_angles_out: dict = {}
    for joint, user_vals in user_angles.items():
        pro_vals = pro_angles.get(joint, [])
        user_mean = sum(user_vals) / len(user_vals) if user_vals else 0.0
        pro_mean = sum(pro_vals) / len(pro_vals) if pro_vals else 0.0
        joint_angles_out[joint] = {
            "user_mean": round(user_mean, 1),
            "pro_mean": round(pro_mean, 1),
            "delta_mean": round(user_mean - pro_mean, 1),
        }

    phase_metrics_out: dict = {}
    for phase in phases:
        user_indices = frames_for_phase(user_phase_map, user_angles, phase)
        pro_indices = frames_for_phase(pro_phase_map, pro_angles, phase)

        phase_user_frames = [user_frames[i] for i in user_indices if i < len(user_frames)]
        phase_pro_frames = [pro_frames[i] for i in pro_indices if i < len(pro_frames)]

        if phase_user_frames and phase_pro_frames:
            try:
                import tennis_core
                phase_sim = tennis_core.similarity_score(phase_user_frames, phase_pro_frames)
            except ImportError:
                d = _dtw_distance_python(phase_user_frames, phase_pro_frames)
                phase_sim = max(0.0, min(100.0, 100.0 * math.exp(-1.0 * d)))
        else:
            phase_sim = score

        phase_joints: dict = {}
        for joint in user_angles:
            u_phase = [user_angles[joint][i] for i in user_indices if i < len(user_angles[joint])]
            p_phase = [pro_angles.get(joint, [])[i] for i in pro_indices if i < len(pro_angles.get(joint, []))]
            if u_phase:
                phase_joints[joint] = {
                    "user_mean": round(sum(u_phase) / len(u_phase), 1),
                    "pro_mean": round(sum(p_phase) / len(p_phase), 1) if p_phase else None,
                }

        phase_metrics_out[phase] = {
            "similarity": round(phase_sim, 1),
            "joints": phase_joints,
        }

    return round(score, 2), joint_angles_out, phase_metrics_out


# ---------------------------------------------------------------------------
# Step 10: Gemini 2.5 Flash coaching feedback (F4)
# ---------------------------------------------------------------------------

GEMINI_PROMPT_TEMPLATE = """You are an expert tennis coach. Analyze the biomechanical comparison below and identify up to 3 flaws that most impact performance.

Shot type: {shot_type}
Pro player compared against: {pro_player_name}
Overall similarity score: {similarity_score}%

Joint angle analysis (user vs pro, mean degrees across full stroke):
{joint_angles_text}

Phase-by-phase similarity:
{phase_similarity_text}

For each flaw you identify, respond in EXACTLY this JSON format (an array of up to 3 objects):
[
  {{
    "flaw_index": 1,
    "what": "One sentence naming the specific flaw with a concrete measurement",
    "why": "One sentence on why this hurts performance",
    "fix_drill": "One concrete drill or cue the player can practice immediately",
    "impact_order": 1
  }}
]

Rules:
- Maximum 3 flaws, ordered by impact (1 = highest impact)
- No jargon; plain language a club player would understand
- Tone: direct, confident, encouraging — no hedging or filler
- The "what" must reference specific numbers from the data above
- Return ONLY the JSON array, no other text"""


def _build_angles_text(joint_angles: dict) -> str:
    lines = []
    for joint, data in joint_angles.items():
        delta = data["delta_mean"]
        direction = "higher" if delta > 0 else "lower"
        lines.append(
            f"  {joint.replace('_', ' ')}: user={data['user_mean']}°, "
            f"pro={data['pro_mean']}°, delta={abs(delta):.1f}° {direction}"
        )
    return "\n".join(lines) if lines else "  No angle data available"


def _build_phase_text(phase_metrics: dict) -> str:
    lines = []
    for phase, data in phase_metrics.items():
        lines.append(f"  {phase}: {data['similarity']:.1f}% similar to pro")
    return "\n".join(lines) if lines else "  No phase data available"


def generate_coaching_feedback(
    shot_type: str,
    pro_player_name: str,
    similarity_score: float,
    joint_angles: dict,
    phase_metrics: dict,
) -> list[dict]:
    """Calls Gemini 2.5 Flash and returns a list of flaw dicts."""
    import json
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = GEMINI_PROMPT_TEMPLATE.format(
        shot_type=shot_type,
        pro_player_name=pro_player_name,
        similarity_score=similarity_score,
        joint_angles_text=_build_angles_text(joint_angles),
        phase_similarity_text=_build_phase_text(phase_metrics),
    )

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    flaws = json.loads(text)
    return flaws[:3]


def _fallback_feedback(joint_angles: dict, similarity_score: float) -> list[dict]:
    """Returns generic feedback when Gemini is unavailable."""
    worst_joint = max(joint_angles, key=lambda j: abs(joint_angles[j]["delta_mean"]), default=None)
    if worst_joint and abs(joint_angles[worst_joint]["delta_mean"]) > 5:
        delta = joint_angles[worst_joint]["delta_mean"]
        direction = "too high" if delta > 0 else "too low"
        return [{
            "flaw_index": 1,
            "what": f"Your {worst_joint.replace('_', ' ')} angle is {abs(delta):.0f}° {direction} compared to the pro.",
            "why": "Deviations in this joint reduce stroke efficiency and consistency.",
            "fix_drill": "Focus on matching the pro's position in slow-motion shadow swings.",
            "impact_order": 1,
        }]
    return [{
        "flaw_index": 1,
        "what": f"Overall stroke similarity is {similarity_score:.0f}% — there is room to improve timing.",
        "why": "Timing mismatches reduce power transfer at contact.",
        "fix_drill": "Film yourself at 240fps and compare frame-by-frame with the pro reference.",
        "impact_order": 1,
    }]


# ---------------------------------------------------------------------------
# Step 11: Persist report + feedback
# ---------------------------------------------------------------------------

def create_report(
    sb,
    job_id: str,
    user_id: str,
    shot_type: str,
    pro_player_id: str,
    similarity_score: float,
    joint_angles: dict,
    phase_metrics: dict,
    warning_code: str | None,
) -> str:
    result = sb.table("analysis_reports").insert({
        "job_id": job_id,
        "user_id": user_id,
        "shot_type": shot_type,
        "pro_player_id": pro_player_id,
        "similarity_score": similarity_score,
        "joint_angles": joint_angles,
        "phase_metrics": phase_metrics,
        "warning_code": warning_code,
    }).execute()
    return result.data[0]["id"]


def store_feedback(sb, report_id: str, flaws: list[dict]) -> None:
    rows = [
        {
            "report_id": report_id,
            "flaw_index": f["flaw_index"],
            "what": f["what"],
            "why": f["why"],
            "fix_drill": f["fix_drill"],
            "impact_order": f["impact_order"],
        }
        for f in flaws
    ]
    if rows:
        sb.table("coaching_feedback").insert(rows).execute()


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
    import datetime
    import tempfile
    from supabase import create_client

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    try:
        # Fetch job + pro player name
        result = sb.table("analysis_jobs").select(
            "*, pro_players(name)"
        ).eq("id", job_id).single().execute()
        job = result.data
        if not job:
            return
        pro_player_name = (job.get("pro_players") or {}).get("name", "the pro")

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

        # Step 6: Persist keypoints
        persist_results(sb, job_id, normalized, phase_map)

        _set_stage(sb, job_id, "comparison", 80)

        # Step 7: Load pro reference
        pro_frames, pro_phase_map = load_pro_reference_frames(
            sb, job["pro_player_id"], job["shot_type"]
        )

        # Step 8+9: Compare — DTW similarity + joint angle deltas
        if pro_frames:
            similarity, joint_angles, phase_metrics = compare_with_pro(
                normalized, phase_map, pro_frames, pro_phase_map
            )
        else:
            # No reference data yet — produce a zero-delta placeholder report
            similarity = 0.0
            joint_angles = {}
            phase_metrics = {}

        _set_stage(sb, job_id, "feedback", 90)

        # Step 10: Gemini coaching feedback
        try:
            flaws = generate_coaching_feedback(
                shot_type=job["shot_type"],
                pro_player_name=pro_player_name,
                similarity_score=similarity,
                joint_angles=joint_angles,
                phase_metrics=phase_metrics,
            )
        except Exception:
            flaws = _fallback_feedback(joint_angles, similarity)

        # Step 11: Persist report + feedback
        report_id = create_report(
            sb,
            job_id=job_id,
            user_id=job["user_id"],
            shot_type=job["shot_type"],
            pro_player_id=job["pro_player_id"],
            similarity_score=similarity,
            joint_angles=joint_angles,
            phase_metrics=phase_metrics,
            warning_code=warning_code,
        )
        store_feedback(sb, report_id, flaws)

        # Step 12: Mark complete with report_id
        _update_job(sb, job_id,
            status="complete",
            stage="complete",
            progress_pct=100,
            report_id=report_id,
            warning_code=warning_code,
            completed_at=datetime.datetime.utcnow().isoformat(),
        )

    except Exception:
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
