"""
MinIO / S3-compatible object storage adapter for the worker service.

Used by the document-fetch pipeline to persist and retrieve raw filing
documents.  All operations are async via aioboto3.

Object key strategy:
    {company_number}/filings/{transaction_id}/{document_id}{ext}

    e.g.  12345678/filings/MzAwNTI0NDY5OW.../MzAwNTI0NDY5OW....xhtml

The key is deterministic: given the same company_number, transaction_id,
document_id, and content_type, the key is always identical.  This makes
re-fetching safe — MinIO overwrites the object with the same content.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import aioboto3

from app.config import settings

# Preferred content types for download, in priority order.
# The parser phase only supports structured formats (xhtml/html/xml),
# so we prefer those over PDF where available.
CONTENT_TYPE_PRIORITY: list[str] = [
    "application/xhtml+xml",
    "text/html",
    "application/xml",
    "application/pdf",
]

_CONTENT_TYPE_EXT: dict[str, str] = {
    "application/xhtml+xml": ".xhtml",
    "text/html": ".html",
    "application/xml": ".xml",
    "application/pdf": ".pdf",
}


def build_storage_key(
    company_number: str,
    transaction_id: str,
    document_id: str,
    content_type: str,
) -> str:
    """
    Build a deterministic MinIO object key for a filing document.

    The extension is derived from the content_type so parsers can identify
    the document format from the key alone without reading DB records.
    """
    # Strip any content-type parameters (e.g. "text/html; charset=utf-8")
    base_ct = content_type.split(";")[0].strip()
    ext = _CONTENT_TYPE_EXT.get(base_ct, ".bin")
    return f"{company_number}/filings/{transaction_id}/{document_id}{ext}"


@asynccontextmanager
async def get_storage_client() -> AsyncGenerator[Any, None]:
    """
    Async context manager yielding a boto3-compatible S3 client for MinIO.

    The client is scoped to the context block and closed on exit.

    Usage:
        async with get_storage_client() as s3:
            await put_document(s3, bucket, key, data, content_type)
    """
    endpoint = settings.minio_endpoint
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"

    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        # MinIO ignores region; boto3 requires a non-empty value.
        region_name="us-east-1",
    ) as client:
        yield client


async def object_exists(client: Any, bucket: str, key: str) -> bool:
    """Return True if *key* exists in *bucket*, False on 404."""
    try:
        await client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception as exc:
        # boto3/aioboto3 raises ClientError; code is in exc.response["Error"]["Code"]
        response = getattr(exc, "response", None)
        if response is not None:
            code = response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey"):
                return False
        raise


async def put_document(
    client: Any,
    bucket: str,
    key: str,
    data: bytes,
    content_type: str,
) -> str:
    """
    Upload *data* to *bucket*/*key* and return the ETag string.

    Idempotent: uploading the same bytes to the same key overwrites the
    existing object without error.  The returned ETag can be used to detect
    content changes on re-fetch.
    """
    response = await client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return response.get("ETag", "").strip('"')


async def get_document(client: Any, bucket: str, key: str) -> bytes:
    """
    Download *key* from *bucket* and return the raw bytes.

    Raises the underlying aioboto3 ClientError (e.g. NoSuchKey) if the
    object does not exist.  Callers should use object_exists() first when
    existence is uncertain, or catch ClientError explicitly.
    """
    response = await client.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    return await body.read()
