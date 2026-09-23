"""Rebuild the tracked, split inference dataset used by forecast routes."""

from __future__ import annotations

import os
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS_DIR = ROOT / "deploy_assets"
TARGET = ROOT / "data" / "features" / "features_daily.parquet"
EXPECTED_SIZE = 101_686_063
EXPECTED_SHA256 = "9d6d3af65121f2b1d4a7d75b14adceab05a8ff2a19a3ebba8ee104c17da21976"


def prepare_features() -> Path:
    parts = sorted(PARTS_DIR.glob("features_daily.parquet.part-*"))
    if not parts:
        if TARGET.is_file():
            return TARGET
        raise FileNotFoundError(
            "Forecast feature data is missing. Include backend/deploy_assets/ "
            "or provide data/features/features_daily.parquet."
        )
    expected_names = [f"features_daily.parquet.part-{index:02d}" for index in range(len(parts))]
    if [part.name for part in parts] != expected_names:
        raise RuntimeError("Forecast feature chunks are incomplete or out of sequence.")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    temporary = TARGET.with_suffix(TARGET.suffix + ".tmp")
    try:
        with temporary.open("wb") as output:
            for part in parts:
                with part.open("rb") as source:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        checksum = hashlib.sha256()
        with temporary.open("rb") as reconstructed:
            while chunk := reconstructed.read(1024 * 1024):
                checksum.update(chunk)
        digest = checksum.hexdigest()
        if temporary.stat().st_size != EXPECTED_SIZE or digest != EXPECTED_SHA256:
            raise RuntimeError("Reconstructed forecast feature data failed its size/hash check.")
        os.replace(temporary, TARGET)
    finally:
        temporary.unlink(missing_ok=True)
    return TARGET


if __name__ == "__main__":
    result = prepare_features()
    print(f"Forecast feature data ready: {result.name} ({result.stat().st_size} bytes)")
