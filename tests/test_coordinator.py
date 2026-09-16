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
    storage = types.ModuleType("homeassistant.helpers.storage")
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

    class Store:
        def __init__(self, *_args, **_kwargs):
            self.saved = None

        async def async_load(self):
            return self.saved

        async def async_save(self, value):
            self.saved = value

    storage.Store = Store
    sys.modules.update(
        {
            "homeassistant": homeassistant,
            "homeassistant.exceptions": exceptions,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.storage": storage,
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


def test_cached_map_restores_before_sleeping_robot_answers() -> None:
    async def run() -> None:
        expected_map = PROTOCOL.NarwalMap(
            revision=42,
            resolution=50,
            width=2,
            height=2,
            compressed_grid=b"grid",
        )

        class Store:
            async def async_load(self):
                return PROTOCOL.map_to_cache(expected_map)

        coordinator = COORDINATOR.NarwalCloudCoordinator(
            object(), object(), "device", "product", timedelta(seconds=1)
        )
        coordinator._map_store = Store()

        await coordinator.async_restore_cached_map()

        assert coordinator.map_data == expected_map
        assert coordinator.map_updated_at is not None

    asyncio.run(run())


def test_successful_map_refresh_is_saved_for_next_restart() -> None:
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
                return ()

        class Store:
            saved = None

            async def async_save(self, value):
                self.saved = value

        coordinator = COORDINATOR.NarwalCloudCoordinator(
            object(), Client(), "device", "product", timedelta(seconds=1)
        )
        coordinator._map_store = Store()

        await coordinator._async_refresh_map_metadata(refresh_plans=False)

        assert PROTOCOL.map_from_cache(coordinator._map_store.saved) == expected_map

    asyncio.run(run())


def test_live_display_map_is_merged_into_cached_saved_map() -> None:
    async def run() -> None:
        display = PROTOCOL.NarwalDisplayMap(
            robot_pose=PROTOCOL.NarwalPose(109.0, 211.0, 1.0),
            timestamp=1_700_000_000_000,
            trajectory=((101.0, 201.0), (102.0, 202.0)),
        )

        class Client:
            last_display_map = None

            async def async_get_base_status(
                self, _device_id, _product_id, *, capture_display=False
            ):
                assert capture_display
                self.last_display_map = display
                return {"battery_percentage": 80}

        coordinator = COORDINATOR.NarwalCloudCoordinator(
            object(), Client(), "device", "product", timedelta(seconds=1)
        )
        coordinator.map_data = PROTOCOL.NarwalMap(
            revision=42,
            width=20,
            height=30,
            origin_x=100,
            origin_y=200,
            compressed_grid=b"grid",
        )
        coordinator.data = {"device": {}, "status": {}, "consumables": []}

        result = await coordinator._async_get_base_status(capture_display=True)

        assert result == {"battery_percentage": 80}
        assert coordinator.map_data.robot_pose == display.robot_pose
        assert coordinator.map_data.trajectory == display.trajectory
        assert coordinator.data["map"] is coordinator.map_data

    asyncio.run(run())


if __name__ == "__main__":
    test_valid_map_survives_clean_plan_failure()
    test_cached_map_restores_before_sleeping_robot_answers()
    test_successful_map_refresh_is_saved_for_next_restart()
    test_live_display_map_is_merged_into_cached_saved_map()
    print("coordinator tests passed")
