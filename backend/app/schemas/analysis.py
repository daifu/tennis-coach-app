from pydantic import BaseModel
from typing import Literal
from uuid import UUID


ShotType = Literal["serve", "forehand"]

JobStatus = Literal["queued", "processing", "complete", "failed"]

JobStage = Literal[
    "queued", "pose_extraction", "phase_detection", "normalization", "complete"
]


class UploadResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    estimated_wait_seconds: int


class PresignRequest(BaseModel):
    shot_type: ShotType
    pro_player_id: UUID
    filename: str
    content_type: Literal["video/mp4", "video/quicktime"]


class PresignResponse(BaseModel):
    job_id: UUID
    upload_url: str
    s3_key: str


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    progress_pct: int
    stage: JobStage
    warning_code: str | None = None
    report_id: UUID | None = None
