# Freo Z10 beta protocol

Version `0.11.0-beta.2` adds a deliberately isolated command profile for the
Freo Z10 product key `OlkUn3oUCu`.

## Start behavior

Manual cleaning modes 2–5 use `clean/start_clean`. The protobuf body carries:

- the current saved-map ID;
- the exact current room IDs;
- one `CleanParam` per room (mode, suction, mop humidity, and cycles);
- the selected task mode.

The integration waits for the matching response topic and requires Narwal's
field-1 `SUCCESS` result code. Publishing alone, a malformed response, and
explicit rejection codes are not reported as a successful start.

Freo Mind (mode 1) continues to require Narwal's official room templates. It is
blocked when any current room lacks a template; the integration never invents a
Freo Mind template.

## Map changes

When the map ID or room definition changes on the Z10 profile, cached templates
are invalidated. The integration performs a fresh activated `clean/plan/get`,
retries once if the Freo Mind plan is incomplete, and stores the new plans only
when every current room is covered. The YJCC012 map and template flow remains
unchanged. An incomplete old Z10 generation may remain useful for map display,
but is never used to start room cleaning.

## Isolation and rollback

The YJCC012 profile still uses its existing `clean/easy_clean/start` bytes. No
fallback sends both protocols. Unknown product IDs do not opt into the Z10
profile.

This implementation is a prerelease until it has been exercised on a physical
Freo Z10. Rollback target: `v0.10.1`.
