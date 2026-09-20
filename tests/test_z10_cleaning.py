"""Regression tests for model-specific Freo Z10 cleaning commands."""

from __future__ import annotations

import asyncio
import sys

from test_auth import API

MQTT = sys.modules["narwal_cloud.mqtt"]
PROTOCOL = sys.modules["narwal_cloud.protocol"]
Z10_PRODUCT_ID = "OlkUn3oUCu"
REPORTED_Z10_PRODUCT_ID = "tPQJmoIbEC"


def _framed_response(body: bytes, header: bytes = b"") -> bytes:
    return b"\x01" + MQTT._varint(len(header)) + header + body


def _integer(fields, number: int) -> int:
    for field in fields:
        if field.number == number and field.wire_type == 0:
            return int(field.value)
    return 0


def _messages(fields, number: int) -> list[bytes]:
    return [
        bytes(field.value)
        for field in fields
        if field.number == number and field.wire_type == 2
    ]


def test_yjcc012_easy_clean_payload_remains_byte_identical() -> None:
    body = MQTT._easy_clean_body(
        [4], mode=4, suction=2, humidity=2, cycles=1
    )
    assert body.hex() == "080410011a0e0804100132080802100118022001"


def test_z10_start_clean_payload_carries_map_rooms_and_settings() -> None:
    body = MQTT._start_clean_body(
        [10, 1], map_id=42, mode=4, suction=3, humidity=2, cycles=2
    )
    assert body.hex() == (
        "0a32082a12140a040801100a120a080410031801200238021801"
        "12140a0408011001120a0804100318012002380218021a002804"
    )

    outer = PROTOCOL.decode_fields(body)
    task = PROTOCOL.decode_fields(_messages(outer, 1)[0])
    assert _integer(task, 1) == 42
    assert _integer(task, 5) == 4

    items = [PROTOCOL.decode_fields(raw) for raw in _messages(task, 2)]
    assert len(items) == 2
    assert [_integer(item, 3) for item in items] == [1, 2]

    zones = [PROTOCOL.decode_fields(_messages(item, 1)[0]) for item in items]
    assert [_integer(zone, 1) for zone in zones] == [1, 1]
    assert [_integer(zone, 2) for zone in zones] == [10, 1]

    params = [PROTOCOL.decode_fields(_messages(item, 2)[0]) for item in items]
    for param in params:
        assert _integer(param, 1) == 4
        assert _integer(param, 2) == 3
        assert _integer(param, 3) == 1
        assert _integer(param, 4) == 2
        assert _integer(param, 7) == 2


def test_z10_uses_start_clean_while_yjcc012_keeps_easy_clean() -> None:
    async def run() -> None:
        calls = []
        original_request = MQTT.async_request

        async def request(*args, **kwargs):
            calls.append((args, kwargs))
            return _framed_response(b"\x08\x01")

        try:
            MQTT.async_request = request
            await MQTT.async_publish_task_command(
                "mqtts://eu.example.invalid:8883",
                "access",
                "client",
                Z10_PRODUCT_ID,
                "z10-device",
                "easy_clean_start",
                [10, 1],
                map_id=42,
                mode=4,
                suction=3,
                humidity=2,
                cycles=2,
            )
            await MQTT.async_publish_task_command(
                "mqtts://eu.example.invalid:8883",
                "access",
                "client",
                "YJCC012",
                "yjcc-device",
                "easy_clean_start",
                [4],
                map_id=42,
                mode=4,
                response_required=False,
            )
        finally:
            MQTT.async_request = original_request

        assert calls[0][0][5] == "clean/start_clean"
        assert calls[0][1]["response_required"] is True
        assert calls[1][0][5] == "clean/easy_clean/start"
        assert calls[1][1]["response_required"] is False

    asyncio.run(run())


