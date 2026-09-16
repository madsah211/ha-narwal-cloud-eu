"""Packaging checks for the Narwal Cloud EU build."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "narwal_cloud" / "manifest.json"
ARCHIVE = ROOT / "dist" / "narwal-cloud-eu-0.9.3-eu.9.zip"


def test_manifest_identifies_eu_build() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["name"] == "Narwal Cloud EU (unofficial)"
    assert data["version"] == "0.9.3-eu.9"
    assert data["domain"] == "narwal_cloud"


def test_release_archive_matches_component_tree() -> None:
    import zipfile

    assert ARCHIVE.exists()
    with zipfile.ZipFile(ARCHIVE) as archive:
        names = set(archive.namelist())
        assert "EU-BUILD.md" not in names
        assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
        source_root = ROOT / "custom_components" / "narwal_cloud"
        for source in source_root.rglob("*"):
            if not source.is_file() or "__pycache__" in source.parts or source.suffix == ".pyc":
                continue
            name = (Path("custom_components") / "narwal_cloud" / source.relative_to(source_root)).as_posix()
            assert name in names
            assert archive.read(name) == source.read_bytes()


if __name__ == "__main__":
    test_manifest_identifies_eu_build()
    test_release_archive_matches_component_tree()
    print("package tests passed")
