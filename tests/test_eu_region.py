"""Regression tests for the private EU Narwal variant."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGION_PATH = ROOT / "custom_components" / "narwal_cloud" / "region.py"


def _load_region_module():
    spec = importlib.util.spec_from_file_location("narwal_cloud_region", REGION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_eu_region_configuration() -> None:
    region = _load_region_module()
    assert region.API_BASE_URL == "https://eu-app.narwaltech.com"
    assert region.COUNTRY_CODE == "DK"
    assert region.BROKER_DISCOVERY_COUNTRY == "DK"


def test_eu_login_payload_uses_plaintext_inside_https() -> None:
    region = _load_region_module()
    payload = region.build_login_payload("user@example.invalid", "correct horse")
    assert payload == {
        "email": "user@example.invalid",
        "password": "correct horse",
    }
    assert "encrypted_password" not in payload


if __name__ == "__main__":
    test_eu_region_configuration()
    test_eu_login_payload_uses_plaintext_inside_https()
    print("EU region tests passed")
