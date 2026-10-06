"""Tests for Firebase profile-image validation and Storage upload behavior."""

from io import BytesIO

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.exceptions import BadRequestError
from app.services.firebase_storage_service import FirebaseStorageService


class FakeBlob:
    def __init__(self):
        self.metadata = None
        self.content = None
        self.content_type = None

    def upload_from_string(self, content: bytes, content_type: str):
        self.content = content
        self.content_type = content_type


class FakeBucket:
    def __init__(self):
        self.blobs = {}

    def blob(self, name: str):
        blob = FakeBlob()
        self.blobs[name] = blob
        return blob


def make_upload(content: bytes, content_type: str = "image/png") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename="avatar.png",
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_upload_avatar_writes_image_and_download_token(monkeypatch):
    service = FirebaseStorageService()
    bucket = FakeBucket()
    monkeypatch.setattr(service, "_get_bucket", lambda: bucket)

    url = await service.upload_avatar("user-123", make_upload(b"image-bytes"))

    assert url.startswith("https://firebasestorage.googleapis.com/v0/b/")
    assert "profile-images" in url
    assert "user-123" in url
    blob = next(iter(bucket.blobs.values()))
    assert blob.content == b"image-bytes"
    assert blob.content_type == "image/png"
    assert blob.metadata["firebaseStorageDownloadTokens"] in url


@pytest.mark.asyncio
async def test_upload_avatar_rejects_unsupported_image_type():
    service = FirebaseStorageService()

    with pytest.raises(BadRequestError, match="JPEG, PNG, or WebP"):
        await service.upload_avatar("user-123", make_upload(b"image-bytes", "text/plain"))


@pytest.mark.asyncio
async def test_upload_avatar_rejects_images_over_five_megabytes():
    service = FirebaseStorageService()

    with pytest.raises(BadRequestError, match="5 MB or smaller"):
        await service.upload_avatar(
            "user-123",
            make_upload(b"x" * (5 * 1024 * 1024 + 1)),
        )
