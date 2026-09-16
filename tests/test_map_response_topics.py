"""Regression tests for Narwal map responses delivered on a live-map topic."""

from __future__ import annotations

import asyncio
import sys
import zlib

from test_auth import API

MQTT = sys.modules["narwal_cloud.mqtt"]
PROTOCOL = sys.modules["narwal_cloud.protocol"]


def test_map_display_topic_is_accepted_as_alternate_response() -> None:
    expected = "/product/device/map/get_map/response"
    alternate = "/product/device/map/display_map"

    assert MQTT._is_expected_response_topic(expected, expected, alternate)
    assert MQTT._is_expected_response_topic(alternate, expected, alternate)
    assert not MQTT._is_expected_response_topic(
        "/product/device/status/working_status", expected, alternate
    )


def test_direct_display_map_payload_is_parsed_without_transport_wrapper() -> None:
    payload = (
        MQTT._protobuf_varint(2, 7)
        + MQTT._protobuf_varint(3, 50)
        + MQTT._protobuf_varint(4, 2)
        + MQTT._protobuf_varint(5, 2)
        + MQTT._protobuf_message(17, zlib.compress(b"\x00\x00\x00\x00"))
    )

    map_data = PROTOCOL.parse_map_display(payload)

    assert map_data.revision == 7
    assert map_data.resolution == 50
    assert map_data.width == 2
    assert map_data.height == 2
    assert map_data.compressed_grid


def test_map_request_enables_display_map_fallback() -> None:
    async def run() -> None:
        client = API.NarwalCloudClient(object(), "access", "refresh", "client")

        async def broker_url() -> str:
            return "mqtts://eu.example.invalid:8883"

        calls: list[dict] = []

        async def request(*_args, **kwargs) -> bytes:
            calls.append(kwargs)
            # Transport marker + empty common header + successful empty map.
            return b"\x01\x00\x08\x01\x12\x00"

        original_request = API.async_request
        client.async_get_broker_url = broker_url
        API.async_request = request
        try:
            await client.async_get_map("device", "product")
        finally:
            API.async_request = original_request

        assert calls[0]["alternate_response_topic_suffix"] == "map/display_map"

    asyncio.run(run())


def test_map_parse_failure_records_only_safe_metadata() -> None:
    async def run() -> None:
        client = API.NarwalCloudClient(object(), "access", "refresh", "client")

        async def broker_url() -> str:
            return "mqtts://eu.example.invalid:8883"

        async def request(*_args, **kwargs) -> bytes:
            kwargs["response_metadata"].update(
                {"response_topic": "map/display_map", "payload_length": 2}
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
            "response_topic": "map/display_map",
            "payload_length": 2,
            "protobuf_fields": ["1:0"],
            "error_type": "ValueError",
            "error": "Unsupported display-map protobuf shape",
        }

    asyncio.run(run())


if __name__ == "__main__":
    test_map_display_topic_is_accepted_as_alternate_response()
    test_direct_display_map_payload_is_parsed_without_transport_wrapper()
    test_map_request_enables_display_map_fallback()
    test_map_parse_failure_records_only_safe_metadata()
    print("map response topic tests passed")
