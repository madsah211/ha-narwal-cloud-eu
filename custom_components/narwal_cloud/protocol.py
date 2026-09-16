"""Small protobuf helpers for the Narwal cloud MQTT protocol.

Narwal does not publish protobuf schemas for these messages.  This module
therefore decodes only the fields that have been verified against YJCC012
traffic captured from the official app.
"""

from __future__ import annotations

import base64
import math
import struct
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class ProtoField:
    """One protobuf field preserving its wire type and raw value."""

    number: int
    wire_type: int
    value: int | bytes


@dataclass(frozen=True)
class NarwalRoom:
    """A selectable room from the current saved map."""

    room_id: int
    name: str
    room_type: int = 0
    instance_index: int = 0


@dataclass(frozen=True)
class NarwalPose:
    """One robot-map pose in Narwal's coordinate system."""

    x: float = 0.0
    y: float = 0.0
    angle: float = 0.0


@dataclass(frozen=True)
class NarwalMap:
    """Map, rooms, and live poses returned by `/map/get_map`."""

    revision: int = 0
    resolution: int = 0
    width: int = 0
    height: int = 0
    rooms: tuple[NarwalRoom, ...] = ()
    compressed_grid: bytes = b""
    border: tuple[int, int, int, int] = (0, 0, 0, 0)
    origin_x: int = 0
    origin_y: int = 0
    origin: NarwalPose | None = None
    station: NarwalPose | None = None
    robot_pose: NarwalPose | None = None
    robot_pose_update_time: int = 0
    trajectory: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class NarwalDisplayMap:
    """Live pose and trajectory broadcast separately from the saved map."""

    robot_pose: NarwalPose
    timestamp: int = 0
    trajectory: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class NarwalCleanPlan:
    """One official-app cleaning plan template."""

    plan_id: int
    mode: int
    room_templates: dict[int, bytes] = field(default_factory=dict)


ROOM_TYPE_NAMES = {
    0: "Room",
    1: "Main bedroom",
    2: "Bedroom",
    3: "Living room",
    4: "Kitchen",
    5: "Study",
    6: "Bathroom",
    7: "Dining room",
    8: "Corridor",
    9: "Balcony",
    # YJCC012 reports its corridor with room type 10.
    10: "Corridor",
    11: "Cloakroom",
    12: "Nursery",
    13: "Recreation room",
    14: "Shower room",
    15: "Other room",
}


def read_varint(data: bytes, position: int = 0) -> tuple[int, int]:
    """Read one protobuf/MQTT variable-length integer."""
    value = 0
    shift = 0
    while position < len(data) and shift < 70:
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, position
        shift += 7
    raise ValueError("Invalid or truncated varint")


def decode_fields(data: bytes) -> list[ProtoField]:
    """Decode protobuf primitives without guessing nested message types."""
    fields: list[ProtoField] = []
    position = 0
    while position < len(data):
        key, position = read_varint(data, position)
        number = key >> 3
        wire_type = key & 7
        if number == 0:
            raise ValueError("Invalid protobuf field number")
        if wire_type == 0:
            value, position = read_varint(data, position)
        elif wire_type == 1:
            end = position + 8
            if end > len(data):
                raise ValueError("Truncated fixed64 field")
            value = data[position:end]
            position = end
        elif wire_type == 2:
            size, position = read_varint(data, position)
            end = position + size
            if end > len(data):
                raise ValueError("Truncated length-delimited field")
            value = data[position:end]
            position = end
        elif wire_type == 5:
            end = position + 4
            if end > len(data):
                raise ValueError("Truncated fixed32 field")
            value = data[position:end]
            position = end
        else:
            raise ValueError(f"Unsupported protobuf wire type {wire_type}")
        fields.append(ProtoField(number, wire_type, value))
    return fields


def unwrap_transport(payload: bytes) -> tuple[bytes, bytes]:
    """Split Narwal's framed common header from the command/response body."""
    if not payload or payload[0] != 1:
        raise ValueError("Invalid Narwal transport marker")
    header_size, body_start = read_varint(payload, 1)
    header_end = body_start + header_size
    if header_end > len(payload):
        raise ValueError("Truncated Narwal transport header")
    return payload[body_start:header_end], payload[header_end:]


