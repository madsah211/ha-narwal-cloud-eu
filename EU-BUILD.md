# Narwal Cloud EU build

This repository is an EU/Denmark adaptation of
[`mk0000001/ha-narwal-cloud`](https://github.com/mk0000001/ha-narwal-cloud):

- Upstream version: `v0.9.2`
- Upstream commit: `e773f8fcfae84c3c68eb4626f71fa2f855f8c60a`
- EU build version: `0.9.3-eu.1`

## Scope

The upstream release is configured for Narwal's Korean cloud endpoint and the
`KR` country code. This build changes only the regional authentication and
broker-discovery path required by a Narwal account whose app region is
**Denmark**:

- REST API: `https://eu-app.narwaltech.com`
- Request country code: `DK`
- MQTT broker discovery country: `DK`
- EU login payload: `email` and `password` transported over verified HTTPS
- Display name: `Narwal Cloud EU (unofficial)`

No user email address, password, token, robot identifier, map, IP address or
Home Assistant installation data is included in this repository or release.

## HACS installation

1. Open HACS and select **Custom repositories**.
2. Add `https://github.com/madsah211/ha-narwal-cloud-eu` as **Integration**.
3. Install **Narwal Cloud EU**.
4. Restart Home Assistant.
5. Add **Narwal Cloud EU (unofficial)** from **Settings → Devices & services**.

## Verification

Run from the repository root:

```text
uv run --python 3.13 --with cryptography python tests/test_auth.py
uv run --python 3.13 --with cryptography python tests/test_eu_region.py
uv run --python 3.13 --with cryptography python tests/test_eu_runtime.py
uv run --python 3.13 --with cryptography python tests/test_package.py
uv run --python 3.13 python -m compileall -q custom_components tests
```

The EU login request format was also checked against the live EU endpoint with
an invented `example.invalid` account. The server recognized the standard EU
payload shape and returned the expected invalid-account response.

## Security note

Credentials are stored in Home Assistant's local config entry so that tokens
can be refreshed automatically. Protect the Home Assistant host and backups.
This project is unofficial and the Narwal cloud protocol may change without
notice.

## License and attribution

MIT licensed. The original implementation and protocol work are credited to
[`mk0000001/ha-narwal-cloud`](https://github.com/mk0000001/ha-narwal-cloud).
