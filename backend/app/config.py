from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    s3_bucket_name: str

    modal_token_id: str = ""
    modal_token_secret: str = ""

    free_tier_monthly_upload_limit: int = 3
    max_video_duration_seconds: int = 60
    max_video_size_bytes: int = 157_286_400  # ~150 MB

    class Config:
        env_file = ".env"


settings = Settings()