def _values(
    fields: list[ProtoField], number: int, wire_type: int | None = None
) -> list[int | bytes]:
    return [
        item.value
        for item in fields
        if item.number == number
        and (wire_type is None or item.wire_type == wire_type)
    ]


def _integer(fields: list[ProtoField], number: int, default: int = 0) -> int:
    values = _values(fields, number, 0)
    return int(values[-1]) if values else default


def _message(fields: list[ProtoField], number: int) -> bytes:
    values = _values(fields, number, 2)
    return bytes(values[-1]) if values else b""


def _messages(fields: list[ProtoField], number: int) -> list[bytes]:
    return [bytes(value) for value in _values(fields, number, 2)]


def _signed(value: int, bits: int = 64) -> int:
    """Interpret protobuf int32/int64 values emitted as two's complement."""
    sign = 1 << (bits - 1)
    return value - (1 << bits) if value & sign else value


def _fixed32_float(fields: list[ProtoField], number: int) -> float:
    values = _values(fields, number, 5)
    if not values:
        return 0.0
    return float(struct.unpack("<f", bytes(values[-1]))[0])


def _pose(fields: list[ProtoField], number: int) -> NarwalPose | None:
    raw_pose = _message(fields, number)
    if not raw_pose:
        return None
    pose = decode_fields(raw_pose)
    point_raw = _message(pose, 1)
    if not point_raw:
        return None
    point = decode_fields(point_raw)
    return NarwalPose(
        x=_fixed32_float(point, 1),
        y=_fixed32_float(point, 2),
        angle=_fixed32_float(pose, 2),
    )


def parse_map_response(payload: bytes) -> NarwalMap:
    """Parse `/map/get_map/response` into a stable public model."""
    _, body = unwrap_transport(payload)
    response = decode_fields(body)
    if _integer(response, 1) != 1:
        raise ValueError("Narwal map request was not successful")
    map_fields = _find_complete_map_fields(decode_fields(_message(response, 2)))
    if map_fields is None:
        raise ValueError("Narwal response did not contain a complete saved map")
    return _parse_map_fields(map_fields)


def _find_complete_map_fields(
    fields: list[ProtoField], depth: int = 0
) -> list[ProtoField] | None:
    """Find the saved-map protobuf node without accepting live overlays."""
    if (
        _integer(fields, 1) > 0
        and _integer(fields, 4) > 0
        and _integer(fields, 5) > 0
        and bool(_message(fields, 17))
    ):
        return fields
    if depth >= 3:
        return None
    for item in fields:
        if item.wire_type != 2:
            continue
        try:
            nested = decode_fields(bytes(item.value))
        except ValueError:
            continue
        match = _find_complete_map_fields(nested, depth + 1)
        if match is not None:
            return match
    return None


def protobuf_field_signature(payload: bytes) -> list[str]:
    """Return field numbers and wire types without exposing protobuf values."""
    try:
        fields = decode_fields(payload)
    except ValueError:
        return []
    return sorted({f"{item.number}:{item.wire_type}" for item in fields})


def parse_map_display(payload: bytes) -> NarwalMap:
    """Parse an unframed `map/display_map` broadcast as a complete map."""
    try:
        map_fields = decode_fields(payload)
    except ValueError as err:
        raise ValueError("Invalid display-map protobuf") from err
    map_data = _parse_map_fields(map_fields)
    if (
        map_data.width <= 0
        or map_data.height <= 0
        or not map_data.compressed_grid
    ):
        raise ValueError("Unsupported display-map protobuf shape")
    return map_data


def _packed_float32(payload: bytes) -> list[float]:
    """Decode complete finite float32 values from one packed protobuf field."""
    usable = len(payload) - (len(payload) % 4)
    return [
        value[0]
        for value in struct.iter_unpack("<f", payload[:usable])
        if math.isfinite(value[0])
    ]


def parse_display_map(payload: bytes) -> NarwalDisplayMap:
    """Parse the unframed live ``map/display_map`` broadcast."""
    fields = decode_fields(payload)
    robot_pose = _pose(fields, 1)
    if robot_pose is None:
        raise ValueError("Narwal display map did not contain a robot pose")

    trajectory: list[tuple[float, float]] = []
    for raw_window in _messages(fields, 2):
        window = decode_fields(raw_window)
        xs = _packed_float32(_message(window, 1))
        ys = _packed_float32(_message(window, 2))
        trajectory.extend(zip(xs, ys, strict=False))
    return NarwalDisplayMap(
        robot_pose=robot_pose,
        timestamp=_integer(fields, 10),
        trajectory=tuple(trajectory),
    )


