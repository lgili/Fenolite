# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The experimental Altium PCB document (``.PcbDoc``) of the Altium writer (change c0035, capability
altium-pcb-writer, "PCB document file", "PCB document placement" and "PCB document links and nets").

Written from ``docs/formats/altium/pcb-document.md`` and ``pcb-records.md``. A document is a compound file:
two header streams, then one storage per object kind holding ``Header`` (the record count) and ``Data``.
Footprint primitives are placed as KiCad places them (``Transform.placement``), then Y is negated and the
board shifted so that its lower-left corner lies at (1000 mil, 1000 mil). Components link to the
schematic through ``SOURCEUNIQUEID=\\<unique id>``. No routing, via, zone, rule or class is written.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import fenolite.backends.altium.pcbrecords as rec
from fenolite.backends.altium.ascii import Field
from fenolite.backends.altium.cfb import Entry, Storage, write_compound
from fenolite.backends.altium.libboard import guid
from fenolite.backends.altium.pcblib import (
    LibFootprint,
    PadExtras,
    check_footprint,
    graphic_records,
    pad_bytes,
)
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry.transform import Transform
from fenolite.model.board import Side

FILE_HEADER_TEXT = "PCB 5.0 Binary File"
"""``FileHeader``: the 32-bit value 19, then the first ten characters of this text in UTF-16LE."""
FILE_HEADER_SIX_TEXT = "PCB 6.0 Binary File"
FILE_HEADER_SIX_VERSION = 5.01
BOARD_OFFSET_MIL = 1000
"""The board's lower-left corner and ``ORIGINX``/``ORIGINY`` lie at (1000 mil, 1000 mil)."""
_OFFSET_NM = BOARD_OFFSET_MIL * 25_400
EMPTY_STORAGES: tuple[str, ...] = (
    "Vias6",
    "Fills6",
    "Regions6",
    "ShapeBasedRegions6",
    "Polygons6",
    "Dimensions6",
    "Classes6",
    "Rules6",
    "ComponentBodies6",
    "ShapeBasedComponentBodies6",
    "DifferentialPairs6",
    "Connections6",
)
"""Storages KiCad looks for: written with ``Header`` 0 and an empty ``Data``."""
LAYER_COUNT = 74
MECHANICAL_ENABLED = (69, 70, 71, 72)
TOP, BOTTOM = 1, 32
TEXT_SIZE = 137
DESIGNATOR_HEIGHT = 1_000_000
DESIGNATOR_STROKE = 150_000
DESIGNATOR_RISE = 500_000
COMMENT_DROP = 1_500_000
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-PCB-DOC-BOTTOM",
        "H-A-PCB-DOC-LINK",
        "H-A-PCB-DOC-NETS",
        "H-A-PCB-DOC-OPEN",
        "H-A-PCB-DOC-VIEWER",
        "H-A-PCB-KICAD-DOC",
    ),
)
"""The PCB document is inferred from public sources; ``pcb import`` checks only what KiCad reads."""


