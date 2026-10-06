"""Check Cloudinary credentials and API connectivity without uploading media."""

import os
import sys
from pathlib import Path

import cloudinary
import cloudinary.api
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
CREDENTIAL_NAMES = (
    "CLOUDINARY_CLOUD_NAME",
    "CLOUDINARY_API_KEY",
    "CLOUDINARY_API_SECRET",
)


def main() -> int:
    load_dotenv(BACKEND_DIR / ".env")

    credentials = {name: os.getenv(name) for name in CREDENTIAL_NAMES}
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        print(f"Cloudinary connection test: NOT CONFIGURED (missing {', '.join(missing)}).")
        return 1

    cloudinary.config(
        cloud_name=credentials["CLOUDINARY_CLOUD_NAME"],
        api_key=credentials["CLOUDINARY_API_KEY"],
        api_secret=credentials["CLOUDINARY_API_SECRET"],
        secure=True,
    )

    try:
        response = cloudinary.api.ping()
    except Exception as exc:
        message = str(exc)
        for value in credentials.values():
            if value:
                message = message.replace(value, "[REDACTED]")
        print(f"Cloudinary connection test: FAILED ({type(exc).__name__}: {message})")
        return 1

    status = response.get("status")
    if status != "ok":
        print(f"Cloudinary connection test: UNEXPECTED RESPONSE (status={status!r}).")
        return 1

    print("Cloudinary connection test: OK (authenticated API ping succeeded).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
