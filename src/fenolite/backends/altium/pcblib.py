# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium PCB library (``.PcbLib``) of the Altium writer (change c0035, capability altium-pcb-writer,
"Footprint content checks", "Footprint line and arc records" and "PCB library file").

Written from ``docs/formats/altium/pcb-library.md`` and ``pcb-records.md``. ``check_footprint`` refuses a
footprint it cannot write exactly and lists what it leaves out; ``pad_bytes`` and ``graphic_records`` turn
a footprint's pads and graphics into records in any frame (the library's own, or a PCB document's).
The KiCad-only facts the model keeps opaque (corner ratio, drill forms, margins) reach this module as
``PadExtras``, which ``lens.altium`` reads: this package never imports a KiCad backend.
"""

from __future__ import annotations

import struct
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

import fenolite.backends.altium.pcbrecords as rec
from fenolite.backends.altium.ascii import text_problem
from fenolite.backends.altium.cfb import Entry, Storage, name_key, write_compound
from fenolite.backends.altium.libboard import board_text, guid
from fenolite.backends.altium.schlib import storage_name
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import Graphic, Pad
from fenolite.model.library import FootprintDef

MAX_TEXT = 255
LIBRARY_HEADER_TEXT = "PCB 6.0 Binary Library File"
"""The text of ``FileHeader``."""
LIBRARY_VERSION = 5.01
"""The double after the text of ``FileHeader``."""
DEFAULT_FILENAME = "Fenolite.PcbLib"
UNIQUE_STORAGE = "UniqueIDPrimitiveInformation"
"""Altium's spelling of the per-footprint storage of unique ids."""
HEIGHT = "0mil"
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-PCB-GRAPHICS",
        "H-A-PCB-KICAD-LIB",
        "H-A-PCB-LIB-NAME",
        "H-A-PCB-LIB-OPEN",
        "H-A-PCB-PAD",
    ),
)
"""The library file is inferred from public sources; the kicad-cli oracle checks only what KiCad reads."""
COPPER_WILDCARDS = ("*.Cu", "F&B.Cu")


@dataclass(frozen=True, slots=True)
class PadExtras:
    """What ``lens.altium.pad_extras`` reads from a pad's KiCad-only children: the corner ratio of a rounded
    rectangle, a reason to refuse the pad, and settings Altium's pad record has no field for."""

    corner_ratio: Decimal | None = None
    refusal: str | None = None
    dropped: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LibFootprint:
    """One footprint to write: the definition, its pad extras by pad id, and its number of texts."""

    defn: FootprintDef
    extras: Mapping[str, PadExtras] = field(default_factory=lambda: {})
    texts: int = 0


@dataclass(frozen=True, slots=True)
class FootprintCheck:
    """The outcome of ``check_footprint``: a refusal, or the pads and graphics to write with what is left
    out (``dropped``, warnings) and what is not written by design (``extras``, infos)."""

    refusal: str | None
    dropped: tuple[str, ...] = ()
    extras: tuple[str, ...] = ()
    pads: tuple[Pad, ...] = ()
    graphics: tuple[Graphic, ...] = ()


def _copper_sides(pad: Pad) -> set[str]:
    layers = set(pad.layers)
    if layers & set(COPPER_WILDCARDS):
        return {"F.Cu", "B.Cu"}
    return layers & {"F.Cu", "B.Cu"}


def _is_copper(layer: str) -> bool:
    return layer.endswith(".Cu")


def _text_refusal(text: str, what: str) -> str | None:
    problem = text_problem(text)
    if problem is not None:
        return f"{what} {text!r} {problem}"
    if len(text.encode("ascii")) > MAX_TEXT:
        return f"{what} {text[:20]!r}… is longer than {MAX_TEXT} bytes"
    return None


def _pad_refusal(pad: Pad, extras: PadExtras) -> str | None:
    where = f"pad {pad.number!r}"
    if (problem := _text_refusal(pad.number, "the pad number")) is not None:
        return problem
    if pad.shape in ("trapezoid", "custom"):
        return f"{where} has the shape {pad.shape}, which has no exact Altium form"
    if pad.kind == "connect":
        return f"{where} is a connector pad (kind connect)"
    if pad.padstack is not None:
        return f"{where} has a per-layer padstack"
    if extras.refusal is not None:
        return f"{where}: {extras.refusal}"
    sides = _copper_sides(pad)
    if pad.kind in ("thru_hole", "np_thru_hole"):
        if pad.drill is None or pad.drill <= 0:
            return f"{where} has no round drill (a slot or an oval hole)"
        if len(sides) == 1:
            return f"{where} is a through-hole pad with copper on one side only"
    elif not sides:
        return f"{where} is a surface pad without a copper layer"
    if pad.shape == "roundrect" and extras.corner_ratio is None:
        return f"{where} is a rounded rectangle without a corner ratio"
    return None


