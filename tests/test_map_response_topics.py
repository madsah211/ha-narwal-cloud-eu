"""Regression tests for Narwal map responses delivered on a live-map topic."""

from __future__ import annotations

import asyncio
import sys

from test_auth import API

MQTT = sys.modules["narwal_cloud.mqtt"]


def test_map_display_topic_is_accepted_as_alternate_response() -> None:
    expected = "/product/device/map/get_map/response"
    alternate = "/product/device/map/display_map"

    assert MQTT._is_expected_response_topic(expected, expected, alternate)
    assert MQTT._is_expected_response_topic(alternate, expected, alternate)
    assert not MQTT._is_expected_response_topic(
        "/product/device/status/working_status", expected, alternate
    )


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
                {"response_topic": "map/display_map", "payload_length": 9}
            )
            return b"not-a-map"

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
            "payload_length": 9,
            "error_type": "ValueError",
            "error": "Invalid Narwal transport marker",
        }

    asyncio.run(run())


if __name__ == "__main__":
    test_map_display_topic_is_accepted_as_alternate_response()
    test_map_request_enables_display_map_fallback()
    test_map_parse_failure_records_only_safe_metadata()
    print("map response topic tests passed")
