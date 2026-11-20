"""Private object storage (S3 / SeaweedFS) and photo processing for proof of work.

Photos: magic-byte allow-list → decode → orient → resize (max 1280 px) → re-encode JPEG under
~200 KB (product plan) → no metadata (EXIF/GPS stripped by re-encoding) → watermark
(desk, IST time, staff code). Served only through short-lived signed URLs.
"""

import asyncio
import hashlib
import io
import warnings
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.core.errors import AppError

IST = ZoneInfo("Asia/Kolkata")
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
TARGET_BYTES = 200 * 1024
MAX_SIDE = 1280
THUMB_SIDE = 320
_MAGIC = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"RIFF": "webp",
}
Image.MAX_IMAGE_PIXELS = 40_000_000  # decompression-bomb guard
warnings.simplefilter("error", Image.DecompressionBombWarning)  # refuse, don't just warn


@lru_cache
def s3() -> Any:
    s = get_settings()
    # Empty values mean "use the AWS instance role" (production); keys are for local S3 only.
    local = bool(s.s3_endpoint_url)
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url or None,
        aws_access_key_id=s.s3_access_key or None,
        aws_secret_access_key=s.s3_secret_key or None,
        region_name=s.s3_region,
        config=Config(
            signature_version="s3v4", s3={"addressing_style": "path" if local else "virtual"}
        ),
    )


def ensure_bucket() -> None:
    bucket = get_settings().s3_bucket
    try:
        s3().head_bucket(Bucket=bucket)
    except ClientError:
        s3().create_bucket(Bucket=bucket)


async def put_object(key: str, data: bytes, content_type: str) -> None:
    await asyncio.to_thread(
        s3().put_object,
        Bucket=get_settings().s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def signed_url(key: str, seconds: int = 300) -> str:
    url: str = s3().generate_presigned_url(
        "get_object", Params={"Bucket": get_settings().s3_bucket, "Key": key}, ExpiresIn=seconds
    )
    return url


@dataclass(frozen=True)
class ProcessedPhoto:
    jpeg: bytes
    thumb: bytes
    width: int
    height: int
    sha256: bytes
    source_sha256: bytes


def _sniff(data: bytes) -> str | None:
    for magic, kind in _MAGIC.items():
        if data.startswith(magic):
            if kind == "webp" and data[8:12] != b"WEBP":
                return None
            return kind
    return None


def _encode_under(img: Image.Image, target: int) -> bytes:
    for quality in (82, 74, 66, 58, 50, 42):
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
        if buf.tell() <= target:
            return buf.getvalue()
    return buf.getvalue()


def _watermark(img: Image.Image, text: str) -> None:
    draw = ImageDraw.Draw(img, "RGBA")
    font = ImageFont.load_default(size=max(14, img.width // 48))
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    pad = 8
    h = bottom - top + pad * 2
    draw.rectangle([(0, img.height - h), (img.width, img.height)], fill=(12, 46, 35, 170))
    draw.text((pad, img.height - h + pad - top), text, font=font, fill=(246, 235, 200, 255))


def process_photo(raw: bytes, watermark: str) -> ProcessedPhoto:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise AppError("PHOTO_TOO_LARGE", 413, max_mb=MAX_UPLOAD_BYTES // 1024 // 1024)
    if _sniff(raw) is None:
        raise AppError("PHOTO_TYPE_NOT_ALLOWED", 415)
    try:
        opened: Image.Image = Image.open(io.BytesIO(raw))
        opened.load()
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise AppError("PHOTO_UNREADABLE", 422) from exc
    oriented = ImageOps.exif_transpose(opened) or opened
    img = oriented.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    _watermark(img, watermark)
    jpeg = _encode_under(img, TARGET_BYTES)
    thumb_img = img.copy()
    thumb_img.thumbnail((THUMB_SIDE, THUMB_SIDE))
    thumb = _encode_under(thumb_img, 24 * 1024)
    return ProcessedPhoto(
        jpeg=jpeg,
        thumb=thumb,
        width=img.width,
        height=img.height,
        sha256=hashlib.sha256(jpeg).digest(),
        source_sha256=hashlib.sha256(raw).digest(),
    )


def ist_label(ts: datetime) -> str:
    return ts.astimezone(IST).strftime("%d %b %Y %H:%M IST")
