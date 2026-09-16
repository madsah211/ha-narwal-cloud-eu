"""Regression tests for Narwal map responses delivered on a live-map topic."""

from __future__ import annotations

import asyncio
import sys
import zlib

from test_auth import API

MQTT = sys.modules["narwal_cloud.mqtt"]
PROTOCOL = sys.modules["narwal_cloud.protocol"]


def test_map_display_topic_is_not_a_full_map_response() -> None:
    expected = "/product/device/map/get_map/response"

    assert MQTT._is_expected_response_topic(expected, expected, None)
    assert not MQTT._is_expected_response_topic(
        "/product/device/map/display_map", expected, None
    )
    assert not MQTT._is_expected_response_topic(
        "/product/device/status/working_status", expected, None
    )


def test_map_request_waits_for_get_map_response() -> None:
    async def run() -> None:
        client = API.NarwalCloudClient(object(), "access", "refresh", "client")

        async def broker_url() -> str:
            return "mqtts://eu.example.invalid:8883"

        calls: list[dict] = []

        async def request(*_args, **kwargs) -> bytes:
            calls.append(kwargs)
            map_message = (
                MQTT._protobuf_varint(1, 42)
                + MQTT._protobuf_varint(3, 50)
                + MQTT._protobuf_varint(4, 1)
                + MQTT._protobuf_varint(5, 1)
                + MQTT._protobuf_message(17, zlib.compress(b"\x00"))
            )
            response = (
                MQTT._protobuf_varint(1, 1)
                + MQTT._protobuf_message(2, map_message)
            )
            return b"\x01\x00" + response

        original_request = API.async_request
        client.async_get_broker_url = broker_url
        API.async_request = request
        try:
            await client.async_get_map("device", "product")
        finally:
            API.async_request = original_request

        assert calls[0].get("alternate_response_topic_suffix") is None

    asyncio.run(run())


def test_nested_saved_map_response_uses_field_one_as_map_id() -> None:
    compressed_grid = zlib.compress(b"\x00\x00\x00\x00")
    map_message = (
        MQTT._protobuf_varint(1, 42)
        + MQTT._protobuf_varint(3, 50)
        + MQTT._protobuf_varint(4, 2)
        + MQTT._protobuf_varint(5, 2)
        + MQTT._protobuf_message(17, compressed_grid)
    )
    response = (
        MQTT._protobuf_varint(1, 1)
        + MQTT._protobuf_message(2, MQTT._protobuf_message(2, map_message))
    )

    map_data = PROTOCOL.parse_map_response(b"\x01\x00" + response)

    assert map_data.revision == 42
    assert map_data.resolution == 50
    assert map_data.width == 2
    assert map_data.height == 2
    assert map_data.compressed_grid == compressed_grid


def test_map_parse_failure_records_only_safe_metadata() -> None:
    async def run() -> None:
        client = API.NarwalCloudClient(object(), "access", "refresh", "client")

        async def broker_url() -> str:
            return "mqtts://eu.example.invalid:8883"

        async def request(*_args, **kwargs) -> bytes:
            kwargs["response_metadata"].update(
                {"response_topic": "map/get_map/response", "payload_length": 2}
            )
            return b"\x08\x01"

        original_request = API.async_request
        client.async_get_broker_url = broker_url
        API.async_request = request
        try:
            try:
                await client.async_get_map("device", "product")
            except API.NarwalCloudError:
                pass
            else:
                raise AssertionError("Invalid map payload should fail")
        finally:
            API.async_request = original_request

        assert client.last_map_diagnostic == {
            "status": "error",
            "response_topic": "map/get_map/response",
            "payload_length": 2,
            "error_type": "ValueError",
            "error": "Invalid Narwal transport marker",
        }

    asyncio.run(run())


if __name__ == "__main__":
    test_map_display_topic_is_not_a_full_map_response()
    test_map_request_waits_for_get_map_response()
    test_nested_saved_map_response_uses_field_one_as_map_id()
    test_map_parse_failure_records_only_safe_metadata()
    print("map response topic tests passed")
