"""Direct-to-object-storage media upload URL generator.

Allows mobile and web clients to upload media directly to CDN/Cloudinary/S3
without proxying binary file bytes through API server processes.
"""

import hashlib
import hmac
import time
from uuid import uuid4
from fastapi import APIRouter, Depends, Request
import logging

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError, ValidationFailedError
from app.models.user import User
from app.schemas.community import MediaUploadUrlRequest, MediaUploadUrlResponse
from app.services.cloudinary_service import cloudinary_service

router = APIRouter()
log = logging.getLogger(__name__)


@router.post(
    "/community/media/upload-url",
    response_model=MediaUploadUrlResponse,
    summary="Generate a direct pre-signed upload URL for media",
)
async def generate_upload_url(
    data: MediaUploadUrlRequest,
    user: User = Depends(get_current_user),
):
    """Generate signature and parameters for direct client-to-storage upload."""
    try:
        public_id = f"community_{user.id}_{int(time.time())}_{uuid4().hex[:8]}"
        
        # Check Cloudinary configuration
        if cloudinary_service.is_configured():
            timestamp = int(time.time())
            folder = "community"
            
            # Generate Cloudinary signature parameters
            params_to_sign = f"folder={folder}&public_id={public_id}&timestamp={timestamp}"
            api_secret = getattr(cloudinary_service, "api_secret", "") or ""
            api_key = getattr(cloudinary_service, "api_key", "") or ""
            cloud_name = getattr(cloudinary_service, "cloud_name", "") or ""

            if api_secret:
                signature = hashlib.sha1(f"{params_to_sign}{api_secret}".encode("utf-8")).hexdigest()
            else:
                signature = ""

            upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
            media_url = f"https://res.cloudinary.com/{cloud_name}/image/upload/{folder}/{public_id}"

            return MediaUploadUrlResponse(
                upload_url=upload_url,
                public_id=public_id,
                media_url=media_url,
                fields={
                    "api_key": api_key,
                    "timestamp": str(timestamp),
                    "signature": signature,
                    "folder": folder,
                    "public_id": public_id,
                },
                headers={"Content-Type": "multipart/form-data"},
            )
        else:
            # Fallback upload direct endpoint placeholder
            return MediaUploadUrlResponse(
                upload_url="/api/v1/community/posts",
                public_id=public_id,
                media_url="",
                fields={},
                headers={},
            )
    except Exception as e:
        log.exception("Generate upload URL failed")
        raise ServiceUnavailableError("Failed to generate upload URL")
