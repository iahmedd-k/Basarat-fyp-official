"""Firebase Storage uploads for user profile images."""

import asyncio
import logging
import secrets
from pathlib import Path
from urllib.parse import quote

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import BadRequestError, ServiceUnavailableError

log = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024


class FirebaseStorageService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _get_bucket(self):
        bucket_name = self.settings.FIREBASE_STORAGE_BUCKET
        credentials_path = Path(self.settings.FIREBASE_CREDENTIALS_PATH)
        if not self.settings.FIREBASE_ENABLED or not bucket_name or not credentials_path.is_file():
            raise ServiceUnavailableError(
                "Profile image storage is not configured. Set Firebase credentials and FIREBASE_STORAGE_BUCKET."
            )

        try:
            import firebase_admin
            from firebase_admin import credentials, storage

            app = firebase_admin.get_app() if firebase_admin._apps else firebase_admin.initialize_app(
                credentials.Certificate(str(credentials_path)),
                {"storageBucket": bucket_name},
            )
            return storage.bucket(name=bucket_name, app=app)
        except ServiceUnavailableError:
            raise
        except Exception as exc:
            log.exception("Firebase Storage initialization failed")
            raise ServiceUnavailableError("Could not initialize Firebase Storage.") from exc

    async def upload_avatar(self, user_id: str, image: UploadFile) -> str:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise BadRequestError("Profile image must be a JPEG, PNG, or WebP file.", field="image")

        content = await image.read(MAX_IMAGE_SIZE_BYTES + 1)
        if not content:
            raise BadRequestError("Profile image cannot be empty.", field="image")
        if len(content) > MAX_IMAGE_SIZE_BYTES:
            raise BadRequestError("Profile image must be 5 MB or smaller.", field="image")

        suffix = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }[image.content_type]
        object_name = f"profile-images/{user_id}/{secrets.token_urlsafe(18)}{suffix}"
        download_token = secrets.token_urlsafe(32)

        def store_image() -> None:
            bucket = self._get_bucket()
            blob = bucket.blob(object_name)
            blob.metadata = {"firebaseStorageDownloadTokens": download_token}
            blob.upload_from_string(content, content_type=image.content_type)

        try:
            await asyncio.to_thread(store_image)
        except ServiceUnavailableError:
            raise
        except Exception as exc:
            log.exception("Firebase profile image upload failed")
            raise ServiceUnavailableError("Could not upload profile image.") from exc

        bucket_name = self.settings.FIREBASE_STORAGE_BUCKET
        return (
            f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/"
            f"{quote(object_name, safe='')}?alt=media&token={download_token}"
        )


firebase_storage_service = FirebaseStorageService()