def merge_display_map(base: NarwalMap, display: NarwalDisplayMap) -> NarwalMap:
    """Overlay live robot data without replacing the saved room grid."""
    return replace(
        base,
        robot_pose=display.robot_pose,
        robot_pose_update_time=display.timestamp,
        trajectory=display.trajectory,
    )


def _pose_to_cache(pose: NarwalPose | None) -> dict[str, float] | None:
    return (
        {"x": pose.x, "y": pose.y, "angle": pose.angle}
        if pose is not None
        else None
    )


def _pose_from_cache(value: object) -> NarwalPose | None:
    if not isinstance(value, dict):
        return None
    return NarwalPose(
        x=float(value.get("x", 0.0)),
        y=float(value.get("y", 0.0)),
        angle=float(value.get("angle", 0.0)),
    )


def map_to_cache(map_data: NarwalMap) -> dict:
    """Serialize a saved map for Home Assistant's local private storage."""
    return {
        "revision": map_data.revision,
        "resolution": map_data.resolution,
        "width": map_data.width,
        "height": map_data.height,
        "rooms": [
            {
                "room_id": room.room_id,
                "name": room.name,
                "room_type": room.room_type,
                "instance_index": room.instance_index,
            }
            for room in map_data.rooms
        ],
        "compressed_grid": base64.b64encode(map_data.compressed_grid).decode("ascii"),
        "border": list(map_data.border),
        "origin_x": map_data.origin_x,
        "origin_y": map_data.origin_y,
        "origin": _pose_to_cache(map_data.origin),
        "station": _pose_to_cache(map_data.station),
        "robot_pose": _pose_to_cache(map_data.robot_pose),
        "robot_pose_update_time": map_data.robot_pose_update_time,
    }


def clean_plans_to_cache(plans: tuple[NarwalCleanPlan, ...]) -> list[dict]:
    """Serialize official cleaning plans for private local storage."""
    return [
        {
            "plan_id": plan.plan_id,
            "mode": plan.mode,
            "room_templates": {
                str(room_id): base64.b64encode(template).decode("ascii")
                for room_id, template in plan.room_templates.items()
            },
        }
        for plan in plans
    ]


def clean_plans_from_cache(value: object) -> tuple[NarwalCleanPlan, ...]:
    """Restore and validate official per-room cleaning templates."""
    if not isinstance(value, list):
        raise TypeError("Invalid cached Narwal cleaning plans")
    plans: list[NarwalCleanPlan] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError("Invalid cached Narwal cleaning plan")
        raw_templates = item.get("room_templates", {})
        if not isinstance(raw_templates, dict):
            raise TypeError("Invalid cached Narwal room templates")
        templates: dict[int, bytes] = {}
        for raw_room_id, encoded in raw_templates.items():
            room_id = int(raw_room_id)
            template = base64.b64decode(str(encoded), validate=True)
            if _integer(decode_fields(template), 1) != room_id:
                raise ValueError("Cached Narwal room template has the wrong room ID")
            templates[room_id] = template
        plans.append(
            NarwalCleanPlan(
                plan_id=int(item.get("plan_id", 0)),
                mode=int(item.get("mode", 0)),
                room_templates=templates,
            )
        )
    return tuple(plans)


