"""Upload a tiny test image to Cloudinary, verify its URL, then remove it."""

import asyncio
import base64
from io import BytesIO
import sys
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import requests
from dotenv import load_dotenv
from fastapi import UploadFile
from starlette.datastructures import Headers


BACKEND_DIR = Path(__file__).resolve().parents[1]
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j4XcAAAAASUVORK5CYII="
)


async def run_upload_test() -> int:
    load_dotenv(BACKEND_DIR / ".env")
    sys.path.insert(0, str(BACKEND_DIR))

    from app.services.cloudinary_service import cloudinary_service

    if not cloudinary_service.is_configured():
        print("Cloudinary upload test: NOT CONFIGURED.")
        return 1

    upload = UploadFile(
        file=BytesIO(PNG_1X1),
        filename="cloudinary-connection-test.png",
        headers=Headers({"content-type": "image/png"}),
    )
    public_id = None
    exit_code = 0
    try:
        url, public_id = await cloudinary_service.upload_image(
            upload,
            folder=f"connection-tests/{uuid4().hex}",
        )
        parsed_url = urlparse(url)
        if parsed_url.scheme != "https" or parsed_url.netloc != "res.cloudinary.com":
            print("Cloudinary upload test: FAILED (upload returned an unexpected URL).")
            exit_code = 1
        else:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            print(f"Cloudinary upload test: OK (uploaded image URL returned and reachable: {url})")
    except Exception as exc:
        message = str(exc)
        for secret in (cloudinary_service.api_key, cloudinary_service.api_secret):
            if secret:
                message = message.replace(secret, "[REDACTED]")
        print(f"Cloudinary upload test: FAILED ({type(exc).__name__}: {message})")
        exit_code = 1
    finally:
        if public_id:
            if await cloudinary_service.delete_image(public_id):
                print("Cloudinary test image cleanup: OK.")
            else:
                print("Cloudinary test image cleanup: FAILED.")
                exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(run_upload_test()))
