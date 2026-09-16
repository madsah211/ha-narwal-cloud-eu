# Narwal YJCC012 cloud protocol notes

These notes contain only redacted protocol structure. Tokens, account IDs,
device IDs, private MQTT captures, and map geometry are intentionally excluded.

## Transport

- Regional REST base for this EU build: `https://eu-app.narwaltech.com`
- MQTT broker is discovered through
  `/iot-broker-discover/app/v1/broker/discover?country=DK`.
- MQTT uses TLS and protocol level 5.
- The access token is the MQTT password. The 32-character account UUID is the
  MQTT username and appears in request header fields 1 and 2.
- Commands use a response topic and request UUID in header field 5.
- The official app subscribes to `<command topic>/response` before publishing.
- Payload framing is:
  `0x01 + varint(header_length) + header_protobuf + command_body_protobuf`.

## Confirmed commands

### Pause

- Topic: `/<product>/<device>/task/pause`
- Command body: empty

### Resume

- Topic: `/<product>/<device>/task/resume`
- Command body: empty

### Start whole-house Freo Mind cleaning

- Topic: `/<product>/<device>/clean/easy_clean/start`
- Body fields:
  - field 1: `1`
  - field 2: `1`
  - repeated field 3: one room plan per room
    - room field 1: room ID
    - room field 2: `3`
    - room field 6:
      - field 1: `2`
      - field 2: `1`
      - field 3: `2`
      - field 4: `1`
- Room IDs are read dynamically from the decoded map response.

### End task

- Topic: `/<product>/<device>/task/force_end`
- Command body: `12 02 01 02`
- Home Assistant mapping: `VacuumEntityFeature.STOP` / `async_stop()`

## State

- REST endpoint: `/device-task/work-status/get`
- Required parameter: `source=0`
- Confirmed state transitions:
  - idle to cleaning after `clean/easy_clean/start`
  - cleaning to idle after `task/force_end`
  - returning is exposed by `recall=true`

## Current implementation status

The EU edition now includes the map camera, room segments, mode and next-task
option selectors, mop station controls, account login, automatic token renewal,
and the dedicated dock recall command. Saved maps and official room templates
are cached together and validated before room cleaning.

Still unresolved:

- live suction changes during an active task;
- reliable physical dock detection when Narwal reports `in_station: false`;
- reliable fresh saved-map retrieval from every idle, app-free session;
- validation across EU countries and Narwal product families beyond the tested
  Danish YJCC012 setup.

## Deployment policy

Only publish complete, tested archives. Never include raw captures, credentials,
account or device identifiers, broker addresses, private map geometry, room
names, or trajectories.

## Map and room discovery

- Request: `/map/get_map`, body `08 00 10 00`
- Response: `/map/get_map/response`
- Response body field 1 is success (`1`); field 2 is the map message.
- Map fields: revision `2`, resolution `3`, width `4`, height `5`,
  repeated room metadata `12`, zlib-compressed grid `17`.
- Room fields: ID `1`, type `2`, UTF-8 custom name `3`, category `4`,
  duplicate instance index `8`.
- Map revision, dimensions and room count are read dynamically.

## Cleaning modes and options

`/clean/plan/get/response` returns the official defaults. Plan field 3 is
the mode number and repeated field 9 contains per-room templates.

The `/clean/easy_clean/start` body has:

- field 1: mode
- field 2: constant `1`
- repeated field 3: room configuration

Verified mode values:

- `1`: Freo Mind
- `2`: Vacuum
- `3`: Mop
- `4`: Vacuum and mop
- `5`: Vacuum then mop

Per-room configuration starts with room ID field 1 and constant field 2 = 1.

- Vacuum: field 4 message; suction field 1 (`1` quiet, `2` standard,
  `3` strong), cycle field 2 (`1`-`3`).
- Mop: field 5 message; constant field 1 = 1, cycle field 2 (`1`-`3`),
  humidity field 3 (`1` slightly dry, `2` standard, `3` slightly wet).
- Vacuum and mop: field 6; suction field 1, vacuum cycle field 2,
  humidity field 3, mop cycle field 4.
- Vacuum then mop: field 7 containing vacuum settings as field 1 and mop
  settings as field 2.
- Freo Mind uses the captured automatic per-room settings and does not
  accept manual option selects.

## Dock mop washing

- Start washing followed by automatic drying:
  `/supply/wash_and_dry_mop`, empty body.
- Finish washing or drying:
  `/task/force_end`, empty body in the current official app. The previously
  captured `12 02 01 02` body is also accepted for ending an active task.
  YJCC012 applies this command without returning a response, so successful
  transmission is treated as success instead of surfacing a false timeout.

## Live map and robot pose

- `/map/get_map`, body `08 00 10 00`.
- Static map payload field 7: `origin` (`PoseData`).
- Static map payload field 8: `station` (`PoseData`).
- Static map payload field 24: `robot_pose` (`PoseData`).
- Static map payload field 36: `robot_pose_update_time`.
- The camera is rendered from the current compressed grid and pose fields; no
  screenshot is retained.

## Battery status

- Request topic: `/status/get_device_base_status`.
- Asynchronous broadcast: `/status/robot_base_status`.
- YJCC012 battery percentage is protobuf fixed32 float field `2`.
- The decoded float is exposed as the battery percentage.

## Consumables

- `POST /consumables-management-app-server/v3/consumables/list`
- JSON body fields: `deviceId`, `productId`.
- Timed rows expose `total_duration` and `usage_duration` in seconds.
- Remaining hours are
  `ceil((total_duration - usage_duration) / 3600)`.
