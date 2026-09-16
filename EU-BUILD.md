# Narwal Cloud EU: provenance and validation

## Project lineage

Narwal Cloud EU began as an adaptation of
[`mk0000001/ha-narwal-cloud`](https://github.com/mk0000001/ha-narwal-cloud):

- initial upstream version: `v0.9.2`
- initial upstream commit: `e773f8fcfae84c3c68eb4626f71fa2f855f8c60a`
- license: MIT

The project is now maintained here as the EU edition. The original copyright
and MIT notice are retained in `LICENSE`; later EU-specific work belongs to this
repository's maintainers.

## What this edition changes

This is no longer only an endpoint swap. Work maintained in this repository
includes:

- EU account authentication and automatic token renewal;
- Denmark (`DK`) broker discovery and regional request handling;
- EU runtime and device discovery;
- Home Assistant config, reauthentication, and options flows;
- saved-map parsing and persistent local cache;
- live robot pose, trajectory, and map rendering;
- room discovery and segment cleaning;
- official cleaning-plan retrieval and persistent template cache;
- stale-template invalidation and fail-closed room commands;
- privacy-safe diagnostics, packaging, tests, and releases.

## Verified scope

The live validation target is currently:

- Narwal EU cloud: `https://eu-app.narwaltech.com`
- account and broker country: `DK`
- robot model family: `YJCC012`
- Home Assistant 2026.3 or newer

Compatibility with other EU countries and product families is not yet claimed.
Reports and pull requests are welcome, but public reports must not include
credentials, account/device identifiers, broker addresses, raw MQTT payloads,
private map geometry, room names, or robot trajectories.

## Release verification

From the repository root, build the archive and run every test script:

```text
python build_release.py
python tests/test_auth.py
python tests/test_eu_region.py
python tests/test_eu_runtime.py
python tests/test_map_response_topics.py
python tests/test_live_map.py
python tests/test_coordinator.py
python tests/test_package.py
uvx ruff check custom_components tests build_release.py
uv run --python 3.13 python -m compileall -q custom_components tests
```

A release is not considered valid until the built archive contains only the
integration package, all tests pass, linting passes, and the public tree has
been checked for generated caches and private data.
