"""Tests for /api/v1/analysis endpoints — upload, presign, confirm, status."""
import io
import pytest
from unittest.mock import MagicMock, patch

from tests.conftest import USER_ID, PRO_PLAYER_ID, JOB_ID, REPORT_ID, make_token

VALID_PLAYER = {"shot_types": ["serve", "forehand"], "is_active": True}
FREE_PROFILE  = {"tier": "free",  "free_uploads_this_month": 0, "free_uploads_reset_at": "2099-01-01T00:00:00+00:00"}
PRO_PROFILE   = {"tier": "pro",   "free_uploads_this_month": 0, "free_uploads_reset_at": "2099-01-01T00:00:00+00:00"}


def _headers():
    return {"Authorization": f"Bearer {make_token()}"}


def _mp4_file(size: int = 1024):
    return ("test.mp4", io.BytesIO(b"x" * size), "video/mp4")


def _supabase_for_upload(profile=None, player=None):
    """Build a mock Supabase that satisfies the upload endpoint chain.

    Call sequence:
      0 — validate_player_shot_type (read)
      1 — check_and_increment_upload_quota (read)
      2 — quota increment write (free users only) OR create_job insert (pro users)
      3 — create_job insert (free users only)
    """
    p = profile or FREE_PROFILE
    sb = MagicMock()
    sb.table.return_value = sb
    sb.select.return_value = sb
    sb.eq.return_value = sb
    sb.single.return_value = sb
    sb.insert.return_value = sb
    sb.update.return_value = sb

    call_count = {"n": 0}

    def execute_side_effect():
        n = call_count["n"]
        call_count["n"] += 1
        if n == 0:                              # validate_player_shot_type
            return MagicMock(data=player or VALID_PLAYER)
        elif n == 1:                            # quota read
            return MagicMock(data=p)
        elif n == 2 and p["tier"] == "free":    # quota write (free only)
            return MagicMock(data=None)
        else:                                   # create_job insert
            return MagicMock(data=[{"id": JOB_ID}])

    sb.execute.side_effect = lambda: execute_side_effect()
    return sb


