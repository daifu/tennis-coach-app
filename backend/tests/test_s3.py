"""Tests for app/core/s3.py — S3 operations."""
import io
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError


@pytest.fixture(autouse=True)
def reset_s3_singleton():
    """Reset the module-level S3 singleton between tests."""
    import app.core.s3 as s3_module
    s3_module._s3 = None
    yield
    s3_module._s3 = None


@pytest.fixture
def mock_s3_client():
    with patch("boto3.client") as mock_boto:
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        yield mock_client


class TestUploadFileobj:
    def test_uploads_with_correct_args(self, mock_s3_client):
        from app.core.s3 import upload_fileobj
        buf = io.BytesIO(b"fake video data")
        upload_fileobj(buf, "uploads/user/video.mp4", "video/mp4")

        mock_s3_client.upload_fileobj.assert_called_once_with(
            buf,
            "test-bucket",
            "uploads/user/video.mp4",
            ExtraArgs={"ContentType": "video/mp4", "ServerSideEncryption": "AES256"},
        )

    def test_default_content_type_is_mp4(self, mock_s3_client):
        from app.core.s3 import upload_fileobj
        upload_fileobj(io.BytesIO(b"data"), "key.mp4")
        call_kwargs = mock_s3_client.upload_fileobj.call_args[1]
        assert call_kwargs["ExtraArgs"]["ContentType"] == "video/mp4"

    def test_mov_content_type_passes_through(self, mock_s3_client):
        from app.core.s3 import upload_fileobj
        upload_fileobj(io.BytesIO(b"data"), "key.mov", "video/quicktime")
        call_kwargs = mock_s3_client.upload_fileobj.call_args[1]
        assert call_kwargs["ExtraArgs"]["ContentType"] == "video/quicktime"

    def test_server_side_encryption_always_set(self, mock_s3_client):
        from app.core.s3 import upload_fileobj
        upload_fileobj(io.BytesIO(b"data"), "key.mp4")
        call_kwargs = mock_s3_client.upload_fileobj.call_args[1]
        assert call_kwargs["ExtraArgs"]["ServerSideEncryption"] == "AES256"


class TestGeneratePresignedPut:
    def test_returns_presigned_url(self, mock_s3_client):
        from app.core.s3 import generate_presigned_put
        mock_s3_client.generate_presigned_url.return_value = "https://s3.example.com/presigned"
        url = generate_presigned_put("uploads/user/video.mp4", "video/mp4")
        assert url == "https://s3.example.com/presigned"

    def test_correct_params_passed(self, mock_s3_client):
        from app.core.s3 import generate_presigned_put
        mock_s3_client.generate_presigned_url.return_value = "https://s3.example.com/presigned"
        generate_presigned_put("my-key.mp4", "video/mp4", expires_in=300)

        _, kwargs = mock_s3_client.generate_presigned_url.call_args
        assert kwargs["Params"]["Key"] == "my-key.mp4"
        assert kwargs["Params"]["ContentType"] == "video/mp4"
        assert kwargs["ExpiresIn"] == 300
        assert kwargs["Params"]["ServerSideEncryption"] == "AES256"

    def test_default_expiry_is_900(self, mock_s3_client):
        from app.core.s3 import generate_presigned_put
        mock_s3_client.generate_presigned_url.return_value = "https://s3.example.com/url"
        generate_presigned_put("key.mp4", "video/mp4")

        _, kwargs = mock_s3_client.generate_presigned_url.call_args
        assert kwargs["ExpiresIn"] == 900


class TestObjectExists:
    def test_returns_true_when_object_exists(self, mock_s3_client):
        from app.core.s3 import object_exists
        mock_s3_client.head_object.return_value = {"ContentLength": 1024}
        assert object_exists("uploads/user/video.mp4") is True

    def test_returns_false_when_object_missing(self, mock_s3_client):
        from app.core.s3 import object_exists
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )
        assert object_exists("uploads/user/missing.mp4") is False

    def test_returns_false_on_any_client_error(self, mock_s3_client):
        from app.core.s3 import object_exists
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadObject"
        )
        assert object_exists("key.mp4") is False
