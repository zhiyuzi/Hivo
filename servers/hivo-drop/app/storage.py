"""R2/S3-compatible object storage operations."""
import hashlib

import boto3
from botocore.exceptions import ClientError

from .config import settings


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint or None,
        aws_access_key_id=settings.r2_access_key_id or None,
        aws_secret_access_key=settings.r2_secret_access_key or None,
        region_name="auto",
    )


def _iss_hash(iss: str) -> str:
    return hashlib.sha256(iss.encode()).hexdigest()[:16]


def make_r2_key(iss: str, sub: str, path: str) -> str:
    """Build the R2 object key for a file."""
    return f"{_iss_hash(iss)}/{sub}/{path.lstrip('/')}"


def upload_object(r2_key: str, data: bytes, content_type: str) -> None:
    client = _client()
    client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=r2_key,
        Body=data,
        ContentType=content_type,
    )


def download_object(r2_key: str) -> bytes:
    client = _client()
    try:
        resp = client.get_object(Bucket=settings.r2_bucket_name, Key=r2_key)
        return resp["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise FileNotFoundError(r2_key)
        raise


def delete_object(r2_key: str) -> None:
    client = _client()
    client.delete_object(Bucket=settings.r2_bucket_name, Key=r2_key)
