"""Tests for app/services/quota.py — upload quota enforcement."""
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

from tests.conftest import USER_ID


def _future_reset():
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


def _past_reset():
    return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()


def _make_profile(tier="free", uploads=0, reset_at=None):
    return {
        "tier": tier,
        "free_uploads_this_month": uploads,
        "free_uploads_reset_at": reset_at or _future_reset(),
    }


@pytest.fixture
def mock_sb():
    sb = MagicMock()
    sb.table.return_value = sb
    sb.select.return_value = sb
    sb.eq.return_value = sb
    sb.single.return_value = sb
    sb.update.return_value = sb
    return sb


class TestCheckAndIncrementUploadQuota:
    def test_free_user_under_limit_increments_counter(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(data=_make_profile(uploads=1))
        with patch("app.services.quota.get_supabase", return_value=mock_sb):
            from app.services.quota import check_and_increment_upload_quota
            check_and_increment_upload_quota(USER_ID)

        # Verify an update was called with incremented count
        mock_sb.update.assert_called_once_with({"free_uploads_this_month": 2})

    def test_free_user_at_limit_raises_402(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(data=_make_profile(uploads=3))
        with patch("app.services.quota.get_supabase", return_value=mock_sb):
            from app.services.quota import check_and_increment_upload_quota
            with pytest.raises(HTTPException) as exc_info:
                check_and_increment_upload_quota(USER_ID)
        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["code"] == "UPLOAD_LIMIT_REACHED"

    def test_free_user_zero_uploads_allowed(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(data=_make_profile(uploads=0))
        with patch("app.services.quota.get_supabase", return_value=mock_sb):
            from app.services.quota import check_and_increment_upload_quota
            check_and_increment_upload_quota(USER_ID)  # Should not raise
        mock_sb.update.assert_called_once_with({"free_uploads_this_month": 1})

    def test_pro_user_bypasses_limit_check(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(data=_make_profile(tier="pro", uploads=100))
        with patch("app.services.quota.get_supabase", return_value=mock_sb):
            from app.services.quota import check_and_increment_upload_quota
            check_and_increment_upload_quota(USER_ID)  # Should not raise
        # Pro users should not trigger an update to the counter
        mock_sb.update.assert_not_called()

    def test_expired_reset_date_resets_counter(self, mock_sb):
        profile = _make_profile(uploads=3, reset_at=_past_reset())
        mock_sb.execute.return_value = MagicMock(data=profile)
        with patch("app.services.quota.get_supabase", return_value=mock_sb):
            from app.services.quota import check_and_increment_upload_quota
            check_and_increment_upload_quota(USER_ID)  # Should not raise after reset
        # First update resets counter; second increments it
        assert mock_sb.update.call_count == 2

    def test_free_user_at_exactly_limit_boundary(self, mock_sb):
        """Exactly at limit (=3) should raise, not allow."""
        mock_sb.execute.return_value = MagicMock(data=_make_profile(uploads=3))
        with patch("app.services.quota.get_supabase", return_value=mock_sb):
            from app.services.quota import check_and_increment_upload_quota
            with pytest.raises(HTTPException) as exc_info:
                check_and_increment_upload_quota(USER_ID)
        assert exc_info.value.status_code == 402

    def test_free_user_one_below_limit_allowed(self, mock_sb):
        """2 uploads used out of 3 limit — should succeed."""
        mock_sb.execute.return_value = MagicMock(data=_make_profile(uploads=2))
        with patch("app.services.quota.get_supabase", return_value=mock_sb):
            from app.services.quota import check_and_increment_upload_quota
            check_and_increment_upload_quota(USER_ID)  # Should not raise


class TestGetEstimatedWaitSeconds:
    def test_pro_user_returns_30(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(data={"tier": "pro"})
        with patch("app.services.quota.get_supabase", return_value=mock_sb):
            from app.services.quota import get_estimated_wait_seconds
            assert get_estimated_wait_seconds(USER_ID) == 30

    def test_free_user_returns_90(self, mock_sb):
        mock_sb.execute.return_value = MagicMock(data={"tier": "free"})
        with patch("app.services.quota.get_supabase", return_value=mock_sb):
            from app.services.quota import get_estimated_wait_seconds
            assert get_estimated_wait_seconds(USER_ID) == 90
