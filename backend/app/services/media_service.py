"""Cloudinary-backed media upload for community posts.

The ``cloudinary`` SDK is imported lazily so the app keeps working when the
package (or credentials) are absent — uploading then fails with a clean
503 ``MEDIA_UPLOAD_UNAVAILABLE``.
"""

import asyncio
import logging
import secrets

from app.core.config import Settings, get_settings
from app.core.exceptions import CommunityError
from app.schemas.community import MediaUploadResponse

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")


def detect_image_mime(data: bytes) -> str | None:
    """Sniff the real image type from magic bytes, ignoring the Content-Type header."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:2] == b"BM":
        return "image/bmp"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if (
        len(data) >= 12
        and data[:3] == b"\x00\x00\x00"
        and data[4:8] == b"ftyp"
        and data[8:12] in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1")
    ):
        return "image/heic"
    return None


class MediaService:
    """Validate an uploaded image and push it to Cloudinary."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _cloudinary_configured(self) -> bool:
        return all(getattr(self.settings, key) for key in _REQUIRED_KEYS)

    async def upload_image(self, content: bytes, original_name: str = "post.jpg") -> MediaUploadResponse:
        if not content:
            raise CommunityError(400, "INVALID_IMAGE", "Uploaded file is empty.", field="image")

        if len(content) > self.settings.MAX_FILE_SIZE_MB * 1_000_000:
            raise CommunityError(
                413,
                "IMAGE_TOO_LARGE",
                f"Image exceeds the {self.settings.MAX_FILE_SIZE_MB}MB limit.",
                field="image",
            )

        mime = detect_image_mime(content)
        if mime is None:
            raise CommunityError(
                400,
                "INVALID_IMAGE",
                "Unsupported file. Upload a JPEG, PNG, WebP, GIF, BMP or HEIC image.",
                field="image",
            )
        if mime not in self.settings.CLOUDINARY_ALLOWED_MIMES:
            raise CommunityError(
                400, "INVALID_IMAGE", f"Image type {mime} is not allowed.", field="image"
            )

        if not self._cloudinary_configured():
            raise CommunityError(
                503,
                "MEDIA_UPLOAD_UNAVAILABLE",
                "Media uploads are not configured on the server.",
                field="image",
            )

        try:
            return await asyncio.to_thread(
                self._upload_sync, content, original_name
            )
        except CommunityError:
            raise
        except Exception:
            logger.exception("Cloudinary upload failed")
            raise CommunityError(
                503,
                "MEDIA_UPLOAD_FAILED",
                "Image could not be uploaded. Please try again.",
                field="image",
            )

    def _upload_sync(self, content: bytes, original_name: str) -> MediaUploadResponse:
        try:
            import cloudinary
        except ImportError:
            raise CommunityError(
                503,
                "MEDIA_UPLOAD_UNAVAILABLE",
                "Media uploads are not available on this server.",
                field="image",
            )
        from cloudinary.uploader import upload

        cloudinary.config(
            cloud_name=self.settings.CLOUDINARY_CLOUD_NAME,
            api_key=self.settings.CLOUDINARY_API_KEY,
            api_secret=self.settings.CLOUDINARY_API_SECRET,
            secure=True,
        )

        result = upload(
            content,
            public_id=_public_id_from_name(original_name),
            folder=self.settings.CLOUDINARY_FOLDER,
            resource_type="image",
            overwrite=False,
        )

        secure_url = result.get("secure_url")
        public_id = result.get("public_id")
        if not secure_url or not public_id:
            logger.warning("Cloudinary returned incomplete upload result: %s", result)
            raise CommunityError(
                503,
                "MEDIA_UPLOAD_FAILED",
                "Image could not be uploaded. Please try again.",
                field="image",
            )
        return MediaUploadResponse(url=secure_url, publicId=public_id)


def _public_id_from_name(original_name: str) -> str:
    """Public id derived from the client filename plus a short random suffix."""
    base, _, _ext = original_name.partition(".")
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in base).strip("_") or "image"
    return f"{cleaned[:40]}_{secrets.token_hex(4)}"