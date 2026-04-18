from pydantic import BaseModel
from typing import Any, Literal
from uuid import UUID


ShotType = Literal["serve", "forehand", "backhand", "volley"]

JobStatus = Literal["queued", "processing", "complete", "failed"]

JobStage = Literal[
    "queued", "pose_extraction", "phase_detection", "normalization",
    "comparison", "feedback", "complete", "failed",
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


class CoachingFlaw(BaseModel):
    flaw_index: int
    what: str
    why: str
    fix_drill: str
    impact_order: int


class ReportResponse(BaseModel):
    report_id: UUID
    job_id: UUID
    shot_type: str
    pro_player_id: UUID
    pro_player_name: str
    similarity_score: float
    joint_angles: dict[str, Any]
    phase_metrics: dict[str, Any]
    coaching_feedback: list[CoachingFlaw]
    warning_code: str | None = None
    created_at: str


class JobHistoryItem(BaseModel):
    job_id: UUID
    shot_type: str
    pro_player_name: str
    status: JobStatus
    similarity_score: float | None = None
    report_id: UUID | None = None
    created_at: str


class JobHistoryResponse(BaseModel):
    jobs: list[JobHistoryItem]