@dataclass(frozen=True, slots=True)
class PlacedComponent:
    """One component on the board: its schematic link, its footprint and its placement (KiCad frame)."""

    ref: str
    unique_id: str
    comment: str
    footprint: LibFootprint
    footprint_library: str
    lib_reference: str
    component_library: str
    at: Point
    rotation: int = 0
    side: Side = "top"
    locked: bool = False
    pad_nets: Mapping[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class PcbDocSpec:
    """A board: its outline (KiCad frame, in order), its components and its net names."""

    outline: tuple[Point, ...]
    components: tuple[PlacedComponent, ...] = ()
    nets: tuple[str, ...] = ()


def _u32(value: int) -> bytes:
    return struct.pack("<I", value)


def _bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def degrees_text(udeg: int) -> str:
    """Microdegrees as degrees in ``[0, 360)`` with at most six decimals."""
    whole, rest = divmod(udeg % 360_000_000, 1_000_000)
    return f"{whole}.{f'{rest:06d}'.rstrip('0')}" if rest else str(whole)


@dataclass(frozen=True, slots=True)
class Frame:
    """KiCad's Y-down board frame → Altium's: Y negated, the outline's lowest X and highest Y moved to
    (1000 mil, 1000 mil); points in nanometres."""

    min_x: int
    max_y: int

    @classmethod
    def of(cls, outline: Sequence[Point]) -> Frame:
        if len(outline) < 3:
            raise ValueError("a board outline needs at least three points")
        return cls(min(p.x for p in outline), max(p.y for p in outline))

    def __call__(self, point: Point) -> Point:
        return Point(point.x - self.min_x + _OFFSET_NM, self.max_y - point.y + _OFFSET_NM)


def file_header() -> bytes:
    return _u32(19) + FILE_HEADER_TEXT[:10].encode("utf-16-le")


def file_header_six(key: str = "") -> bytes:
    """``FileHeaderSix``: the header text, the version double and the document's GUID, each text as a
    32-bit length and a length byte that both hold the text length. ``key`` names the document."""
    text = FILE_HEADER_SIX_TEXT.encode("ascii")
    unique = guid(f"pcbdoc:{key}").encode("ascii")
    return (
        _u32(len(text))
        + bytes((len(text),))
        + text
        + struct.pack("<d", FILE_HEADER_SIX_VERSION)
        + _u32(len(unique))
        + bytes((len(unique),))
        + unique
    )


def board_record(outline: Sequence[Point]) -> bytes:
    """The one ``Board6`` record: kind, version, origin, layers 1 to 74 linked ``1 → 32 → 0``, the outline."""
    frame = Frame.of(outline)
    origin = rec.mil_text(rec.to_units(_OFFSET_NM))
    fields: list[Field] = [
        ("KIND", "Protel_Advanced_PCB"),
        ("VERSION", "5.00"),
        ("ORIGINX", origin),
        ("ORIGINY", origin),
    ]
    for layer in range(1, LAYER_COUNT + 1):
        previous = TOP if layer == BOTTOM else 0
        following = BOTTOM if layer == TOP else 0
        fields += [
            (f"LAYER{layer}NAME", rec.LAYER_NAMES[layer]),
            (f"LAYER{layer}PREV", str(previous)),
            (f"LAYER{layer}NEXT", str(following)),
        ]
        if layer in MECHANICAL_ENABLED:
            fields.append((f"LAYER{layer}MECHENABLED", "TRUE"))
    vertices = [*outline, outline[0]]
    for index, point in enumerate(vertices):
        placed = frame(point)
        fields += [
            (f"KIND{index}", "0"),
            (f"VX{index}", rec.mil_text(rec.to_units(placed.x))),
            (f"VY{index}", rec.mil_text(rec.to_units(placed.y))),
        ]
    return rec.property_block(fields)


def _component_record(component: PlacedComponent, frame: Frame) -> bytes:
    at = frame(component.at)
    fields: list[Field] = [
        ("LAYER", "BOTTOM" if component.side == "bottom" else "TOP"),
        ("X", rec.mil_text(rec.to_units(at.x))),
        ("Y", rec.mil_text(rec.to_units(at.y))),
        ("ROTATION", degrees_text(component.rotation)),
        ("LOCKED", _bool(component.locked)),
        ("NAMEON", "TRUE"),
        ("COMMENTON", "FALSE"),
        ("PATTERN", component.footprint.defn.name),
        ("SOURCEDESIGNATOR", component.ref),
        ("SOURCEUNIQUEID", "\\" + component.unique_id),
        ("SOURCEHIERARCHICALPATH", ""),
        ("SOURCEFOOTPRINTLIBRARY", component.footprint_library),
        ("SOURCELIBREFERENCE", component.lib_reference),
        ("SOURCECOMPONENTLIBRARY", component.component_library),
    ]
    return rec.property_block(fields)


def text_record(
    text: str,
    *,
    layer: int,
    at: Point,
    component: int,
    designator: bool,
    wide_index: int,
    mirrored: bool = False,
) -> bytes:
    """A text (type 5) in the 123-byte long form, ``at`` in nanometres in the Altium frame."""
    body = rec.prefix(layer, component=component)
    body += struct.pack(
        "<3iHdBi",
        rec.to_units(at.x),
        rec.to_units(at.y),
        rec.to_units(DESIGNATOR_HEIGHT),
        1,
        0.0,
        1 if mirrored else 0,
        rec.to_units(DESIGNATOR_STROKE),
    )
    body += bytes((0 if designator else 1, 1 if designator else 0, 0, 0, 0, 0))
    body += bytes(64) + b"\0" + struct.pack("<iI", 0, wide_index) + bytes(TEXT_SIZE - 119)
    assert len(body) == TEXT_SIZE
    return bytes((rec.TEXT,)) + rec.subrecord(body) + rec.subrecord(rec.short_string(text))


def _wide_entry(index: int, text: str) -> bytes:
    data = text.encode("utf-16-le") + b"\0\0"
    return struct.pack("<2I", index, len(data)) + data


@dataclass
class _Placed:
    pads: list[bytes]
    tracks: list[bytes]
    arcs: list[bytes]
    box: tuple[int, int, int, int]


def _extend(box: list[int], x: int, y: int, reach: int = 0) -> None:
    box[0], box[1] = min(box[0], x - reach), min(box[1], y - reach)
    box[2], box[3] = max(box[2], x + reach), max(box[3], y + reach)


def place_component(component: PlacedComponent, index: int, frame: Frame, nets: Mapping[str, int]) -> _Placed:
    """The pads, tracks and arcs of one component at absolute Altium coordinates, and the box of its pads
    and graphics (nanometres, Altium frame)."""
    footprint = component.footprint
    check = check_footprint(footprint.defn, footprint.extras, texts=footprint.texts)
    if check.refusal is not None:
        raise ValueError(f"{component.ref}: {check.refusal}")
    bottom = component.side == "bottom"
    transform = Transform.placement(component.at, component.rotation, mirror=bottom)

    def to_frame(point: Point) -> Point:
        return frame(transform.apply(point))

    box = [2**62, 2**62, -(2**62), -(2**62)]
    pads: list[bytes] = []
    for pad in check.pads:
        at = to_frame(pad.position)
        net = nets.get(component.pad_nets.get(pad.number, ""), rec.NO_INDEX)
        pads.append(
            pad_bytes(
                pad,
                footprint.extras.get(pad.id, PadExtras()),
                at=at,
                rotation_udeg=transform.apply_angle(pad.rotation),
                flip=bottom,
                net=net,
                component=index,
            )
        )
        _extend(box, at.x, at.y, max(pad.size.w, pad.size.h) // 2)
    tracks: list[bytes] = []
    arcs: list[bytes] = []
    for graphic in check.graphics:
        for record in graphic_records(graphic, to_frame, flip=bottom, component=index):
            (tracks if record[0] == rec.TRACK else arcs).append(record)
        points = [to_frame(p) for p in graphic.points]
        if graphic.kind == "circle":
            centre, edge = points
            reach = max(abs(edge.x - centre.x), abs(edge.y - centre.y))
            _extend(box, centre.x, centre.y, reach)
        else:
            for point in points:
                _extend(box, point.x, point.y)
    if box[0] > box[2]:
        at = frame(component.at)
        box = [at.x, at.y, at.x, at.y]
    return _Placed(pads, tracks, arcs, (box[0], box[1], box[2], box[3]))


def _storage(name: str, records: Sequence[bytes]) -> Storage:
    return Storage(name, (("Header", _u32(len(records))), ("Data", b"".join(records))))


def write_pcbdoc(spec: PcbDocSpec) -> bytes:
    """The bytes of the PCB document of ``spec`` (``pcb-document.md``, "Fenolite's choices"). ``ValueError``
    for an outline of fewer than three points or a refused footprint; ``cfb.CompoundTooLarge`` past the
    size limit."""
    frame = Frame.of(spec.outline)
    net_names = sorted(spec.nets)
    nets = {name: index for index, name in enumerate(net_names)}
    components: list[bytes] = []
    pads: list[bytes] = []
    tracks: list[bytes] = []
    arcs: list[bytes] = []
    texts: list[bytes] = []
    wide: list[bytes] = []
    for index, component in enumerate(spec.components):
        components.append(_component_record(component, frame))
        placed = place_component(component, index, frame, nets)
        pads += placed.pads
        tracks += placed.tracks
        arcs += placed.arcs
        x0, y0, x1, y1 = placed.box
        middle = (x0 + x1) // 2
        bottom = component.side == "bottom"
        overlay = rec.LAYER_MAP["B.SilkS" if bottom else "F.SilkS"]
        for text, designator, at in (
            (component.ref, True, Point(middle, y1 + DESIGNATOR_RISE)),
            (component.comment, False, Point(middle, y0 - COMMENT_DROP)),
        ):
            number = len(texts)
            texts.append(
                text_record(
                    text,
                    layer=overlay,
                    at=at,
                    component=index,
                    designator=designator,
                    wide_index=number,
                    mirrored=bottom,
                )
            )
            wide.append(_wide_entry(number, text))
    entries: list[Entry] = [
        ("FileHeader", file_header()),
        ("FileHeaderSix", file_header_six(",".join(c.unique_id for c in spec.components))),
        _storage("Board6", [board_record(spec.outline)]),
        _storage("Nets6", [rec.property_block((("NAME", name),)) for name in net_names]),
        _storage("Components6", components),
        _storage("Pads6", pads),
        _storage("Tracks6", tracks),
        _storage("Arcs6", arcs),
        _storage("Texts6", texts),
        _storage("WideStrings6", wide),
    ]
    entries += [_storage(name, []) for name in EMPTY_STORAGES]
    return write_compound(entries)


__all__ = [
    "BOARD_OFFSET_MIL",
    "EMPTY_STORAGES",
    "EVIDENCE",
    "FILE_HEADER_SIX_TEXT",
    "FILE_HEADER_TEXT",
    "Frame",
    "PcbDocSpec",
    "PlacedComponent",
    "board_record",
    "degrees_text",
    "file_header",
    "file_header_six",
    "place_component",
    "text_record",
    "write_pcbdoc",
]
