"""
Shared fixtures for all backend tests.
Supabase, S3, and Modal are always mocked — no real external calls are made.
"""
import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from jose import jwt

# ---------------------------------------------------------------------------
# Environment stub — must be set before app imports
# ---------------------------------------------------------------------------
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "super-secret-jwt-key-for-tests-only")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-key-id")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")

JWT_SECRET = "super-secret-jwt-key-for-tests-only"
USER_ID        = "10000000-0000-0000-0000-000000000001"
PRO_PLAYER_ID  = "20000000-0000-0000-0000-000000000002"
JOB_ID         = "30000000-0000-0000-0000-000000000003"
REPORT_ID      = "40000000-0000-0000-0000-000000000004"


def make_token(user_id: str = USER_ID, secret: str = JWT_SECRET) -> str:
    return jwt.encode({"sub": user_id, "role": "authenticated"}, secret, algorithm="HS256")


@pytest.fixture
def valid_token() -> str:
    return make_token()


@pytest.fixture
def auth_headers(valid_token) -> dict:
    return {"Authorization": f"Bearer {valid_token}"}


@pytest.fixture
def mock_supabase():
    """Returns a MagicMock that mimics the Supabase fluent query builder."""
    sb = MagicMock()
    # Default chain: .table().select().eq().single().execute()
    sb.table.return_value = sb
    sb.select.return_value = sb
    sb.eq.return_value = sb
    sb.single.return_value = sb
    sb.insert.return_value = sb
    sb.update.return_value = sb
    sb.limit.return_value = sb
    return sb


@pytest.fixture
def client(mock_supabase):
    """FastAPI TestClient with Supabase patched."""
    with patch("app.core.supabase._client", mock_supabase):
        from app.main import app
        yield TestClient(app)
