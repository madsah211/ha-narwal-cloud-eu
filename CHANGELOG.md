# Changelog

## 0.10.0

- Replaced the inherited Korean project documentation and translation with an
  English-first README and a complete Danish Home Assistant translation.
- Rewrote compatibility, setup, privacy, provenance, and feature documentation
  to match the behavior actually verified on the EU YJCC012 integration.
- Documented that fan speed affects the next task, dock presence can be reported
  incorrectly by Narwal, and compatibility outside the tested Danish setup is
  not yet guaranteed.
- Kept the original MIT copyright and upstream attribution while identifying
  this repository as the maintained home of the EU edition.
- Adopted normal semantic versioning; `EU` remains part of the project name
  instead of being repeated in every future version number.

## 0.9.3-eu.10

- Stores official per-room cleaning templates together with the saved map so
  safe segment cleaning survives Home Assistant restarts.
- Invalidates cached templates whenever the map revision or room definition
  changes, then refreshes and stores a coherent map-and-plan snapshot.
- Refuses Freo Mind room cleaning when an official template is unavailable,
  instead of falling back to a command that may clean the whole map.

## 0.9.3-eu.9

- Stores the last valid saved map in Home Assistant's private local storage so
  rooms and the rendered base map survive restarts while older Freo firmware is
  asleep.
- Captures `map/display_map` alongside the existing MQTT base-status request
  while cleaning, without logging or exposing the raw payload.
- Merges live robot pose, frame timestamp, and Narwal's native trajectory into
  the cached saved map and renders the route on the normal map camera.

## 0.9.3-eu.8

- Sends the official app-style named broadcast-topic subscription for ten
  minutes instead of the incomplete numeric activation payload.
- Preserves the saved map's verified origin offsets and uses the validated
  `pixel = position - origin` coordinate transform.
- Restores the robot marker when the saved response contains an in-bounds pose.

## 0.9.3-eu.7

- Publishes a decoded saved map before requesting optional cleaning-plan data.
- A cleaning-plan timeout no longer discards map, room, renderer, or pose data.
- Uses the verified app-open wake sequence before sleeping-robot queries.

## 0.9.3-eu.6

- Reads the active map ID from saved-map field 1.
- Locates complete maps through validated nested protobuf envelopes.
- Rejects empty parser results instead of reporting a false successful map.

## 0.9.3-eu.5

- Treats `map/display_map` as live position, trajectory, and cleaning-overlay
  data rather than a complete saved map.
- Keeps map requests open until the actual saved-map response arrives.
- Retains privacy-safe topic and payload-length diagnostics without raw data.

## 0.9.3-eu.4

- Adds strict parsing for unframed complete-map protobuf messages published on
  `map/display_map`.
- Keeps only privacy-safe protobuf shape diagnostics.

## 0.9.3-eu.3

- Adds privacy-safe map diagnostics without exposing raw maps, account IDs,
  broker addresses, tokens, or device identifiers.

## 0.9.3-eu.2

- Accepts the YJCC012 live `map/display_map` publication as a fallback response
  when some EU firmware does not answer on `map/get_map/response`.

## 0.9.2

- Added explicit dark-theme icons and logos for Home Assistant 2026.8.

## 0.9.1

- Added local Narwal app icon and wordmark assets for Home Assistant 2026.3+.

## 0.9.0

- Reduced default state polling from 30 seconds to 1 second.
- Added a configurable 1–300 second polling interval.
- Isolated the slower map refresh from primary state polling.
- Documented that some idle YJCC012 sessions do not answer fresh map requests.

## 0.8.0

- Added Narwal account login and automatic token recovery.
- Changed segment cleaning to use the app's official per-room templates.
- Fixed timezone arithmetic that could make all entities unavailable.