def _pad_drops(pad: Pad, extras: PadExtras) -> list[str]:
    layers = set(pad.layers)
    found = [f"pad {pad.number} {item}" for item in extras.dropped]
    if pad.kind == "smd":
        side = "F" if "F.Cu" in layers else "B"
        for kind in ("Mask", "Paste"):
            if f"{side}.{kind}" not in layers:
                found.append(f"pad {pad.number} without {side}.{kind}")
    elif pad.kind == "thru_hole" and not layers & {"*.Mask", "F&B.Mask", "F.Mask", "B.Mask"}:
        found.append(f"pad {pad.number} without a solder mask opening")
    return found


def _graphic_drop(graphic: Graphic) -> str | None:
    if rec.LAYER_MAP.get(graphic.layer) not in rec.FLIP_PAIRS:  # unmapped, or an inner copper layer
        return f"{graphic.kind} on {graphic.layer}"
    if graphic.kind == "polygon":
        return f"{'filled ' if graphic.filled else ''}polygon on {graphic.layer}"
    if graphic.filled and graphic.kind in ("rect", "circle"):
        return f"filled {graphic.kind} on {graphic.layer}"
    if graphic.kind == "arc":
        start, mid, end = graphic.points
        try:
            rec.arc_from_points(start, mid, end)
        except ValueError:
            return f"degenerate arc on {graphic.layer}"
    if graphic.kind == "circle" and graphic.points[0] == graphic.points[1]:
        return f"circle of zero radius on {graphic.layer}"
    return None


def check_footprint(defn: FootprintDef, extras: Mapping[str, PadExtras], *, texts: int = 0) -> FootprintCheck:
    """Refuse ``defn`` (a reason naming the pad or graphic) or list what is written, dropped and extra."""
    if (problem := _text_refusal(defn.name, "the footprint name")) is not None:
        return FootprintCheck(problem)
    dropped: list[str] = []
    for pad in defn.pads:
        pad_extras = extras.get(pad.id, PadExtras())
        refusal = _pad_refusal(pad, pad_extras)
        if refusal is not None:
            return FootprintCheck(refusal)
        dropped += _pad_drops(pad, pad_extras)
    graphics: list[Graphic] = []
    for graphic in defn.graphics:
        if _is_copper(graphic.layer):
            return FootprintCheck(f"a {graphic.kind} lies on the copper layer {graphic.layer}")
        drop = _graphic_drop(graphic)
        if drop is None:
            graphics.append(graphic)
        else:
            dropped.append(drop)
    notes: list[str] = []
    if texts:
        notes.append(f"{texts} text(s)")
    if defn.properties:
        notes.append(f"{len(defn.properties)} propert{'y' if len(defn.properties) == 1 else 'ies'}")
    if defn.models:
        notes.append(f"{len(defn.models)} 3D model link(s)")
    return FootprintCheck(None, tuple(dropped), tuple(notes), defn.pads, tuple(graphics))


Frame = Callable[[Point], Point]
"""A footprint point (nanometres, KiCad's Y-down frame) → its point in nanometres in the Y-up frame."""


def library_frame(point: Point) -> Point:
    """A library footprint's own frame: Y negated."""
    return Point(point.x, -point.y)


def _units(point: Point) -> tuple[int, int]:
    return rec.to_units(point.x), rec.to_units(point.y)


def graphic_records(
    graphic: Graphic,
    frame: Frame = library_frame,
    *,
    flip: bool = False,
    component: int = rec.NO_INDEX,
) -> list[bytes]:
    """The tracks or arc of one kept graphic: a line one track, a rectangle four tracks, a circle one arc
    from 0 to 360 degrees, an arc rebuilt from its three points in ``frame``. ``flip`` swaps the layer."""
    layer = rec.LAYER_MAP[graphic.layer]
    if flip:
        layer = rec.FLIP_PAIRS[layer]
    width = rec.to_units(graphic.width)
    points = graphic.points
    if graphic.kind == "line":
        a, b = points
        return [rec.track_record(layer, _units(frame(a)), _units(frame(b)), width, component=component)]
    if graphic.kind == "rect":
        s, e = points
        corners = [s, Point(e.x, s.y), e, Point(s.x, e.y)]
        mapped = [_units(frame(p)) for p in corners]
        return [
            rec.track_record(layer, mapped[i], mapped[(i + 1) % 4], width, component=component)
            for i in range(4)
        ]
    if graphic.kind == "circle":
        centre, on_circle = points
        arc = rec.circle_geometry(frame(centre), frame(on_circle))
        return [rec.arc_record(layer, arc, width, component=component)]
    if graphic.kind == "arc":
        start, mid, end = (frame(p) for p in points)
        return [rec.arc_record(layer, rec.arc_from_points(start, mid, end), width, component=component)]
    raise ValueError(f"a {graphic.kind} graphic has no written form")


