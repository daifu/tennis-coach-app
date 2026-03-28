"""Tests for app/core/auth.py — JWT verification."""
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from tests.conftest import JWT_SECRET, USER_ID, make_token


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def get_user_id(token: str) -> str:
    from app.core.auth import get_current_user_id
    return get_current_user_id(_credentials(token))


class TestGetCurrentUserId:
    def test_valid_token_returns_user_id(self):
        token = make_token(USER_ID)
        assert get_user_id(token) == USER_ID

    def test_different_user_id_is_returned(self):
        other_id = "other-user-abc"
        token = make_token(other_id)
        assert get_user_id(token) == other_id

    def test_invalid_signature_raises_401(self):
        bad_token = make_token(USER_ID, secret="wrong-secret")
        with pytest.raises(HTTPException) as exc_info:
            get_user_id(bad_token)
        assert exc_info.value.status_code == 401

    def test_malformed_token_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            get_user_id("not.a.jwt")
        assert exc_info.value.status_code == 401

    def test_empty_token_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            get_user_id("")
        assert exc_info.value.status_code == 401

    def test_token_missing_sub_raises_401(self):
        # Token with no 'sub' field
        token = jwt.encode({"role": "authenticated"}, JWT_SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as exc_info:
            get_user_id(token)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"

    def test_expired_token_raises_401(self):
        import time
        token = jwt.encode({"sub": USER_ID, "exp": int(time.time()) - 3600}, JWT_SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as exc_info:
            get_user_id(token)
        assert exc_info.value.status_code == 401
