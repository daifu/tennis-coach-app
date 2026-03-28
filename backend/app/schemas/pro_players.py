from pydantic import BaseModel
from typing import Literal
from uuid import UUID


class ProPlayer(BaseModel):
    id: UUID
    name: str
    gender: Literal["atp", "wta"]
    thumbnail_url: str
    shot_types: list[str]


class ProPlayersResponse(BaseModel):
    players: list[ProPlayer]