def pad_layer(pad: Pad) -> int:
    """74 for a through-hole pad; 1 or 32 for a surface pad, by its copper layer."""
    if pad.kind in ("thru_hole", "np_thru_hole"):
        return rec.MULTI_LAYER
    return rec.LAYER_MAP["F.Cu"] if "F.Cu" in _copper_sides(pad) else rec.LAYER_MAP["B.Cu"]


def pad_bytes(
    pad: Pad,
    extras: PadExtras,
    *,
    at: Point,
    rotation_udeg: int,
    flip: bool = False,
    net: int = rec.NO_INDEX,
    component: int = rec.NO_INDEX,
) -> bytes:
    """One pad record at ``at`` (nanometres, Y-up frame) with ``rotation_udeg``; ``flip`` swaps its layer."""
    layer = pad_layer(pad)
    if flip:
        layer = rec.FLIP_PAIRS[layer]
    corner = None
    if pad.shape == "roundrect":
        assert extras.corner_ratio is not None
        corner = rec.corner_percent(extras.corner_ratio)
    hole = rec.to_units(pad.drill) if pad.kind in ("thru_hole", "np_thru_hole") and pad.drill else 0
    return rec.pad_record(
        name=pad.number,
        layer=layer,
        x=rec.to_units(at.x),
        y=rec.to_units(at.y),
        size=(rec.to_units(pad.size.w), rec.to_units(pad.size.h)),
        shape=rec.PAD_SHAPES[pad.shape],
        rotation=rec.degrees_of(rotation_udeg),
        hole=hole,
        plated=pad.kind == "thru_hole",
        corner=corner,
        net=net,
        component=component,
    )


def _u32(value: int) -> bytes:
    return struct.pack("<I", value)


def _counted(text: str) -> bytes:
    """A text of ``FileHeader``: a 32-bit length and a length byte that both hold the text length."""
    data = text.encode("ascii")
    return _u32(len(data)) + bytes((len(data),)) + data


def _file_header(filename: str) -> bytes:
    """53 bytes: the header text, the version double and the library's eight-letter id."""
    from fenolite.backends.altium.project import unique_id  # project imports this module

    return (
        _counted(LIBRARY_HEADER_TEXT)
        + struct.pack("<d", LIBRARY_VERSION)
        + _counted(unique_id(f"pcblib:{filename}"))
    )


def _section_keys(keyed: list[tuple[str, str]]) -> bytes:
    out = struct.pack("<i", len(keyed))
    for full, key in keyed:
        text = full.encode("ascii") + b"\0"
        out += _u32(len(text)) + text + rec.string_block(key)
    return out


def _parameters(defn: FootprintDef) -> bytes:
    fields: list[tuple[str, str]] = [
        ("PATTERN", defn.name),
        ("HEIGHT", HEIGHT),
        ("DESCRIPTION", _description(defn)),
        ("ITEMGUID", ""),
        ("REVISIONGUID", ""),
    ]
    return rec.property_block(fields)


def _description(defn: FootprintDef) -> str:
    """The description, or the empty text when there is none or it is not printable 7-bit ASCII."""
    text = defn.description or ""
    return text if text and text_problem(text) is None else ""


def _params_toc(footprints: Sequence[LibFootprint]) -> bytes:
    """``ComponentParamsTOC/Data``: one line per footprint, CR LF ended, then the NUL the length counts."""
    lines = "".join(
        f"Name={f.defn.name}|Pad Count={len(f.defn.pads)}|Height=0|Description={_description(f.defn)}\r\n"
        for f in footprints
    )
    data = lines.encode("ascii") + b"\0"
    return _u32(len(data)) + data


def _used_layers(footprints: Sequence[LibFootprint]) -> set[int]:
    """The layer ids the written primitives lie on (the layer byte of each record's common prefix)."""
    used: set[int] = set()
    for footprint in footprints:
        for kind, record in footprint_primitives(footprint):
            body = record[1:]
            if kind == "Pad":
                for _ in range(4):
                    (length,) = struct.unpack_from("<I", body)
                    body = body[4 + length :]
            used.add(body[4])
    return used


