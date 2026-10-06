from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.exceptions import BadRequestError, ServiceUnavailableError
from app.services.cloudinary_service import CloudinaryService


def make_upload(content: bytes, content_type: str = "image/png") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename="avatar.png",
        headers=Headers({"content-type": content_type}),
    )


def make_service() -> CloudinaryService:
    service = CloudinaryService.__new__(CloudinaryService)
    service.settings = SimpleNamespace(
        CLOUDINARY_CLOUD_NAME="test-cloud",
        CLOUDINARY_API_KEY="test-key",
        CLOUDINARY_API_SECRET="test-secret",
    )
    service._configured = True
    return service


@pytest.mark.asyncio
async def test_upload_image_returns_cloudinary_secure_url_and_public_id(monkeypatch):
    service = make_service()
    upload = Mock(
        return_value={
            "secure_url": "https://res.cloudinary.com/test-cloud/image/upload/avatar.png",
            "public_id": "profile-images/user/avatar",
        }
    )
    monkeypatch.setattr("app.services.cloudinary_service.cloudinary.uploader.upload", upload)

    result = await service.upload_image(make_upload(b"image-bytes"), folder="profile-images/user")

    assert result == (
        "https://res.cloudinary.com/test-cloud/image/upload/avatar.png",
        "profile-images/user/avatar",
    )
    assert upload.call_args.kwargs["folder"] == "profile-images/user"


@pytest.mark.asyncio
async def test_upload_image_rejects_unsupported_image_type():
    service = make_service()

    with pytest.raises(BadRequestError, match="Invalid image type"):
        await service.upload_image(make_upload(b"image-bytes", "text/plain"))


@pytest.mark.asyncio
async def test_upload_image_rejects_when_cloudinary_is_unconfigured():
    service = make_service()
    service._configured = False

    with pytest.raises(ServiceUnavailableError, match="not configured"):
        await service.upload_image(make_upload(b"image-bytes"))