class TestUploadVideo:
    def test_valid_mp4_returns_202(self, client):
        sb = _supabase_for_upload()
        with patch("app.api.v1.analysis.get_supabase", return_value=sb), \
             patch("app.services.job_queue.get_supabase", return_value=sb), \
             patch("app.services.quota.get_supabase", return_value=sb), \
             patch("app.api.v1.analysis.upload_fileobj"), \
             patch("app.api.v1.analysis.get_estimated_wait_seconds", return_value=90):
            resp = client.post(
                "/api/v1/analysis/upload",
                headers=_headers(),
                files={"video": _mp4_file()},
                data={"shot_type": "serve", "pro_player_id": PRO_PLAYER_ID},
            )
        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "queued"
        assert body["estimated_wait_seconds"] == 90

    def test_mov_file_accepted(self, client):
        sb = _supabase_for_upload()
        with patch("app.api.v1.analysis.get_supabase", return_value=sb), \
             patch("app.services.job_queue.get_supabase", return_value=sb), \
             patch("app.services.quota.get_supabase", return_value=sb), \
             patch("app.api.v1.analysis.upload_fileobj"), \
             patch("app.api.v1.analysis.get_estimated_wait_seconds", return_value=90):
            resp = client.post(
                "/api/v1/analysis/upload",
                headers=_headers(),
                files={"video": ("clip.mov", io.BytesIO(b"data"), "video/quicktime")},
                data={"shot_type": "serve", "pro_player_id": PRO_PLAYER_ID},
            )
        assert resp.status_code == 202

    def test_invalid_format_returns_400(self, client):
        resp = client.post(
            "/api/v1/analysis/upload",
            headers=_headers(),
            files={"video": ("clip.avi", io.BytesIO(b"data"), "video/avi")},
            data={"shot_type": "serve", "pro_player_id": PRO_PLAYER_ID},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_FORMAT"

    def test_file_too_large_returns_413(self, client):
        oversized = b"x" * (160 * 1024 * 1024)  # 160 MB > 150 MB limit
        resp = client.post(
            "/api/v1/analysis/upload",
            headers=_headers(),
            files={"video": ("big.mp4", io.BytesIO(oversized), "video/mp4")},
            data={"shot_type": "serve", "pro_player_id": PRO_PLAYER_ID},
        )
        assert resp.status_code == 413
        assert resp.json()["detail"]["code"] == "FILE_TOO_LARGE"

    def test_missing_auth_returns_403(self, client):
        resp = client.post(
            "/api/v1/analysis/upload",
            files={"video": _mp4_file()},
            data={"shot_type": "serve", "pro_player_id": PRO_PLAYER_ID},
        )
        assert resp.status_code == 403

    def test_missing_shot_type_returns_422(self, client):
        resp = client.post(
            "/api/v1/analysis/upload",
            headers=_headers(),
            files={"video": _mp4_file()},
            data={"pro_player_id": PRO_PLAYER_ID},
        )
        assert resp.status_code == 422

    def test_missing_pro_player_returns_422(self, client):
        resp = client.post(
            "/api/v1/analysis/upload",
            headers=_headers(),
            files={"video": _mp4_file()},
            data={"shot_type": "serve"},
        )
        assert resp.status_code == 422

    def test_upload_limit_reached_returns_402(self, client):
        sb = MagicMock()
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.single.return_value = sb

        call_count = {"n": 0}
        def _execute():
            n = call_count["n"]; call_count["n"] += 1
            if n == 0: return MagicMock(data=VALID_PLAYER)
            return MagicMock(data={"tier": "free", "free_uploads_this_month": 3,
                                   "free_uploads_reset_at": "2099-01-01T00:00:00+00:00"})
        sb.execute.side_effect = lambda: _execute()

        with patch("app.api.v1.analysis.get_supabase", return_value=sb), \
             patch("app.services.job_queue.get_supabase", return_value=sb), \
             patch("app.services.quota.get_supabase", return_value=sb):
            resp = client.post(
                "/api/v1/analysis/upload",
                headers=_headers(),
                files={"video": _mp4_file()},
                data={"shot_type": "serve", "pro_player_id": PRO_PLAYER_ID},
            )
        assert resp.status_code == 402
        assert resp.json()["detail"]["code"] == "UPLOAD_LIMIT_REACHED"

    def test_pro_user_gets_30s_estimate(self, client):
        sb = _supabase_for_upload(profile=PRO_PROFILE)
        with patch("app.api.v1.analysis.get_supabase", return_value=sb), \
             patch("app.services.job_queue.get_supabase", return_value=sb), \
             patch("app.services.quota.get_supabase", return_value=sb), \
             patch("app.api.v1.analysis.upload_fileobj"), \
             patch("app.api.v1.analysis.get_estimated_wait_seconds", return_value=30):
            resp = client.post(
                "/api/v1/analysis/upload",
                headers=_headers(),
                files={"video": _mp4_file()},
                data={"shot_type": "serve", "pro_player_id": PRO_PLAYER_ID},
            )
        assert resp.json()["estimated_wait_seconds"] == 30


class TestGetJobStatus:
    def _job_row(self, user_id=USER_ID, status="processing", stage="pose_extraction",
                 progress=45, warning=None, report_id=None):
        return {
            "id": JOB_ID, "user_id": user_id, "status": status,
            "stage": stage, "progress_pct": progress,
            "warning_code": warning, "report_id": report_id,
        }

    def test_returns_job_status(self, client):
        sb = MagicMock()
        sb.table.return_value = sb; sb.select.return_value = sb
        sb.eq.return_value = sb; sb.single.return_value = sb
        sb.execute.return_value = MagicMock(data=self._job_row())
        with patch("app.api.v1.analysis.get_supabase", return_value=sb):
            resp = client.get(f"/api/v1/analysis/{JOB_ID}/status", headers=_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "processing"
        assert body["stage"] == "pose_extraction"
        assert body["progress_pct"] == 45

    def test_complete_job_includes_report_id(self, client):
        sb = MagicMock()
        sb.table.return_value = sb; sb.select.return_value = sb
        sb.eq.return_value = sb; sb.single.return_value = sb
        sb.execute.return_value = MagicMock(data=self._job_row(status="complete", stage="complete",
                                                                progress=100, report_id=REPORT_ID))
        with patch("app.api.v1.analysis.get_supabase", return_value=sb):
            resp = client.get(f"/api/v1/analysis/{JOB_ID}/status", headers=_headers())
        assert resp.json()["report_id"] == REPORT_ID

    def test_returns_warning_code_when_set(self, client):
        sb = MagicMock()
        sb.table.return_value = sb; sb.select.return_value = sb
        sb.eq.return_value = sb; sb.single.return_value = sb
        sb.execute.return_value = MagicMock(data=self._job_row(warning="WARNING_POOR_ANGLE"))
        with patch("app.api.v1.analysis.get_supabase", return_value=sb):
            resp = client.get(f"/api/v1/analysis/{JOB_ID}/status", headers=_headers())
        assert resp.json()["warning_code"] == "WARNING_POOR_ANGLE"

    def test_other_users_job_returns_404(self, client):
        sb = MagicMock()
        sb.table.return_value = sb; sb.select.return_value = sb
        sb.eq.return_value = sb; sb.single.return_value = sb
        sb.execute.return_value = MagicMock(data=self._job_row(user_id="different-user"))
        with patch("app.api.v1.analysis.get_supabase", return_value=sb):
            resp = client.get(f"/api/v1/analysis/{JOB_ID}/status", headers=_headers())
        assert resp.status_code == 404

    def test_nonexistent_job_returns_404(self, client):
        sb = MagicMock()
        sb.table.return_value = sb; sb.select.return_value = sb
        sb.eq.return_value = sb; sb.single.return_value = sb
        sb.execute.return_value = MagicMock(data=None)
        with patch("app.api.v1.analysis.get_supabase", return_value=sb):
            resp = client.get("/api/v1/analysis/nonexistent-id/status", headers=_headers())
        assert resp.status_code == 404

    def test_requires_auth(self, client):
        resp = client.get(f"/api/v1/analysis/{JOB_ID}/status")
        assert resp.status_code == 403


class TestConfirmUpload:
    def test_confirms_queued_job_with_s3_object(self, client):
        sb = MagicMock()
        sb.table.return_value = sb; sb.select.return_value = sb
        sb.eq.return_value = sb; sb.single.return_value = sb
        sb.execute.return_value = MagicMock(data={
            "video_s3_key": "uploads/user/video.mp4",
            "user_id": USER_ID,
            "status": "queued",
        })
        with patch("app.api.v1.analysis.get_supabase", return_value=sb), \
             patch("app.api.v1.analysis.object_exists", return_value=True):
            resp = client.post(f"/api/v1/analysis/{JOB_ID}/confirm", headers=_headers())
        assert resp.status_code == 202
        assert resp.json()["status"] == "queued"

    def test_s3_object_missing_returns_400(self, client):
        sb = MagicMock()
        sb.table.return_value = sb; sb.select.return_value = sb
        sb.eq.return_value = sb; sb.single.return_value = sb
        sb.execute.return_value = MagicMock(data={
            "video_s3_key": "uploads/user/video.mp4",
            "user_id": USER_ID,
            "status": "queued",
        })
        with patch("app.api.v1.analysis.get_supabase", return_value=sb), \
             patch("app.api.v1.analysis.object_exists", return_value=False):
            resp = client.post(f"/api/v1/analysis/{JOB_ID}/confirm", headers=_headers())
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "S3_OBJECT_NOT_FOUND"

    def test_already_processing_job_returns_409(self, client):
        sb = MagicMock()
        sb.table.return_value = sb; sb.select.return_value = sb
        sb.eq.return_value = sb; sb.single.return_value = sb
        sb.execute.return_value = MagicMock(data={
            "video_s3_key": "uploads/user/video.mp4",
            "user_id": USER_ID,
            "status": "processing",
        })
        with patch("app.api.v1.analysis.get_supabase", return_value=sb):
            resp = client.post(f"/api/v1/analysis/{JOB_ID}/confirm", headers=_headers())
        assert resp.status_code == 409

    def test_other_users_job_returns_404(self, client):
        sb = MagicMock()
        sb.table.return_value = sb; sb.select.return_value = sb
        sb.eq.return_value = sb; sb.single.return_value = sb
        sb.execute.return_value = MagicMock(data={
            "video_s3_key": "key.mp4", "user_id": "another-user", "status": "queued"
        })
        with patch("app.api.v1.analysis.get_supabase", return_value=sb):
            resp = client.post(f"/api/v1/analysis/{JOB_ID}/confirm", headers=_headers())
        assert resp.status_code == 404