def test_reported_plain_z10_routes_only_manual_modes_to_start_clean() -> None:
    async def run() -> None:
        calls = []
        original_request = MQTT.async_request

        async def request(*args, **kwargs):
            calls.append((args, kwargs))
            return _framed_response(b"\x08\x01")

        try:
            MQTT.async_request = request
            for mode in range(2, 6):
                await MQTT.async_publish_task_command(
                    "mqtts://eu.example.invalid:8883",
                    "access",
                    "client",
                    REPORTED_Z10_PRODUCT_ID,
                    "z10-device",
                    "easy_clean_start",
                    [10, 1],
                    map_id=1,
                    mode=mode,
                )
            await MQTT.async_publish_task_command(
                "mqtts://eu.example.invalid:8883",
                "access",
                "client",
                REPORTED_Z10_PRODUCT_ID,
                "z10-device",
                "easy_clean_start",
                [10],
                map_id=1,
                mode=1,
                room_templates={10: b"\x08\x0a"},
                response_required=False,
            )
        finally:
            MQTT.async_request = original_request

        assert [call[0][5] for call in calls[:4]] == ["clean/start_clean"] * 4
        assert all(call[1]["response_required"] is True for call in calls[:4])
        assert calls[4][0][5] == "clean/easy_clean/start"
        assert calls[4][1]["response_required"] is False
        assert not MQTT.uses_start_clean(REPORTED_Z10_PRODUCT_ID, 0)
        assert not MQTT.uses_start_clean(REPORTED_Z10_PRODUCT_ID, 6)

    asyncio.run(run())


def test_task_diagnostics_show_route_without_device_identity() -> None:
    async def run() -> None:
        calls = []
        transport_calls = []

        class RecordingLogger:
            def debug(self, message, *args) -> None:
                calls.append(message % args)

        async def request(*args, **kwargs):
            transport_calls.append((args, kwargs))
            return b""

        original_logger = MQTT._LOGGER
        original_request = MQTT.async_request
        MQTT._LOGGER = RecordingLogger()
        MQTT.async_request = request
        try:
            await MQTT.async_publish_task_command(
                "mqtts://private-broker.example.invalid:8883",
                "private-access-token",
                "private-client-id",
                "unexpected-z10-product",
                "private-device-id",
                "easy_clean_start",
                [10],
                map_id=42,
                mode=2,
                room_templates={10: b"private-template-marker"},
                response_required=False,
            )
            await MQTT.async_publish_task_command(
                "mqtts://private-broker.example.invalid:8883",
                "private-access-token",
                "private-client-id",
                "unexpected-z10-product",
                "private-device-id",
                "recall",
                map_id=42,
                mode=2,
                response_required=False,
            )
        finally:
            MQTT._LOGGER = original_logger
            MQTT.async_request = original_request

        rendered = "\n".join(calls)
        assert "product_id=unexpected-z10-product" in rendered
        assert "action=easy_clean_start" in rendered
        assert "mode=2" in rendered
        assert "map_id=42" in rendered
        assert "topic=clean/easy_clean/start" in rendered
        assert "topic=supply/recall" in rendered
        assert "response_required=False" in rendered
        assert "Narwal task completed" in rendered
        assert transport_calls[1][0][5] == "supply/recall"
        assert transport_calls[1][0][6] == b""
        assert transport_calls[1][1]["response_required"] is False
        for private_value in (
            "private-device-id",
            "private-access-token",
            "private-client-id",
            "private-broker",
            "private-template-marker",
        ):
            assert private_value not in rendered

    asyncio.run(run())


def test_z10_start_clean_requires_current_map_id() -> None:
    try:
        MQTT._start_clean_body([1], map_id=0, mode=2)
    except ValueError as err:
        assert "map" in str(err).lower()
    else:
        raise AssertionError("Z10 cleaning accepted a missing map id")


def test_z10_start_clean_rejects_negative_acknowledgement() -> None:
    async def run() -> None:
        async def request(*_args, **_kwargs):
            return _framed_response(b"\x08\x02")

        original_request = MQTT.async_request
        MQTT.async_request = request
        try:
            try:
                await MQTT.async_publish_task_command(
                    "mqtts://eu.example.invalid:8883",
                    "access",
                    "client",
                    Z10_PRODUCT_ID,
                    "z10-device",
                    "easy_clean_start",
                    [1],
                    map_id=42,
                    mode=2,
                )
            except MQTT.NarwalMqttError as err:
                assert "result code 2" in str(err)
            else:
                raise AssertionError("Z10 rejection was reported as success")
        finally:
            MQTT.async_request = original_request

    asyncio.run(run())


