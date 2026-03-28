from fastapi import APIRouter, Depends, Query
from app.core.auth import get_current_user_id
from app.core.supabase import get_supabase
from app.schemas.pro_players import ProPlayersResponse, ProPlayer

router = APIRouter(prefix="/pro-players", tags=["pro-players"])


@router.get("", response_model=ProPlayersResponse)
def list_pro_players(
    shot_type: str | None = Query(default=None, description="Filter by available shot type"),
    _user_id: str = Depends(get_current_user_id),
):
    sb = get_supabase()
    query = sb.table("pro_players").select("id, name, gender, thumbnail_url, shot_types").eq("is_active", True)

    result = query.execute()
    players = result.data

    if shot_type:
        players = [p for p in players if shot_type in p["shot_types"]]

    return ProPlayersResponse(players=[ProPlayer(**p) for p in players])
