# App feature survey

This document separates implemented behavior from options merely observed in
the official Narwal app. The current live-validation target is a Freo YJCC012
using the European cloud and a Danish account.

## Implemented and verified

- Battery, movement, cleaning, fault, and turbo state
- Start, pause, resume, stop, and return to dock
- Freo Mind, vacuum, mop, vacuum-and-mop, and vacuum-then-mop tasks
- Suction, mop humidity, and cycle selection for the next cleaning task
- Saved map, room list, robot position, live trajectory, and cleaning overlay
- Room/segment cleaning using official per-room plans
- Persistent map and plan cache with stale-plan invalidation
- Fail-closed room cleaning when a matching official template is unavailable
- Mop washing/drying start and finish controls
- Consumable remaining-time sensors

## Known gaps in implemented controls

- Changing fan speed during an active task does not currently change live
  suction; the value is used for the next task.
- Narwal's `in_station` field is unreliable on the verified firmware, so a robot
  physically at the dock can appear as `idle` instead of `docked`.
- Fresh app-free saved-map retrieval is not reliable on every YJCC012 session;
  the integration preserves the last valid map and matching room plans locally.

## Seen in the app but not implemented

These options exist in the official app, but their commands and responses have
not been safely verified:

- intensive edge-cleaning schedule;
- Freo Mind strategy settings;
- do-not-disturb schedule;
- child lock and environment modes;
- mop-drying intensity and automatic detergent dosing;
- scheduled jobs;
- multiple-map management and map editing;
- live suction adjustment during an active task.

No guessed command should be sent for these features. They should be added only
after request and response behavior has been captured, redacted, and verified
on supported hardware.
