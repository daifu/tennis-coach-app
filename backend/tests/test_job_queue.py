"""Tests for app/services/job_queue.py — job creation and player validation."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from tests.conftest import USER_ID, PRO_PLAYER_ID, JOB_ID


@pytest.fixture
def mock_sb():
    sb = MagicMock()
    sb.table.return_value = sb
    sb.select.return_value = sb
    sb.eq.return_value = sb
    sb.single.return_value = sb
    sb.insert.return_value = sb
    return sb


class TestCreateJob:
    def test_returns_job_id(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(data=[{"id": JOB_ID}])
        with patch("app.services.job_queue.get_supabase", return_value=mock_sb):
            from app.services.job_queue import create_job
            result = create_job(USER_ID, "serve", PRO_PLAYER_ID, "uploads/user/video.mp4")
        assert result == JOB_ID

    def test_inserts_correct_fields(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(data=[{"id": JOB_ID}])
        with patch("app.services.job_queue.get_supabase", return_value=mock_sb):
            from app.services.job_queue import create_job
            create_job(USER_ID, "forehand", PRO_PLAYER_ID, "uploads/user/video.mp4")

        inserted = mock_sb.insert.call_args[0][0]
        assert inserted["user_id"] == USER_ID
        assert inserted["shot_type"] == "forehand"
        assert inserted["pro_player_id"] == PRO_PLAYER_ID
        assert inserted["status"] == "queued"
        assert inserted["stage"] == "queued"
        assert inserted["progress_pct"] == 0
        assert inserted["video_s3_key"] == "uploads/user/video.mp4"

    def test_pro_player_id_converted_to_str(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(data=[{"id": JOB_ID}])
        import uuid
        uid = uuid.UUID(PRO_PLAYER_ID) if len(PRO_PLAYER_ID) == 36 else uuid.uuid4()
        with patch("app.services.job_queue.get_supabase", return_value=mock_sb):
            from app.services.job_queue import create_job
            create_job(USER_ID, "serve", str(uid), "key.mp4")
        inserted = mock_sb.insert.call_args[0][0]
        assert isinstance(inserted["pro_player_id"], str)


class TestValidatePlayerShotType:
    def test_valid_player_and_shot_type_passes(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(
            data={"shot_types": ["serve", "forehand"], "is_active": True}
        )
        with patch("app.services.job_queue.get_supabase", return_value=mock_sb):
            from app.services.job_queue import validate_player_shot_type
            validate_player_shot_type(PRO_PLAYER_ID, "serve")  # Should not raise

    def test_shot_type_not_in_player_raises_400(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(
            data={"shot_types": ["serve"], "is_active": True}
        )
        with patch("app.services.job_queue.get_supabase", return_value=mock_sb):
            from app.services.job_queue import validate_player_shot_type
            with pytest.raises(HTTPException) as exc_info:
                validate_player_shot_type(PRO_PLAYER_ID, "backhand")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "PLAYER_SHOT_TYPE_UNAVAILABLE"

    def test_inactive_player_raises_400(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(
            data={"shot_types": ["serve", "forehand"], "is_active": False}
        )
        with patch("app.services.job_queue.get_supabase", return_value=mock_sb):
            from app.services.job_queue import validate_player_shot_type
            with pytest.raises(HTTPException) as exc_info:
                validate_player_shot_type(PRO_PLAYER_ID, "serve")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "INVALID_PRO_PLAYER"

    def test_player_not_found_raises_400(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(data=None)
        with patch("app.services.job_queue.get_supabase", return_value=mock_sb):
            from app.services.job_queue import validate_player_shot_type
            with pytest.raises(HTTPException) as exc_info:
                validate_player_shot_type("nonexistent-id", "serve")
        assert exc_info.value.status_code == 400

    def test_error_message_includes_shot_type(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(
            data={"shot_types": ["serve"], "is_active": True}
        )
        with patch("app.services.job_queue.get_supabase", return_value=mock_sb):
            from app.services.job_queue import validate_player_shot_type
            with pytest.raises(HTTPException) as exc_info:
                validate_player_shot_type(PRO_PLAYER_ID, "volley")
        assert "volley" in exc_info.value.detail["message"]
