import uuid
from app.core.supabase import get_supabase


def create_job(user_id: str, shot_type: str, pro_player_id: str, s3_key: str) -> str:
    """Insert a new analysis_jobs row with status=queued and return the job_id."""
    sb = get_supabase()
    result = sb.table("analysis_jobs").insert({
        "user_id": user_id,
        "shot_type": shot_type,
        "pro_player_id": str(pro_player_id),
        "video_s3_key": s3_key,
        "status": "queued",
        "stage": "queued",
        "progress_pct": 0,
    }).execute()
    return result.data[0]["id"]


def enqueue_job(job_id: str) -> None:
    """
    Trigger the Modal worker for this job.
    The worker polls for 'queued' jobs — marking status='queued' (already set on creation)
    is sufficient for Modal's polling approach.
    In production, this could also push a message to a queue (SQS / Redis).
    """
    # Modal worker polls Supabase for queued jobs; no explicit push needed for MVP.
    # If switching to push-based queue, add the message dispatch here.
    pass


def validate_player_shot_type(pro_player_id: str, shot_type: str) -> None:
    from fastapi import HTTPException, status
    sb = get_supabase()
    result = sb.table("pro_players").select("shot_types, is_active").eq("id", pro_player_id).single().execute()
    player = result.data
    if not player or not player["is_active"]:
        raise HTTPException(status_code=400, detail={"code": "INVALID_PRO_PLAYER"})
    if shot_type not in player["shot_types"]:
        raise HTTPException(status_code=400, detail={"code": "PLAYER_SHOT_TYPE_UNAVAILABLE",
            "message": f"This pro does not have reference data for shot type '{shot_type}'"})
