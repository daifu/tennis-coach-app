from fastapi import APIRouter, Depends
from app.core.auth import get_current_user_id
from app.core.supabase import get_supabase
from app.schemas.analysis import JobHistoryItem, JobHistoryResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/jobs", response_model=JobHistoryResponse)
def get_job_history(user_id: str = Depends(get_current_user_id)):
    sb = get_supabase()

    result = sb.table("analysis_jobs").select(
        "id, shot_type, status, report_id, created_at, pro_players(name), "
        "analysis_reports(similarity_score)"
    ).eq("user_id", user_id).order("created_at", desc=True).limit(50).execute()

    items = []
    for row in result.data or []:
        report_data = row.get("analysis_reports") or {}
        items.append(JobHistoryItem(
            job_id=row["id"],
            shot_type=row["shot_type"],
            pro_player_name=(row.get("pro_players") or {}).get("name", ""),
            status=row["status"],
            similarity_score=float(report_data["similarity_score"]) if report_data.get("similarity_score") is not None else None,
            report_id=row.get("report_id"),
            created_at=row["created_at"],
        ))

    return JobHistoryResponse(jobs=items)