def map_from_cache(value: object) -> NarwalMap:
    """Restore a saved map from Home Assistant's local private storage."""
    if not isinstance(value, dict):
        raise TypeError("Invalid cached Narwal map")
    rooms_value = value.get("rooms", [])
    rooms = tuple(
        NarwalRoom(
            room_id=int(room["room_id"]),
            name=str(room["name"]),
            room_type=int(room.get("room_type", 0)),
            instance_index=int(room.get("instance_index", 0)),
        )
        for room in rooms_value
        if isinstance(room, dict) and "room_id" in room and "name" in room
    )
    border_value = value.get("border", [0, 0, 0, 0])
    if not isinstance(border_value, list) or len(border_value) != 4:
        raise ValueError("Invalid cached Narwal map border")
    return NarwalMap(
        revision=int(value.get("revision", 0)),
        resolution=int(value.get("resolution", 0)),
        width=int(value.get("width", 0)),
        height=int(value.get("height", 0)),
        rooms=rooms,
        compressed_grid=base64.b64decode(str(value.get("compressed_grid", ""))),
        border=tuple(int(item) for item in border_value),
        origin_x=int(value.get("origin_x", 0)),
        origin_y=int(value.get("origin_y", 0)),
        origin=_pose_from_cache(value.get("origin")),
        station=_pose_from_cache(value.get("station")),
        robot_pose=_pose_from_cache(value.get("robot_pose")),
        robot_pose_update_time=int(value.get("robot_pose_update_time", 0)),
    )


def _parse_map_fields(map_fields: list[ProtoField]) -> NarwalMap:
    """Decode the verified fields shared by response and broadcast maps."""

    rooms: list[NarwalRoom] = []
    duplicate_names: dict[str, int] = {}
    for raw_room in _messages(map_fields, 12):
        room = decode_fields(raw_room)
        room_id = _integer(room, 1)
        room_type = _integer(room, 2)
        instance_index = _integer(room, 8)
        raw_name = _message(room, 3)
        name = raw_name.decode("utf-8", errors="replace").strip()
        if not name:
            name = ROOM_TYPE_NAMES.get(room_type, "Room")
            if instance_index > 1:
                name = f"{name} {instance_index}"
        duplicate_names[name] = duplicate_names.get(name, 0) + 1
        if duplicate_names[name] > 1:
            name = f"{name} {duplicate_names[name]}"
        if room_id:
            rooms.append(NarwalRoom(room_id, name, room_type, instance_index))

    border_fields = decode_fields(_message(map_fields, 6))
    border = (
        _signed(_integer(border_fields, 1)),
        _signed(_integer(border_fields, 2)),
        _signed(_integer(border_fields, 3)),
        _signed(_integer(border_fields, 4)),
    )

    return NarwalMap(
        revision=_integer(map_fields, 1),
        resolution=_integer(map_fields, 3),
        width=_integer(map_fields, 4),
        height=_integer(map_fields, 5),
        rooms=tuple(rooms),
        compressed_grid=_message(map_fields, 17),
        border=border,
        origin_x=_signed(_integer(border_fields, 3)),
        origin_y=_signed(_integer(border_fields, 1)),
        origin=_pose(map_fields, 7),
        station=_pose(map_fields, 8),
        robot_pose=_pose(map_fields, 24),
        robot_pose_update_time=_integer(map_fields, 36),
    )


def parse_base_status_response(payload: bytes) -> dict[str, int]:
    """Parse the verified battery field from robot_base_status.

    YJCC012 publishes the battery percentage as protobuf fixed32 float field
    2 on the asynchronous ``status/robot_base_status`` broadcast.
    """
    fields = decode_fields(payload)
    if not _values(fields, 2, 5):
        raise ValueError("Narwal battery field is missing")
    battery = round(_fixed32_float(fields, 2))
    if not 0 <= battery <= 100:
        raise ValueError("Narwal returned an invalid battery percentage")
    return {"battery_percentage": battery}


def parse_clean_plans_response(payload: bytes) -> tuple[NarwalCleanPlan, ...]:
    """Parse official cleaning-plan room templates.

    Each field 2 item is a plan; its field 9 entries are the exact room
    messages accepted as field 3 by `/clean/easy_clean/start`.
    """
    _, body = unwrap_transport(payload)
    response = decode_fields(body)
    if _integer(response, 1) != 1:
        raise ValueError("Narwal cleaning-plan request was not successful")

    plans: list[NarwalCleanPlan] = []
    for raw_plan in _messages(response, 2):
        plan = decode_fields(raw_plan)
        templates: dict[int, bytes] = {}
        for room_template in _messages(plan, 9):
            room = decode_fields(room_template)
            room_id = _integer(room, 1)
            if room_id:
                templates[room_id] = room_template
        plans.append(
            NarwalCleanPlan(
                plan_id=_integer(plan, 1),
                mode=_integer(plan, 3),
                room_templates=templates,
            )
        )
    return tuple(plans)
