"""Tests for GET /api/v1/pro-players endpoint."""
import pytest
from unittest.mock import MagicMock, patch

from tests.conftest import USER_ID, make_token

PLAYERS = [
    {"id": "a0000000-0000-0000-0000-000000000001", "name": "Carlos Alcaraz", "gender": "atp", "thumbnail_url": "https://s3.example.com/alcaraz.jpg", "shot_types": ["serve", "forehand"]},
    {"id": "a0000000-0000-0000-0000-000000000002", "name": "Iga Swiatek",    "gender": "wta", "thumbnail_url": "https://s3.example.com/swiatek.jpg",  "shot_types": ["serve", "forehand"]},
    {"id": "a0000000-0000-0000-0000-000000000003", "name": "Jannik Sinner",  "gender": "atp", "thumbnail_url": "https://s3.example.com/sinner.jpg",   "shot_types": ["serve"]},
]


@pytest.fixture
def mock_sb_players():
    sb = MagicMock()
    sb.table.return_value = sb
    sb.select.return_value = sb
    sb.eq.return_value = sb
    sb.execute.return_value = MagicMock(data=PLAYERS)
    return sb


class TestListProPlayers:
    def test_returns_all_active_players(self, client, mock_sb_players):
        with patch("app.api.v1.pro_players.get_supabase", return_value=mock_sb_players):
            resp = client.get("/api/v1/pro-players", headers={"Authorization": f"Bearer {make_token()}"})
        assert resp.status_code == 200
        assert len(resp.json()["players"]) == 3

    def test_filters_by_shot_type_serve(self, client, mock_sb_players):
        with patch("app.api.v1.pro_players.get_supabase", return_value=mock_sb_players):
            resp = client.get("/api/v1/pro-players?shot_type=serve", headers={"Authorization": f"Bearer {make_token()}"})
        # All 3 players have "serve"
        assert resp.status_code == 200
        assert len(resp.json()["players"]) == 3

    def test_filters_by_shot_type_forehand(self, client, mock_sb_players):
        with patch("app.api.v1.pro_players.get_supabase", return_value=mock_sb_players):
            resp = client.get("/api/v1/pro-players?shot_type=forehand", headers={"Authorization": f"Bearer {make_token()}"})
        # Only p1 and p2 have "forehand"
        data = resp.json()["players"]
        assert resp.status_code == 200
        assert len(data) == 2
        assert all("forehand" in p["shot_types"] for p in data)

    def test_shot_type_with_no_matches_returns_empty(self, client, mock_sb_players):
        with patch("app.api.v1.pro_players.get_supabase", return_value=mock_sb_players):
            resp = client.get("/api/v1/pro-players?shot_type=volley", headers={"Authorization": f"Bearer {make_token()}"})
        assert resp.status_code == 200
        assert resp.json()["players"] == []

    def test_requires_auth(self, client):
        resp = client.get("/api/v1/pro-players")
        assert resp.status_code == 403

    def test_invalid_token_returns_401(self, client):
        resp = client.get("/api/v1/pro-players", headers={"Authorization": "Bearer bad-token"})
        assert resp.status_code == 401

    def test_response_shape(self, client, mock_sb_players):
        with patch("app.api.v1.pro_players.get_supabase", return_value=mock_sb_players):
            resp = client.get("/api/v1/pro-players", headers={"Authorization": f"Bearer {make_token()}"})
        player = resp.json()["players"][0]
        assert "id" in player
        assert "name" in player
        assert "gender" in player
        assert "thumbnail_url" in player
        assert "shot_types" in player

    def test_empty_player_list_returns_empty_array(self, client):
        sb = MagicMock()
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.execute.return_value = MagicMock(data=[])
        with patch("app.api.v1.pro_players.get_supabase", return_value=sb):
            resp = client.get("/api/v1/pro-players", headers={"Authorization": f"Bearer {make_token()}"})
        assert resp.status_code == 200
        assert resp.json()["players"] == []
