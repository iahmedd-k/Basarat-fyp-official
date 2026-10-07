"""Rebuild the tracked, split inference dataset used by forecast routes."""

from __future__ import annotations

import os
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS_DIR = ROOT / "deploy_assets"
TARGET = ROOT / "data" / "features" / "features_daily.parquet"
EXPECTED_SIZE = 41_180_828
EXPECTED_SHA256 = "f52ddc78c74389b4852486e66e17bf00abb35eb8305f697524431bcbb98f0459"


def prepare_features(force: bool = False) -> Path:
    parts = sorted(PARTS_DIR.glob("features_daily.parquet.part-*"))
    if not parts:
        if TARGET.is_file():
            return TARGET
        raise FileNotFoundError(
            "Forecast feature data is missing. Include backend/deploy_assets/ "
            "or provide data/features/features_daily.parquet."
        )

    # Re-use existing target if it matches expected size and force is not set
    if TARGET.is_file() and not force:
        if TARGET.stat().st_size == EXPECTED_SIZE:
            return TARGET

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
