import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from app.core.auth import get_current_user_id
from app.core.s3 import upload_fileobj, generate_presigned_put, object_exists
from app.core.supabase import get_supabase
from app.schemas.analysis import (
    JobStatusResponse, PresignRequest, PresignResponse, ShotType, UploadResponse,
)
from app.services.job_queue import create_job, enqueue_job, validate_player_shot_type
from app.services.quota import check_and_increment_upload_quota, get_estimated_wait_seconds
from app.config import settings

router = APIRouter(prefix="/analysis", tags=["analysis"])

ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime"}


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_video(
    shot_type: ShotType = Form(...),
    pro_player_id: str = Form(...),
    video: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    # Validate file type
    if video.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, detail={"code": "INVALID_FORMAT", "message": "Only MP4 and MOV files are supported"})

    # Validate file size
    video_bytes = await video.read()
    if len(video_bytes) > settings.max_video_size_bytes:
        raise HTTPException(413, detail={"code": "FILE_TOO_LARGE"})

    # Validate shot type availability for chosen pro
    validate_player_shot_type(pro_player_id, shot_type)

    # Check + increment upload quota
    check_and_increment_upload_quota(user_id)

    # Upload to S3
    s3_key = f"uploads/{user_id}/{uuid.uuid4()}/{video.filename}"
    import io
    upload_fileobj(io.BytesIO(video_bytes), s3_key, video.content_type)

    # Create job and enqueue
    job_id = create_job(user_id, shot_type, pro_player_id, s3_key)
    enqueue_job(job_id)

    return UploadResponse(
        job_id=job_id,
        status="queued",
        estimated_wait_seconds=get_estimated_wait_seconds(user_id),
    )


@router.post("/presign", response_model=PresignResponse, status_code=201)
def presign_upload(
    body: PresignRequest,
    user_id: str = Depends(get_current_user_id),
):
    # Validate shot type availability
    validate_player_shot_type(str(body.pro_player_id), body.shot_type)

    # Check quota (reserve the slot now; if user never confirms, a cleanup job reclaims it)
    check_and_increment_upload_quota(user_id)

    s3_key = f"uploads/{user_id}/{uuid.uuid4()}/{body.filename}"
    upload_url = generate_presigned_put(s3_key, body.content_type)

    # Create a pending job row
    job_id = create_job(user_id, body.shot_type, str(body.pro_player_id), s3_key)

    return PresignResponse(job_id=job_id, upload_url=upload_url, s3_key=s3_key)


@router.post("/{job_id}/confirm", status_code=202)
def confirm_upload(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    sb = get_supabase()
    result = sb.table("analysis_jobs").select("video_s3_key, user_id, status").eq("id", job_id).single().execute()
    job = result.data

    if not job or job["user_id"] != user_id:
        raise HTTPException(404, detail="Job not found")
    if job["status"] != "queued":
        raise HTTPException(409, detail="Job already confirmed or processing")
    if not object_exists(job["video_s3_key"]):
        raise HTTPException(400, detail={"code": "S3_OBJECT_NOT_FOUND", "message": "Upload the video to S3 before confirming"})

    enqueue_job(job_id)
    return {"job_id": job_id, "status": "queued"}


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    sb = get_supabase()
    result = sb.table("analysis_jobs").select(
        "id, user_id, status, stage, progress_pct, warning_code, report_id"
    ).eq("id", job_id).single().execute()
    job = result.data

    if not job or job["user_id"] != user_id:
        raise HTTPException(404, detail="Job not found")

    return JobStatusResponse(
        job_id=job["id"],
        status=job["status"],
        progress_pct=job["progress_pct"],
        stage=job["stage"],
        warning_code=job.get("warning_code"),
        report_id=job.get("report_id"),
    )
