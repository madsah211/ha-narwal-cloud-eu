"""Build the Narwal Cloud EU installation archive."""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "custom_components" / "narwal_cloud"
DIST = ROOT / "dist"
ARCHIVE = DIST / "narwal-cloud-eu-0.9.3-eu.9.zip"

DIST.mkdir(exist_ok=True)
if ARCHIVE.exists():
    ARCHIVE.unlink()

with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as output:
    for path in sorted(SOURCE.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        archive_path = Path("custom_components") / "narwal_cloud" / path.relative_to(SOURCE)
        output.write(path, archive_path.as_posix())
print(ARCHIVE)
