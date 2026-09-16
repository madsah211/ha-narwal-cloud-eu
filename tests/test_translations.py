"""Translation coverage checks for every Narwal entity platform."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "narwal_cloud"

ENTITY_KEYS = {
    "binary_sensor": {"turbo_mode"},
    "button": {"wash_and_dry_mop", "finish_station"},
    "camera": {"map", "map_data"},
    "select": {
        "cleaning_mode",
        "suction_power",
        "mop_humidity",
        "cleaning_cycles",
    },
    "sensor": {
        "battery",
        "movement_status",
        "cleaning_status",
        "filter_remaining",
        "mop_remaining",
        "side_brush_remaining",
        "sponge_remaining",
        "main_brush_remaining",
    },
}

SELECT_STATES = {
    "cleaning_mode": {
        "freo_mind",
        "vacuum",
        "mop",
        "vacuum_and_mop",
        "vacuum_then_mop",
    },
    "suction_power": {"quiet", "standard", "strong"},
    "mop_humidity": {"slightly_dry", "standard", "slightly_wet"},
    "cleaning_cycles": {"one_time", "two_times", "three_times"},
}


def load_translation(name: str) -> dict:
    path = COMPONENT / ("strings.json" if name == "strings" else f"translations/{name}.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_english_and_danish_cover_every_entity() -> None:
    for language in ("strings", "en", "da"):
        entity = load_translation(language)["entity"]
        for platform, keys in ENTITY_KEYS.items():
            assert keys <= set(entity[platform]), (language, platform, keys - set(entity[platform]))
        for key, states in SELECT_STATES.items():
            assert states == set(entity["select"][key]["state"]), (language, key)


def test_entity_code_uses_translation_keys_instead_of_english_names() -> None:
    button_source = (COMPONENT / "button.py").read_text(encoding="utf-8")
    select_source = (COMPONENT / "select.py").read_text(encoding="utf-8")
    sensor_source = (COMPONENT / "sensor.py").read_text(encoding="utf-8")

    assert "self._attr_translation_key = action" in button_source
    assert "self._attr_translation_key = key" in select_source
    assert "self._attr_translation_key =" in sensor_source
    assert "self._attr_name = name" not in button_source
    assert "self._attr_name = name" not in select_source


if __name__ == "__main__":
    test_english_and_danish_cover_every_entity()
    test_entity_code_uses_translation_keys_instead_of_english_names()
    print("translation tests passed")
