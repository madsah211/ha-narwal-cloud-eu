"""Regression tests for independent map and cleaning-plan publication."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from datetime import timedelta
from pathlib import Path

from test_auth import API

ROOT = Path(__file__).parents[1] / "custom_components" / "narwal_cloud"


def _load_coordinator():
    homeassistant = types.ModuleType("homeassistant")
    exceptions = types.ModuleType("homeassistant.exceptions")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers")
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")

    exceptions.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})
    core.HomeAssistant = object

    class DataUpdateCoordinator:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, hass, **_kwargs):
            self.hass = hass
            self.data = None

        def async_set_updated_data(self, data):
            self.data = data

    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.UpdateFailed = type("UpdateFailed", (Exception,), {})
    sys.modules.update(
        {
            "homeassistant": homeassistant,
            "homeassistant.exceptions": exceptions,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.update_coordinator": update_coordinator,
        }
    )

    spec = importlib.util.spec_from_file_location(
        "narwal_cloud.coordinator", ROOT / "coordinator.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


COORDINATOR = _load_coordinator()
PROTOCOL = sys.modules["narwal_cloud.protocol"]


def test_valid_map_survives_clean_plan_failure() -> None:
    async def run() -> None:
        expected_map = PROTOCOL.NarwalMap(
            revision=42,
            resolution=50,
            width=2,
            height=2,
            compressed_grid=b"grid",
        )

        class Client:
            async def async_get_map(self, _device_id, _product_id):
                return expected_map

            async def async_get_clean_plans(self, _device_id, _product_id):
                raise API.NarwalCloudError("plans unavailable")

        coordinator = COORDINATOR.NarwalCloudCoordinator(
            object(), Client(), "device", "product", timedelta(seconds=1)
        )
        coordinator.data = {"device": {}, "status": {}, "consumables": []}

        await coordinator._async_refresh_map_metadata(refresh_plans=True)

        assert coordinator.map_data is expected_map
        assert coordinator.data["map"] is expected_map
        assert coordinator.data["clean_plans"] == ()
        assert coordinator.map_updated_at is not None

    asyncio.run(run())


if __name__ == "__main__":
    test_valid_map_survives_clean_plan_failure()
    print("coordinator tests passed")
