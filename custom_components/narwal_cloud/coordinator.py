"""Data coordinator for Narwal Cloud."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NarwalCloudAuthError, NarwalCloudClient, NarwalCloudError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, Z10_PRODUCT_IDS
from .protocol import (
    NarwalCleanPlan,
    NarwalMap,
    clean_plans_from_cache,
    clean_plans_to_cache,
    map_from_cache,
    map_to_cache,
    merge_display_map,
)

MAP_REFRESH_INTERVAL = timedelta(minutes=5)
MAP_CACHE_VERSION = 1
_LOGGER = logging.getLogger(__name__)


def _plan_map_signature(map_data: NarwalMap) -> tuple:
    """Return the map fields that make per-room templates safe to reuse."""
    return (
        map_data.revision,
        tuple(
            sorted(
                (
                    room.room_id,
                    room.name,
                    room.room_type,
                    room.instance_index,
                )
                for room in map_data.rooms
            )
        ),
    )


def _freo_plan_covers_map(
    plans: tuple[NarwalCleanPlan, ...], map_data: NarwalMap
) -> bool:
    """Return whether Freo Mind has a template for every current room."""
    room_ids = {room.room_id for room in map_data.rooms}
    if not room_ids:
        return True
    freo_plan = next((plan for plan in plans if plan.mode == 1), None)
    return freo_plan is not None and room_ids <= set(freo_plan.room_templates)


class NarwalCloudCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the exact state endpoint used by the official Narwal app."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NarwalCloudClient,
        device_id: str,
        product_id: str,
        scan_interval: timedelta = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=scan_interval,
        )
        self.client = client
        self.device_id = device_id
        self.product_id = product_id
        self.map_data = NarwalMap()
        self._map_store = Store(
            hass,
            MAP_CACHE_VERSION,
            f"{DOMAIN}.{device_id}.map",
        )
        self.clean_plans: tuple[NarwalCleanPlan, ...] = ()
        self._map_updated_at: datetime | None = None
        self._map_attempted_at: datetime | None = None
        self._map_refresh_task: asyncio.Task[None] | None = None
        self.cleaning_mode = 1
        self.suction_power = 2
        self.mop_humidity = 2
        self.cleaning_cycles = 1

    async def async_restore_cached_map(self) -> None:
        """Restore the last valid map and plans before contacting the robot."""
        cached = await self._map_store.async_load()
        if cached is None:
            return
        try:
            # eu.9 stored a bare map. Keep it readable, but do not invent
            # cleaning plans that were never persisted.
            bundled = isinstance(cached, dict) and "map" in cached
            map_data = map_from_cache(cached["map"] if bundled else cached)
            clean_plans = (
                clean_plans_from_cache(cached.get("clean_plans", []))
                if bundled
                else ()
            )
        except (KeyError, TypeError, ValueError):
            _LOGGER.warning("Ignoring an invalid cached Narwal map")
            return
        if not map_data.compressed_grid or map_data.width <= 0 or map_data.height <= 0:
            return
        self.map_data = map_data
        self.clean_plans = (
            clean_plans
            if self.product_id not in Z10_PRODUCT_IDS
            or _freo_plan_covers_map(clean_plans, map_data)
            else ()
        )
        self._map_updated_at = datetime.now().astimezone()

    async def _async_save_map_cache(self) -> None:
        """Persist map and cleaning plans as one coherent cache snapshot."""
        await self._map_store.async_save(
            {
                "map": map_to_cache(self.map_data),
                "clean_plans": clean_plans_to_cache(self.clean_plans),
            }
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            device, status = await asyncio.gather(
                self.client.async_get_device_info(self.device_id, self.product_id),
                self.client.async_get_work_status(self.device_id, self.product_id),
            )
            # Narwal intermittently returns malformed consumable data when
            # broker discovery and consumable REST calls overlap. Keep these
            # optional reads sequential so one feature cannot block setup.
            capture_display = not bool(status.get("free")) and not bool(
                status.get("in_station")
            )
            base_status = await self._async_get_base_status(
                capture_display=capture_display
            )
            consumables = await self._async_get_consumables()
            status = {**status, **base_status}
            now = datetime.now().astimezone()
            last_map_activity = self._map_updated_at or self._map_attempted_at
            if (
                last_map_activity is None
                or now - last_map_activity >= MAP_REFRESH_INTERVAL
            ) and (
                self._map_refresh_task is None
                or self._map_refresh_task.done()
            ):
                # Map data is optional and its sleeping-robot handshake can
                # take several seconds. Never hold up HA startup or the
                # primary vacuum state while it refreshes.
                self._map_refresh_task = asyncio.create_task(
                    self._async_refresh_map_metadata(),
                    name=f"{DOMAIN}-map-refresh",
                )
        except NarwalCloudAuthError as err:
            raise ConfigEntryAuthFailed from err
        except NarwalCloudError as err:
            raise UpdateFailed(str(err)) from err
        return {
            "device": device,
            "status": status,
            "map": self.map_data,
            "clean_plans": self.clean_plans,
            "consumables": consumables,
        }

    async def _async_get_base_status(
        self, *, capture_display: bool = False
    ) -> dict[str, int]:
        """Read optional live battery data without failing core polling."""
        try:
            status = await self.client.async_get_base_status(
                self.device_id,
                self.product_id,
                capture_display=capture_display,
            )
            display = self.client.last_display_map if capture_display else None
            if display is not None and self.map_data.compressed_grid:
                self.map_data = merge_display_map(self.map_data, display)
                self._map_updated_at = datetime.now().astimezone()
                if self.data is not None:
                    self.async_set_updated_data(
                        {
                            **self.data,
                            "map": self.map_data,
                            "clean_plans": self.clean_plans,
                        }
                    )
            return status
        except NarwalCloudError:
            _LOGGER.warning(
                "Unable to refresh Narwal battery status",
                exc_info=True,
            )
            return {}

    async def _async_get_consumables(self) -> list[dict[str, Any]]:
        """Read optional consumables without failing integration setup."""
        try:
            return await self.client.async_get_consumables(
                self.device_id, self.product_id
            )
        except NarwalCloudError:
            _LOGGER.warning(
                "Unable to refresh Narwal consumable data",
                exc_info=True,
            )
            if self.data is not None:
                return list(self.data.get("consumables", []))
            return []

    async def _async_refresh_map_metadata(
        self, refresh_plans: bool = True
    ) -> None:
        """Refresh live map data without blocking core device polling."""
        self._map_attempted_at = datetime.now().astimezone()
        try:
            map_data = await self.client.async_get_map(
                self.device_id, self.product_id
            )
        except NarwalCloudError:
            _LOGGER.debug("Narwal map is temporarily unavailable", exc_info=True)
            return

        # Publish a valid saved map immediately. Cleaning-plan metadata is a
        # separate optional request and must never discard a map already read.
        previous_map = self.map_data
        previous_plans = self.clean_plans
        map_changed = bool(
            previous_map.compressed_grid
            and _plan_map_signature(previous_map) != _plan_map_signature(map_data)
        )
        is_z10 = self.product_id in Z10_PRODUCT_IDS
        reusable_plans = (
            previous_plans
            if is_z10
            and not map_changed
            and _freo_plan_covers_map(previous_plans, map_data)
            else ()
        )
        self.map_data = map_data
        if map_changed:
            self.clean_plans = ()
        self._map_updated_at = datetime.now().astimezone()
        if self.data is not None:
            self.async_set_updated_data(
                {
                    **self.data,
                    "map": self.map_data,
                    "clean_plans": self.clean_plans,
                }
            )
        try:
            # These requests use the same MQTT client id, so they must remain
            # sequential or the broker disconnects the first session.
            clean_plans = self.clean_plans
            if refresh_plans or not clean_plans:
                clean_plans = await self.client.async_get_clean_plans(
                    self.device_id, self.product_id
                )
                if is_z10 and not _freo_plan_covers_map(clean_plans, map_data):
                    # A map split can race Narwal's plan regeneration. Repeat the
                    # full activated plan read once and never cache a partial set.
                    clean_plans = await self.client.async_get_clean_plans(
                        self.device_id, self.product_id
                    )
            self.clean_plans = (
                clean_plans
                if not is_z10 or _freo_plan_covers_map(clean_plans, map_data)
                else reusable_plans
            )
            if self.data is not None:
                self.async_set_updated_data(
                    {
                        **self.data,
                        "map": self.map_data,
                        "clean_plans": self.clean_plans,
                    }
                )
        except NarwalCloudError:
            _LOGGER.debug(
                "Narwal cleaning plans are temporarily unavailable",
                exc_info=True,
            )
        await self._async_save_map_cache()

    @property
    def map_updated_at(self) -> datetime | None:
        """Return the time the latest cloud map completed loading."""
        return self._map_updated_at

    def async_request_map_refresh(self) -> None:
        """Schedule a map refresh without blocking a camera request."""
        if self._map_refresh_task is None or self._map_refresh_task.done():
            self._map_refresh_task = self.hass.async_create_task(
                self._async_refresh_map_metadata(refresh_plans=False),
                name=f"{DOMAIN}-map-camera-refresh",
            )

    async def async_refresh_rooms(self) -> None:
        """Refresh map rooms and official per-room cleaning templates."""
        if self._map_refresh_task is not None and not self._map_refresh_task.done():
            await self._map_refresh_task
            if self.clean_plans:
                return
        await self._async_refresh_map_metadata(refresh_plans=True)

    async def async_require_room_templates(
        self, mode: int, room_ids: list[int]
    ) -> dict[int, bytes]:
        """Return safe room templates or refuse an ambiguous Freo command."""
        templates = self.room_templates_for_mode(mode)
        if mode != 1:
            return templates
        missing = [room_id for room_id in room_ids if room_id not in templates]
        if missing:
            await self.async_refresh_rooms()
            templates = self.room_templates_for_mode(mode)
            missing = [room_id for room_id in room_ids if room_id not in templates]
        if missing:
            raise ValueError(
                "Narwal room template unavailable; room cleaning was not started"
            )
        return templates

    def room_templates_for_mode(self, mode: int) -> dict[int, bytes]:
        """Return exact official room templates for a cleaning mode."""
        plan = next((plan for plan in self.clean_plans if plan.mode == mode), None)
        return dict(plan.room_templates) if plan is not None else {}
