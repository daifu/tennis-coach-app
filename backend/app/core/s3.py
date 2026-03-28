import boto3
from botocore.exceptions import ClientError
from app.config import settings

_s3 = None


def get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
    return _s3


def upload_fileobj(fileobj, s3_key: str, content_type: str = "video/mp4") -> None:
    get_s3().upload_fileobj(
        fileobj,
        settings.s3_bucket_name,
        s3_key,
        ExtraArgs={"ContentType": content_type, "ServerSideEncryption": "AES256"},
    )


def generate_presigned_put(s3_key: str, content_type: str, expires_in: int = 900) -> str:
    return get_s3().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.s3_bucket_name,
            "Key": s3_key,
            "ContentType": content_type,
            "ServerSideEncryption": "AES256",
        },
        ExpiresIn=expires_in,
    )


def object_exists(s3_key: str) -> bool:
    try:
        get_s3().head_object(Bucket=settings.s3_bucket_name, Key=s3_key)
        return True
    except ClientError:
        return False
