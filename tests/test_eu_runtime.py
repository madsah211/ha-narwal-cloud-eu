"""Request-level regression tests for the private EU runtime flow."""

from __future__ import annotations

import asyncio

from test_auth import API


class _Response:
    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    async def json(self, **_kwargs):
        return self._payload


class _Session:
    def __init__(self, *, request_responses=None, post_responses=None):
        self.request_responses = list(request_responses or [])
        self.post_responses = list(post_responses or [])
        self.request_calls = []
        self.post_calls = []

    def request(self, *args, **kwargs):
        self.request_calls.append((args, kwargs))
        return self.request_responses.pop(0)

    def post(self, *args, **kwargs):
        self.post_calls.append((args, kwargs))
        return self.post_responses.pop(0)


def test_refresh_uses_eu_endpoint_and_rotates_tokens() -> None:
    async def run() -> None:
        session = _Session(
            post_responses=[
                _Response({"result": {"token": "new-access", "refreshToken": "new-refresh"}})
            ]
        )
        stored = []

        async def save(access_token, refresh_token):
            stored.append((access_token, refresh_token))

        client = API.NarwalCloudClient(
            session, "old-access", "old-refresh", "client", save
        )
        await client.async_refresh_token()

        args, kwargs = session.post_calls[0]
        assert args[0] == (
            "https://eu-app.narwaltech.com/"
            "user-authentication-server/v1/token/refresh"
        )
        assert kwargs["headers"]["country_code"] == "DK"
        assert kwargs["json"] == {"refreshToken": "old-refresh"}
        assert client.access_token == "new-access"
        assert client.refresh_token == "new-refresh"
        assert stored == [("new-access", "new-refresh")]

    asyncio.run(run())


def test_device_lookup_uses_eu_endpoint() -> None:
    async def run() -> None:
        session = _Session(
            request_responses=[
                _Response(
                    {
                        "result": {
                            "deviceInfoList": [
                                {"deviceId": "robot", "productId": "product"}
                            ]
                        }
                    }
                )
            ]
        )
        client = API.NarwalCloudClient(session, "access", "refresh", "client")
        devices = await client.async_get_devices()

        args, kwargs = session.request_calls[0]
        assert args == (
            "GET",
            (
                "https://eu-app.narwaltech.com/"
                "user-device-platform-server/device-info/getDeviceInfoList"
            ),
        )
        assert kwargs["headers"]["country_code"] == "DK"
        assert devices == [{"deviceId": "robot", "productId": "product"}]

    asyncio.run(run())


def test_broker_discovery_uses_denmark() -> None:
    async def run() -> None:
        session = _Session(
            request_responses=[
                _Response({"result": "mqtts://eu-01.mqtt.narwaltech.com:8883"})
            ]
        )
        client = API.NarwalCloudClient(session, "access", "refresh", "client")
        broker = await client.async_get_broker_url()

        args, kwargs = session.request_calls[0]
        assert args == (
            "GET",
            (
                "https://eu-app.narwaltech.com/"
                "iot-broker-discover/app/v1/broker/discover"
            ),
        )
        assert kwargs["params"] == {"country": "DK"}
        assert kwargs["headers"]["country_code"] == "DK"
        assert broker == "mqtts://eu-01.mqtt.narwaltech.com:8883"

    asyncio.run(run())


def test_unauthorized_request_refreshes_and_retries_on_eu() -> None:
    async def run() -> None:
        session = _Session(
            request_responses=[
                _Response({}, status=401),
                _Response({"result": {"deviceInfoList": []}}),
            ],
            post_responses=[
                _Response({"result": {"token": "new-access", "refreshToken": "new-refresh"}})
            ],
        )
        client = API.NarwalCloudClient(
            session, "old-access", "old-refresh", "client"
        )
        assert await client.async_get_devices() == []
        assert len(session.request_calls) == 2
        assert session.request_calls[0][1]["headers"]["auth-token"] == "old-access"
        assert session.request_calls[1][1]["headers"]["auth-token"] == "new-access"
        assert session.post_calls[0][0][0].startswith("https://eu-app.narwaltech.com/")

    asyncio.run(run())


if __name__ == "__main__":
    test_refresh_uses_eu_endpoint_and_rotates_tokens()
    test_device_lookup_uses_eu_endpoint()
    test_broker_discovery_uses_denmark()
    test_unauthorized_request_refreshes_and_retries_on_eu()
    print("EU runtime tests passed")
