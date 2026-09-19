import os
import logging
from typing import Optional, Tuple

import cloudinary
import cloudinary.uploader
import cloudinary.api
from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import BadRequestError, ServiceUnavailableError

log = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class CloudinaryService:
    def __init__(self):
        self.settings = get_settings()
        self._configured = False
        self._configure()

    def _configure(self) -> None:
        try:
            cloudinary.config(
                cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
                api_key=os.getenv("CLOUDINARY_API_KEY"),
                api_secret=os.getenv("CLOUDINARY_API_SECRET"),
                secure=True,
            )
            self._configured = True
        except Exception as e:
            log.warning("Cloudinary not configured: %s", e)
            self._configured = False

    def is_configured(self) -> bool:
        return self._configured

    def validate_image(self, file: UploadFile) -> None:
        if not file.content_type or file.content_type not in ALLOWED_MIME_TYPES:
            raise BadRequestError(
                f"Invalid image type. Allowed: {', '.join(ALLOWED_MIME_TYPES)}",
                field="image",
            )

        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)

        if size > MAX_FILE_SIZE_BYTES:
            raise BadRequestError(
                f"Image too large. Maximum size: {MAX_FILE_SIZE_MB}MB",
                field="image",
            )

    async def upload_image(self, file: UploadFile, folder: str = "community") -> Tuple[str, str]:
        if not self._configured:
            raise ServiceUnavailableError("Image upload service not configured")

        self.validate_image(file)

        try:
            result = cloudinary.uploader.upload(
                file.file,
                folder=folder,
                resource_type="image",
                overwrite=False,
                unique_filename=True,
                use_filename=False,
            )
            return result["secure_url"], result["public_id"]
        except Exception as e:
            log.exception("Cloudinary upload failed")
            raise ServiceUnavailableError("Failed to upload image")

    async def delete_image(self, public_id: str) -> bool:
        if not self._configured or not public_id:
            return False

        try:
            result = cloudinary.uploader.destroy(public_id, resource_type="image")
            return result.get("result") == "ok"
        except Exception as e:
            log.warning("Cloudinary delete failed for %s: %s", public_id, e)
            return False


cloudinary_service = CloudinaryService()