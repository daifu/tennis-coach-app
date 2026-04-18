from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user_id
from app.core.supabase import get_supabase
from app.schemas.analysis import CoachingFlaw, ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: str, user_id: str = Depends(get_current_user_id)):
    sb = get_supabase()

    result = sb.table("analysis_reports").select(
        "*, analysis_jobs(id), pro_players(name)"
    ).eq("id", report_id).single().execute()
    report = result.data

    if not report or report["user_id"] != user_id:
        raise HTTPException(404, detail="Report not found")

    feedback_result = sb.table("coaching_feedback").select("*").eq(
        "report_id", report_id
    ).order("impact_order").execute()
    flaws = [
        CoachingFlaw(
            flaw_index=f["flaw_index"],
            what=f["what"],
            why=f["why"],
            fix_drill=f["fix_drill"],
            impact_order=f["impact_order"],
        )
        for f in (feedback_result.data or [])
    ]

    return ReportResponse(
        report_id=report["id"],
        job_id=report["job_id"],
        shot_type=report["shot_type"],
        pro_player_id=report["pro_player_id"],
        pro_player_name=(report.get("pro_players") or {}).get("name", ""),
        similarity_score=float(report["similarity_score"]),
        joint_angles=report["joint_angles"] or {},
        phase_metrics=report["phase_metrics"] or {},
        coaching_feedback=flaws,
        warning_code=report.get("warning_code"),
        created_at=report["created_at"],
    )