def _library_storage(filename: str, footprints: Sequence[LibFootprint]) -> Storage:
    """The ``Library`` storage: the board record with the name list, and the side streams Altium saves."""
    names = b"".join(rec.string_block(f.defn.name) for f in footprints)
    data = rec.text_block(board_text(filename, _used_layers(footprints))) + _u32(len(footprints)) + names
    empty: tuple[Entry, ...] = (("Header", _u32(0)), ("Data", b""))
    pad_via = rec.property_block(
        (
            ("PADVIALIBRARY.LIBRARYID", guid(f"padvia:{filename}")),
            ("PADVIALIBRARY.LIBRARYNAME", "<Local>"),
            ("PADVIALIBRARY.DISPLAYUNITS", "1"),
        )
    )
    return Storage(
        "Library",
        (
            ("Header", _u32(1)),
            ("Data", data),
            ("EmbeddedFonts", _u32(0)),
            Storage("Models", empty),
            Storage("ModelsNoEmbed", empty),
            Storage("Textures", empty),
            Storage("ComponentParamsTOC", (("Header", _u32(1)), ("Data", _params_toc(footprints)))),
            Storage("PadViaLibrary", (("Header", _u32(0)), ("Data", pad_via))),
        ),
    )


def footprint_primitives(footprint: LibFootprint) -> list[tuple[str, bytes]]:
    """``(object id, record)`` of each written primitive: the pads in definition order, then the tracks and
    arcs in graphic order; ``ValueError`` for a refused footprint."""
    check = check_footprint(footprint.defn, footprint.extras, texts=footprint.texts)
    if check.refusal is not None:
        raise ValueError(f"{footprint.defn.name}: {check.refusal}")
    out: list[tuple[str, bytes]] = []
    for pad in check.pads:
        extras = footprint.extras.get(pad.id, PadExtras())
        out.append(
            ("Pad", pad_bytes(pad, extras, at=library_frame(pad.position), rotation_udeg=pad.rotation))
        )
    for graphic in check.graphics:
        for record in graphic_records(graphic):
            out.append(("Track" if record[0] == rec.TRACK else "Arc", record))
    return out


def _footprint_storage(key: str, footprint: LibFootprint) -> Storage:
    from fenolite.backends.altium.project import unique_id  # project imports this module

    defn = footprint.defn
    primitives = footprint_primitives(footprint)
    unique = b"".join(
        rec.property_block(
            (
                ("PRIMITIVEINDEX", str(index)),
                ("PRIMITIVEOBJECTID", kind),
                ("UNIQUEID", unique_id(f"pcblib:{defn.name}:{index}")),
            )
        )
        for index, (kind, _record) in enumerate(primitives)
    )
    entries: tuple[Entry, ...] = (
        ("Header", _u32(len(primitives))),
        ("Parameters", _parameters(defn)),
        ("WideStrings", rec.EMPTY_PROPERTY_BLOCK),
        ("Data", rec.string_block(defn.name) + b"".join(record for _kind, record in primitives)),
        Storage(UNIQUE_STORAGE, (("Header", _u32(len(primitives))), ("Data", unique))),
    )
    return Storage(key, entries)


def write_pcblib(footprints: Sequence[LibFootprint], *, filename: str = DEFAULT_FILENAME) -> bytes:
    """The bytes of one PCB library holding ``footprints`` (``pcb-library.md``, "Fenolite's choices").
    ``filename`` is the library's file name without a folder: the board record's ``FILENAME`` and the key
    of the library's ids. ``ValueError`` for a refused footprint, two equal storage names or a file name
    that cannot be written; ``cfb.CompoundTooLarge`` past the size limit."""
    if (problem := _text_refusal(filename, "the library file name")) is not None:
        raise ValueError(problem)
    if "/" in filename or "\\" in filename:
        raise ValueError(f"the library file name {filename!r} holds a folder")
    keyed: dict[tuple[int, tuple[int, ...]], tuple[str, LibFootprint]] = {}
    for footprint in footprints:
        key = storage_name(footprint.defn.name)
        order = name_key(key)
        if order in keyed:
            other = keyed[order][1].defn.name
            raise ValueError(
                f"the footprints {other!r} and {footprint.defn.name!r} get one storage name {key!r}"
            )
        keyed[order] = (key, footprint)
    ordered = [keyed[order] for order in sorted(keyed)]
    entries: list[Entry] = [("FileHeader", _file_header(filename))]
    section = [(f.defn.name, key) for key, f in ordered if key != f.defn.name]
    if section:
        entries.append(("SectionKeys", _section_keys(section)))
    entries.append(_library_storage(filename, [f for _key, f in ordered]))
    entries += [_footprint_storage(key, footprint) for key, footprint in ordered]
    return write_compound(entries)


__all__ = [
    "EVIDENCE",
    "DEFAULT_FILENAME",
    "LIBRARY_HEADER_TEXT",
    "LIBRARY_VERSION",
    "UNIQUE_STORAGE",
    "FootprintCheck",
    "Frame",
    "LibFootprint",
    "PadExtras",
    "check_footprint",
    "footprint_primitives",
    "graphic_records",
    "library_frame",
    "pad_bytes",
    "pad_layer",
    "write_pcblib",
]