def test_z10_mode_one_refuses_incomplete_templates_before_publish() -> None:
    async def run() -> None:
        called = False

        async def request(*_args, **_kwargs):
            nonlocal called
            called = True
            return _framed_response(b"\x08\x01")

        original_request = MQTT.async_request
        MQTT.async_request = request
        try:
            try:
                await MQTT.async_publish_task_command(
                    "mqtts://eu.example.invalid:8883",
                    "access",
                    "client",
                    Z10_PRODUCT_ID,
                    "z10-device",
                    "easy_clean_start",
                    [1, 10],
                    map_id=42,
                    mode=1,
                    room_templates={1: b"\x08\x01"},
                    response_required=False,
                )
            except ValueError as err:
                assert "template" in str(err).lower()
            else:
                raise AssertionError("Incomplete Z10 Freo templates were accepted")
            assert called is False
        finally:
            MQTT.async_request = original_request

    asyncio.run(run())


def test_z10_response_transport_is_parsed_structurally() -> None:
    MQTT._validate_command_response(_framed_response(b"\x08\x01"))

    misleading_header = b"\x08\x01" + (b"x" * 128)
    try:
        MQTT._validate_command_response(
            _framed_response(b"\x08\x02", misleading_header)
        )
    except MQTT.NarwalMqttError as err:
        assert "result code 2" in str(err)
    else:
        raise AssertionError("Transport header was mistaken for command success")

    for malformed in (b"\x01\x80", _framed_response(b"\x08\x01\x00")):
        try:
            MQTT._validate_command_response(malformed)
        except MQTT.NarwalMqttError as err:
            assert "malformed" in str(err)
        else:
            raise AssertionError("Malformed Z10 response was accepted")


def test_z10_mode_one_keeps_legacy_no_wait_behavior() -> None:
    async def run() -> None:
        calls = []

        async def publish(*args, **kwargs):
            calls.append((args, kwargs))

        original_publish = API.async_publish_task_command
        API.async_publish_task_command = publish
        client = API.NarwalCloudClient(object(), "access", "refresh", "client")

        async def broker_url():
            return "mqtts://eu.example.invalid:8883"

        client.async_get_broker_url = broker_url
        try:
            await client.async_send_task_command(
                "device",
                Z10_PRODUCT_ID,
                "easy_clean_start",
                [1],
                map_id=42,
                mode=1,
                room_templates={1: b"\x08\x01"},
            )
        finally:
            API.async_publish_task_command = original_publish

        assert calls[0][1]["response_required"] is False

    asyncio.run(run())


def test_api_wraps_z10_payload_validation_error() -> None:
    async def run() -> None:
        async def invalid_publish(*_args, **_kwargs):
            raise ValueError("missing map")

        original_publish = API.async_publish_task_command
        API.async_publish_task_command = invalid_publish
        client = API.NarwalCloudClient(object(), "access", "refresh", "client")

        async def broker_url():
            return "mqtts://eu.example.invalid:8883"

        client.async_get_broker_url = broker_url
        try:
            try:
                await client.async_send_task_command(
                    "device",
                    Z10_PRODUCT_ID,
                    "easy_clean_start",
                    [1],
                    map_id=0,
                    mode=2,
                )
            except API.NarwalCloudError as err:
                assert "missing map" in str(err)
            else:
                raise AssertionError("Raw Z10 validation error escaped the API")
        finally:
            API.async_publish_task_command = original_publish

    asyncio.run(run())


if __name__ == "__main__":
    test_yjcc012_easy_clean_payload_remains_byte_identical()
    test_z10_start_clean_payload_carries_map_rooms_and_settings()
    test_z10_uses_start_clean_while_yjcc012_keeps_easy_clean()
    test_reported_plain_z10_routes_only_manual_modes_to_start_clean()
    test_task_diagnostics_show_route_without_device_identity()
    test_z10_start_clean_requires_current_map_id()
    test_z10_start_clean_rejects_negative_acknowledgement()
    test_z10_mode_one_refuses_incomplete_templates_before_publish()
    test_z10_response_transport_is_parsed_structurally()
    test_z10_mode_one_keeps_legacy_no_wait_behavior()
    test_api_wraps_z10_payload_validation_error()
    print("Z10 cleaning tests passed")
