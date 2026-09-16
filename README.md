# Narwal Cloud EU for Home Assistant

A community-maintained Home Assistant integration for Narwal robots using the
European Narwal Cloud.

This repository is the primary home of the EU edition. It began as an MIT-licensed
fork of [`mk0000001/ha-narwal-cloud`](https://github.com/mk0000001/ha-narwal-cloud),
but its EU authentication, runtime, saved-map handling, live map, room cleaning,
cache safety, tests, and release process are maintained here.

> [!IMPORTANT]
> This project is not affiliated with or endorsed by Narwal. Narwal's cloud API
> is private and can change without notice.

## Verified compatibility

The current release is live-tested with:

- a Danish Narwal account on the EU cloud;
- country code and broker discovery set to `DK`;
- Narwal Freo model family `YJCC012`;
- Home Assistant 2026.3 or newer.

Other EU countries and robot models may work, but they have not been verified.
Please do not describe the integration as universally compatible with every EU
Narwal account yet.

## Features

- Narwal account login with automatic access/refresh-token renewal
- Manual app-token setup for existing installations
- Battery, movement, cleaning, fault, and turbo state
- Start, pause, resume, stop, and return to dock
- Cleaning modes: Freo Mind, vacuum, mop, vacuum-and-mop, and vacuum-then-mop
- Settings for suction, mop humidity, and cleaning cycles for the **next task**
- Saved map, rooms, robot position, live trajectory, and cleaning overlay
- Room/segment cleaning using Narwal's official per-room templates
- Persistent map and room-template cache across Home Assistant restarts
- Fail-closed room cleaning: no command is sent if a safe room template is missing
- Mop washing/drying controls and consumable remaining-time sensors
- Configurable state polling from 1 to 300 seconds (default: 1 second)
- English and Danish Home Assistant translations

## Installation with HACS

1. Open HACS and choose **Custom repositories**.
2. Add `https://github.com/madsah211/ha-narwal-cloud-eu` as an
   **Integration** repository.
3. Install **Narwal Cloud EU**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration**.
6. Select **Narwal Cloud EU (unofficial)** and sign in with your Narwal account.

Existing token-based entries can use **Reconfigure** to switch to automatic
account login. Manual token setup is documented in
[`docs/token_setup.md`](docs/token_setup.md).

## First-time map setup

Normally, you only need to open the official Narwal app **once after installing
the integration**. Open the map in the app and leave it open for approximately
**2 minutes**, even if the map appears sooner. This gives Home Assistant time to
receive both the map and the room-cleaning templates. Then close the app again.

Home Assistant saves the map and room-cleaning templates locally. They survive
normal Home Assistant restarts, integration updates, and Home Assistant Core
updates, so you do not need to open the Narwal app each time.

Open the app again only if:

- you change the map or room layout in the Narwal app;
- the integration is removed and installed again;
- Home Assistant reports that a room template is missing.

Until a valid room template is available, room cleaning is safely blocked rather
than risking a whole-home cleaning task.

## Important behavior and known limitations

- The vacuum card's fan-speed control selects suction for the **next cleaning
  task**. It does not currently change suction during an active task.
- Freo Mind uses Narwal's official automatic room plan; manual suction, humidity,
  and cycle choices are not applied to that mode.
- On the verified YJCC012 firmware, Narwal can report `in_station: false` while
  the robot is physically at the dock. Home Assistant may therefore show
  `idle` instead of `docked`; return-to-dock itself still works.
- A fresh cloud map request can time out while the app is closed. The last valid
  saved map remains available from the local cache.
- The detailed map-data camera exposes more raw map information than the normal
  rendered map camera. Keep it disabled unless you specifically need it.

## Privacy and security

Credentials are stored in Home Assistant's local config entry. They are not
written to this repository, diagnostics, or normal integration logs. Protect
your Home Assistant host and backups because they can contain local secrets.

Maps, room names, and robot positions describe a real home. Do not post raw MQTT
payloads, diagnostics containing identifiers, map geometry, broker addresses,
tokens, or unredacted logs in public issues.

## Documentation

- [`CHANGELOG.md`](CHANGELOG.md) — release history
- [`EU-BUILD.md`](EU-BUILD.md) — provenance, scope, and validation
- [`docs/discovered_features.md`](docs/discovered_features.md) — implemented and pending capabilities
- [`docs/protocol_yjcc012.md`](docs/protocol_yjcc012.md) — redacted protocol notes
- [`docs/token_setup.md`](docs/token_setup.md) — advanced manual-token setup

## Ownership, attribution, and license

This EU edition is maintained in this repository and may be described as the
**Narwal Cloud EU community integration**. It should not be presented as an
official Narwal product or as code written entirely from scratch.

The original implementation and protocol work remain credited to
[`mk0000001/ha-narwal-cloud`](https://github.com/mk0000001/ha-narwal-cloud), as
required by the MIT license. The EU-specific work and later maintenance are by
this repository's maintainers. See [`LICENSE`](LICENSE).
