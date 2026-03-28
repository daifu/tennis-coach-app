from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.core.supabase import get_supabase
from app.config import settings


def check_and_increment_upload_quota(user_id: str) -> None:
    """
    For free-tier users: verify monthly upload limit has not been reached,
    then increment the counter. Raises 402 if limit exceeded.
    """
    sb = get_supabase()
    result = sb.table("user_profiles").select("tier, free_uploads_this_month, free_uploads_reset_at").eq("id", user_id).single().execute()
    profile = result.data

    # Reset counter if we've passed the reset date
    reset_at = datetime.fromisoformat(profile["free_uploads_reset_at"])
    now = datetime.now(timezone.utc)
    if now >= reset_at:
        next_reset = (now.replace(day=1) + __import__("dateutil.relativedelta", fromlist=["relativedelta"]).relativedelta(months=1))
        sb.table("user_profiles").update({
            "free_uploads_this_month": 0,
            "free_uploads_reset_at": next_reset.isoformat(),
        }).eq("id", user_id).execute()
        profile["free_uploads_this_month"] = 0

    if profile["tier"] == "pro":
        return  # No limit for pro users

    if profile["free_uploads_this_month"] >= settings.free_tier_monthly_upload_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "UPLOAD_LIMIT_REACHED", "message": "Free tier limit of 3 uploads/month reached. Upgrade to Pro for unlimited uploads."},
        )

    sb.table("user_profiles").update({
        "free_uploads_this_month": profile["free_uploads_this_month"] + 1,
    }).eq("id", user_id).execute()


def get_estimated_wait_seconds(user_id: str) -> int:
    sb = get_supabase()
    result = sb.table("user_profiles").select("tier").eq("id", user_id).single().execute()
    return 30 if result.data["tier"] == "pro" else 90
