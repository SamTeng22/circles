import uuid
import boto3
from botocore.config import Config
from app.core.config import settings

# One shared S3-compatible client. Works for Cloudflare R2 (set S3_ENDPOINT_URL)
# or real AWS S3 (leave S3_ENDPOINT_URL blank -> endpoint_url=None).
_s3 = boto3.client(
    "s3",
    endpoint_url=settings.S3_ENDPOINT_URL or None,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.S3_REGION,
    config=Config(signature_version="s3v4"),
)


def put_object(data: bytes, content_type: str, circle_id: str, filename: str) -> str:
    """Store raw bytes and return the object key."""
    key = f"notes/{circle_id}/{uuid.uuid4()}/{filename}"
    _s3.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type or "application/octet-stream",
    )
    return key


def get_object(key: str) -> bytes:
    """Fetch the raw bytes of a stored object (used to reprocess a note)."""
    resp = _s3.get_object(Bucket=settings.S3_BUCKET, Key=key)
    return resp["Body"].read()


def presigned_get(key: str, expires: int = 3600) -> str:
    """Short-lived URL to download/view the original file."""
    return _s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )


def delete_object(key: str) -> None:
    """Remove an object (used when a note is deleted)."""
    _s3.delete_object(Bucket=settings.S3_BUCKET, Key=key)
