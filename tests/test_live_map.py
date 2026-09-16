"""Regression tests for app-free map wake and robot coordinates."""

from __future__ import annotations

import asyncio
import importlib.util
import struct
import sys
import zlib
from pathlib import Path

from test_auth import API

MQTT = sys.modules["narwal_cloud.mqtt"]
PROTOCOL = sys.modules["narwal_cloud.protocol"]
ROOT = Path(__file__).parents[1] / "custom_components" / "narwal_cloud"


def _load_renderer():
    spec = importlib.util.spec_from_file_location(
        "narwal_cloud.map_renderer", ROOT / "map_renderer.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RENDERER = _load_renderer()


def _fixed32(field_number: int, value: float) -> bytes:
    return MQTT._varint((field_number << 3) | 5) + struct.pack("<f", value)


def _pose(x: float, y: float, angle: float = 0.0) -> bytes:
    point = _fixed32(1, x) + _fixed32(2, y)
    return MQTT._protobuf_message(1, point) + _fixed32(2, angle)


def test_wake_subscription_names_every_broadcast_topic_for_ten_minutes() -> None:
    subscription = MQTT._wake_requests()[1][1]
    outer = PROTOCOL.decode_fields(subscription)
    entries = [
        PROTOCOL.decode_fields(bytes(field.value))
        for field in outer
        if field.number == 1 and field.wire_type == 2
    ]
    topics = [
        bytes(next(field.value for field in entry if field.number == 1)).decode()
        for entry in entries
    ]
    durations = [
        next(field.value for field in entry if field.number == 2)
        for entry in entries
    ]

    assert topics == [
        "status/robot_base_status",
        "status/working_status",
        "upgrade/upgrade_status",
        "status/download_status",
        "map/display_map",
        "status/time_line_status",
    ]
    assert durations == [600] * len(topics)


def test_saved_map_exposes_origin_offsets_for_live_overlay_coordinates() -> None:
    border = (
        MQTT._protobuf_varint(1, 200)
        + MQTT._protobuf_varint(2, 0)
        + MQTT._protobuf_varint(3, 100)
        + MQTT._protobuf_varint(4, 50)
    )
    map_message = (
        MQTT._protobuf_varint(1, 42)
        + MQTT._protobuf_varint(3, 50)
        + MQTT._protobuf_varint(4, 20)
        + MQTT._protobuf_varint(5, 30)
        + MQTT._protobuf_message(6, border)
        + MQTT._protobuf_message(8, _pose(104.0, 206.0))
        + MQTT._protobuf_message(24, _pose(109.0, 211.0, 1.0))
        + MQTT._protobuf_message(17, zlib.compress(b"\x00" * 600))
    )
    response = MQTT._protobuf_varint(1, 1) + MQTT._protobuf_message(2, map_message)

    map_data = PROTOCOL.parse_map_response(b"\x01\x00" + response)

    assert map_data.origin_x == 100
    assert map_data.origin_y == 200
    assert map_data.station is not None
    assert map_data.robot_pose is not None
    assert map_data.robot_pose.x - map_data.origin_x == 9.0
    assert map_data.robot_pose.y - map_data.origin_y == 11.0


def test_renderer_places_robot_by_subtracting_saved_map_origin() -> None:
    map_data = PROTOCOL.NarwalMap(
        width=20,
        height=30,
        resolution=50,
        origin_x=100,
        origin_y=200,
        robot_pose=PROTOCOL.NarwalPose(x=109.0, y=211.0, angle=1.0),
    )

    assert RENDERER._pose_pixel(map_data) == (9.0, 11.0)


def test_display_map_updates_pose_timestamp_and_native_trajectory() -> None:
    trajectory = (
        MQTT._protobuf_message(1, struct.pack("<ff", 101.0, 102.0))
        + MQTT._protobuf_message(2, struct.pack("<ff", 201.0, 202.0))
    )
    payload = (
        MQTT._protobuf_message(1, _pose(109.0, 211.0, 1.0))
        + MQTT._protobuf_message(2, trajectory)
        + MQTT._protobuf_varint(10, 1_700_000_000_000)
    )
    base = PROTOCOL.NarwalMap(
        revision=42,
        width=20,
        height=30,
        origin_x=100,
        origin_y=200,
        compressed_grid=b"grid",
    )

    display = PROTOCOL.parse_display_map(payload)
    merged = PROTOCOL.merge_display_map(base, display)

    assert merged.robot_pose == PROTOCOL.NarwalPose(109.0, 211.0, 1.0)
    assert merged.robot_pose_update_time == 1_700_000_000_000
    assert merged.trajectory == ((101.0, 201.0), (102.0, 202.0))
    assert merged.compressed_grid == b"grid"
    assert RENDERER._pose_pixel(merged) == (9.0, 11.0)
    assert RENDERER._trajectory_pixels(merged) == [(3.0, 3.0), (6.0, 6.0)]


def test_saved_map_cache_round_trip_preserves_private_map_only_locally() -> None:
    original = PROTOCOL.NarwalMap(
        revision=42,
        resolution=50,
        width=2,
        height=3,
        rooms=(PROTOCOL.NarwalRoom(4, "Kitchen", 4, 1),),
        compressed_grid=b"compressed-grid",
        border=(1, 2, 3, 4),
        origin_x=3,
        origin_y=1,
        station=PROTOCOL.NarwalPose(5.0, 6.0, 0.5),
        robot_pose=PROTOCOL.NarwalPose(7.0, 8.0, 1.0),
        robot_pose_update_time=123456,
    )

    restored = PROTOCOL.map_from_cache(PROTOCOL.map_to_cache(original))

    assert restored == original


def test_base_status_request_also_keeps_latest_display_map() -> None:
    async def run() -> None:
        client = API.NarwalCloudClient(object(), "access", "refresh", "client")
        base_payload = _fixed32(2, 80.0)
        display_payload = (
            MQTT._protobuf_message(1, _pose(109.0, 211.0, 1.0))
            + MQTT._protobuf_varint(10, 1_700_000_000_000)
        )

        async def broker_url() -> str:
            return "mqtts://eu.example.invalid:8883"

        async def request(*_args, **_kwargs):
            return base_payload, display_payload

        original = API.async_request_base_status
        client.async_get_broker_url = broker_url
        API.async_request_base_status = request
        try:
            status = await client.async_get_base_status(
                "device", "product", capture_display=True
            )
        finally:
            API.async_request_base_status = original

        assert status == {"battery_percentage": 80}
        assert client.last_display_map is not None
        assert client.last_display_map.robot_pose == PROTOCOL.NarwalPose(
            109.0, 211.0, 1.0
        )

    asyncio.run(run())


if __name__ == "__main__":
    test_wake_subscription_names_every_broadcast_topic_for_ten_minutes()
    test_saved_map_exposes_origin_offsets_for_live_overlay_coordinates()
    test_renderer_places_robot_by_subtracting_saved_map_origin()
    test_display_map_updates_pose_timestamp_and_native_trajectory()
    test_saved_map_cache_round_trip_preserves_private_map_only_locally()
    test_base_status_request_also_keeps_latest_display_map()
    print("live map foundation tests passed")
