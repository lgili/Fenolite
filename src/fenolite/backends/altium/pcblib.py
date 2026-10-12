# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium PCB library (``.PcbLib``) of the Altium writer (change c0035, capability altium-pcb-writer,
"Footprint content checks", "Footprint line and arc records" and "PCB library file"; change c0121,
"Component bodies of a library footprint").

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
from fenolite.geometry.transform import FULL_TURN
from fenolite.model.board import ComponentBody, Graphic, Pad, PadstackLayer
from fenolite.model.library import FootprintDef

MAX_TEXT = 255
PLAIN_PAD_SHAPES = ("circle", "oval", "rect", "roundrect")
"""The model shapes one layer of a pad stack may carry and be written exactly (``rec.PAD_SHAPES``); any
other shape (``custom``, ``trapezoid``) keeps the pad a loss (change c0160)."""
INNER_WILDCARD = "In*.Cu"
INNER_WILDCARDS = frozenset({"In*.Cu", "Inner"})
"""The two spellings of the wildcard for every inner copper layer: the model's own ``In*.Cu`` (what the
Altium reader writes) and ``Inner`` (the layer a KiCad file writes, kept by the KiCad reader)."""
LIBRARY_HEADER_TEXT = "PCB 6.0 Binary Library File"
"""The text of ``FileHeader``."""
LIBRARY_VERSION = 5.01
"""The double after the text of ``FileHeader``."""
DEFAULT_FILENAME = "Fenolite.PcbLib"
UNIQUE_STORAGE = "UniqueIDPrimitiveInformation"
"""Altium's spelling of the per-footprint storage of unique ids."""
HEIGHT = "0mil"
BODY_OBJECT = "Body"
"""The kind of a component body among the primitives of ``footprint_primitives``."""
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-CONV-DIFAT",
        "H-A-CONV-LIBRARY",
        "H-A-CONV-PADSTACK",
        "H-A-PCB-GRAPHICS",
        "H-A-PCB-KICAD-LIB",
        "H-A-PCBX-BODY-FORM",
        "H-A-PCBX-BODY-LIB",
        "H-A-PCB-LIB-NAME",
        "H-A-PCB-LIB-OPEN",
        "H-A-PCB-PAD",
    ),
)
"""The library file is inferred from public sources; the kicad-cli oracle checks only what KiCad reads.
A body of a library footprint (change c0121) is written in the form of a document's body: no extruded
body of a saved library was read (``H-A-PCBX-BODY-LIB``)."""
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
    """One footprint to write: the definition, its pad extras by pad id, and its number of texts.
    ``bodies`` (change c0121) are the component bodies to write into the library with it: empty, the value
    of every write with ``bodies="off"`` (``--altium-bodies off``), or the bodies of the definition."""

    defn: FootprintDef
    extras: Mapping[str, PadExtras] = field(default_factory=lambda: {})
    texts: int = 0
    bodies: tuple[ComponentBody, ...] = ()
    extra_primitives: tuple[tuple[str, bytes], ...] = ()
    """Additional graphics and texts encoded by the model writer in the library frame (c0160)."""
    wide_strings: bytes = rec.EMPTY_PROPERTY_BLOCK


@dataclass(frozen=True, slots=True)
class FootprintCheck:
    """The outcome of ``check_footprint``: a refusal, or the pads and graphics to write with what is left
    out (``dropped``, warnings) and what is not written by design (``extras``, infos)."""

    refusal: str | None
    dropped: tuple[str, ...] = ()
    extras: tuple[str, ...] = ()
    pads: tuple[Pad, ...] = ()
    graphics: tuple[Graphic, ...] = ()
    bodies: tuple[ComponentBody, ...] = ()
    """The component bodies that are written (change c0121)."""


BODY_IS_MODEL = "a body that names a 3D model needs the model's data, which the model does not hold"
BODY_NO_OUTLINE = "the body has no outline"


def _mm(nm: int) -> str:
    text = format(Decimal(nm) / Decimal(1_000_000), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def body_problem(body: ComponentBody) -> str | None:
    """Why ``body`` has no record, or ``None`` (capability altium-pcb-writer, "Component bodies are
    reported"; ``pcb-bodies.md``, "What is not written"): the kind ``model``; an outline of fewer than three
    distinct points; a standoff below the board surface, which no saved extruded body holds; a height that
    is not above the standoff in the units of the record. It reads ``kind``, ``outline``, ``height`` and
    ``standoff`` as the model holds them and no other field."""
    if body.kind != "extruded":
        return BODY_IS_MODEL
    if len(set(body.outline)) < 3:
        return BODY_NO_OUTLINE
    if body.standoff < 0:
        return f"its standoff of {_mm(body.standoff)} mm lies below the board surface"
    if rec.to_units(body.height) <= rec.to_units(body.standoff):
        return f"its height of {_mm(body.height)} mm is not above its standoff of {_mm(body.standoff)} mm"
    return None


def library_body_vertices(body: ComponentBody) -> list[tuple[int, int]]:
    """The outline of ``body`` in the library's frame as whole units, without a point that equals the one
    before it and without a last point that repeats the first."""
    vertices: list[tuple[int, int]] = []
    for point in body.outline:
        vertex = _units(library_frame(point))
        if not vertices or vertices[-1] != vertex:
            vertices.append(vertex)
    while len(vertices) > 1 and vertices[-1] == vertices[0]:
        vertices.pop()
    return vertices


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


def _pad_part(layer: PadstackLayer, corner: int | None) -> rec.PadPart:
    """The record part of one layer of a padstack; ``ValueError`` names a shape with no exact form."""
    if layer.shape not in PLAIN_PAD_SHAPES:
        raise ValueError(f"gives the layer {layer.layer} the shape {layer.shape}, which has no exact form")
    return rec.PadPart(
        rec.PAD_SHAPES[layer.shape],
        (rec.to_units(layer.size.w), rec.to_units(layer.size.h)),
        corner if layer.shape == "roundrect" else None,
    )


def pad_stack(pad: Pad, *, corner: int | None, copper_layers: Sequence[str] = ()) -> rec.PadStack | None:
    """The record stack of ``pad``: ``None`` when it gives one shape to every copper layer, else the mode
    (1 Top-Middle-Bottom when the inner layers share one shape and size, 2 Full Stack otherwise) and its
    parts (change c0160; ``pcb-library.md``, "Pad records of a written footprint").

    ``copper_layers`` is the board's copper layers in stack order for a document, empty for a library
    footprint, whose inner layers are the wildcard ``In*.Cu`` of a mode 1 stack or the ``In<k>.Cu`` a mode 2
    stack names. ``ValueError`` names a layer the stack leaves out and a shape with no exact form.
    """
    stack = pad.padstack
    if stack is None or not stack.layers:
        return None
    by_layer = {layer.layer: layer for layer in stack.layers}
    top, bottom = by_layer.get("F.Cu"), by_layer.get("B.Cu")
    if top is None or bottom is None:
        raise ValueError("gives no F.Cu or B.Cu part to its per-layer stack")
    top_part, bottom_part = _pad_part(top, corner), _pad_part(bottom, corner)
    wildcard = next((by_layer[name] for name in INNER_WILDCARDS if name in by_layer), None)
    if wildcard is not None and not copper_layers:
        mid = _pad_part(wildcard, corner)
        return rec.PadStack(rec.PAD_MODE_TOP_MID_BOTTOM, top_part, mid, bottom_part)
    names = (
        list(copper_layers[1:-1])
        if copper_layers
        else [layer.layer for layer in stack.layers if layer.layer not in ("F.Cu", "B.Cu")]
    )
    parts: list[rec.PadPart] = []
    for name in names:
        layer = by_layer.get(name, wildcard) if copper_layers else by_layer[name]
        if layer is None:
            raise ValueError(f"names no layer for {name}")
        parts.append(_pad_part(layer, corner))
    if not parts:
        # No inner layer holds the pad (a two-layer board): the top and bottom parts alone. When they
        # share one shape and size there is nothing to write, else it is a mode 1 stack without a middle.
        if (top_part.shape, top_part.size) == (bottom_part.shape, bottom_part.size):
            return None
        return rec.PadStack(rec.PAD_MODE_TOP_MID_BOTTOM, top_part, top_part, bottom_part)
    mid = parts[0]
    if all((part.shape, part.size) == (mid.shape, mid.size) for part in parts):
        return rec.PadStack(rec.PAD_MODE_TOP_MID_BOTTOM, top_part, mid, bottom_part)
    return rec.PadStack(rec.PAD_MODE_FULL, top_part, mid, bottom_part, inner=tuple(parts))


def pad_hole(pad: Pad) -> tuple[int, int, float]:
    """The hole shape of ``pad``, the slot length in record units and the slot rotation in degrees: the
    three fields of a hole that is not round (change c0160; ``pcb-records.md``, "Pad"). The rotation is
    relative to the pad, which is what the reader adds the pad's own angle to."""
    stack = pad.padstack
    if stack is None or stack.hole_shape == "round":
        return rec.HOLE_SHAPE_ROUND, 0, 0.0
    if stack.hole_shape == "square":
        return rec.HOLE_SHAPE_SQUARE, 0, 0.0
    length = rec.to_units(stack.hole_length) if stack.hole_length else rec.to_units(pad.drill or 0)
    rotation = rec.degrees_of((stack.hole_rotation - pad.rotation) % FULL_TURN)
    return rec.HOLE_SHAPE_SLOT, length, rotation


def _pad_refusal(pad: Pad, extras: PadExtras, *, copper_layers: Sequence[str] = ()) -> str | None:
    where = f"pad {pad.number!r}"
    if pad.number and (problem := _text_refusal(pad.number, "the pad number")) is not None:
        return problem
    if pad.shape in ("trapezoid", "custom"):
        return f"{where} has the shape {pad.shape}, which has no exact Altium form"
    if extras.refusal is not None:
        return f"{where}: {extras.refusal}"
    try:
        pad_stack(pad, corner=None, copper_layers=copper_layers)
    except ValueError as error:
        return f"{where} {error}"
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


def check_footprint(
    defn: FootprintDef,
    extras: Mapping[str, PadExtras],
    *,
    texts: int = 0,
    bodies: Sequence[ComponentBody] = (),
    copper_layers: Sequence[str] = (),
) -> FootprintCheck:
    """Refuse ``defn`` (a reason naming the pad or graphic) or list what is written, dropped and extra.
    ``bodies`` (change c0121) are the component bodies asked for: one that ``body_problem`` passes and that
    keeps three vertices in the library's units is written; each other body of ``bodies`` and of the
    definition is counted in the notes. ``copper_layers`` (change c0160) is the board's copper layers in
    stack order when the footprint is written into a document, and empty in a library."""
    if (problem := _text_refusal(defn.name, "the footprint name")) is not None:
        return FootprintCheck(problem)
    dropped: list[str] = []
    kept: list[Pad] = []
    for pad in defn.pads:
        pad_extras = extras.get(pad.id, PadExtras())
        refusal = _pad_refusal(pad, pad_extras, copper_layers=copper_layers)
        if refusal is not None:
            return FootprintCheck(refusal)
        if not pad.number:
            dropped.append("the pad has no number, which a library footprint cannot hold (change c0160)")
            continue
        kept.append(pad)
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
    written = tuple(
        body for body in bodies if body_problem(body) is None and len(library_body_vertices(body)) >= 3
    )
    ids = {body.id for body in written}
    unwritten = sum(1 for body in {b.id: b for b in (*defn.bodies, *bodies)}.values() if body.id not in ids)
    if unwritten:
        notes.append(f"{unwritten} component bod{'y' if unwritten == 1 else 'ies'}")
    return FootprintCheck(None, tuple(dropped), tuple(notes), tuple(kept), tuple(graphics), written)


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
    copper_layers: Sequence[str] = (),
) -> bytes:
    """One pad record at ``at`` (nanometres, Y-up frame) with ``rotation_udeg``; ``flip`` swaps its layer.
    ``copper_layers`` (change c0160) is the board's copper layers in stack order for a document, empty in a
    library; the pad's per-layer stack and a hole that is not round are written from it."""
    layer = pad_layer(pad)
    if flip:
        layer = rec.FLIP_PAIRS[layer]
    corner = None
    if pad.shape == "roundrect":
        assert extras.corner_ratio is not None
        corner = rec.corner_percent(extras.corner_ratio)
    stack = pad_stack(pad, corner=corner, copper_layers=copper_layers)
    hole_shape, slot_length, slot_rotation = pad_hole(pad)
    hole = rec.to_units(pad.drill) if pad.kind in ("thru_hole", "np_thru_hole") and pad.drill else 0
    # A connector pad has copper only: no paste and no mask opening, so neither mask takes the rule's
    # expansion (change c0160; ``pcb-library.md``, "Pad records of a written footprint", U1 and U2).
    solder_mode = rec.PAD_EXPANSION_NONE if pad.kind == "connect" else rec.SOLDER_FROM_RULES
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
        stack=stack,
        hole_shape=hole_shape,
        slot_length=slot_length,
        slot_rotation=slot_rotation,
        solder_mode=solder_mode,
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
    arcs in graphic order, then the component bodies of ``footprint.bodies`` that are written (change
    c0121; ``pcb-bodies.md``, "Library": the document's form with no component, in the library's frame);
    ``ValueError`` for a refused footprint."""
    check = check_footprint(footprint.defn, footprint.extras, texts=footprint.texts, bodies=footprint.bodies)
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
    out.extend(footprint.extra_primitives)
    for body in check.bodies:
        record = rec.body_record(
            rec.body_layer(body.layer, bottom=False),
            library_body_vertices(body),
            component=rec.NO_INDEX,
            standoff=rec.to_units(body.standoff),
            overall=rec.to_units(body.height),
            bottom=False,
            identifier=body.name,
            model_id=rec.body_model_id(body.id),
        )
        out.append((BODY_OBJECT, record))
    return out


def _footprint_storage(key: str, footprint: LibFootprint) -> Storage:
    from fenolite.backends.altium.project import unique_id  # project imports this module

    defn = footprint.defn
    primitives = footprint_primitives(footprint)
    # a body has no entry in the list of unique ids: the one saved library with a body lists its pads only
    listed = [kind for kind, _record in primitives if kind != BODY_OBJECT]
    unique = b"".join(
        rec.property_block(
            (
                ("PRIMITIVEINDEX", str(index)),
                ("PRIMITIVEOBJECTID", kind),
                ("UNIQUEID", unique_id(f"pcblib:{defn.name}:{index}")),
            )
        )
        for index, kind in enumerate(listed)
    )
    entries: tuple[Entry, ...] = (
        ("Header", _u32(len(primitives))),
        ("Parameters", _parameters(defn)),
        ("WideStrings", footprint.wide_strings),
        ("Data", rec.string_block(defn.name) + b"".join(record for _kind, record in primitives)),
        Storage(UNIQUE_STORAGE, (("Header", _u32(len(listed))), ("Data", unique))),
    )
    return Storage(key, entries)


def write_pcblib(
    footprints: Sequence[LibFootprint],
    *,
    filename: str = DEFAULT_FILENAME,
    disambiguate_storages: bool = False,
) -> bytes:
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
        if order in keyed and disambiguate_storages:
            if any(f.defn.name == footprint.defn.name for _, f in keyed.values()):
                raise ValueError(f"duplicate footprint name {footprint.defn.name!r}")
            index = 2
            while order in keyed:
                suffix = f"_{index}"
                key = storage_name(footprint.defn.name)[: 31 - len(suffix)] + suffix
                order = name_key(key)
                index += 1
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
    "BODY_IS_MODEL",
    "BODY_NO_OUTLINE",
    "BODY_OBJECT",
    "EVIDENCE",
    "DEFAULT_FILENAME",
    "LIBRARY_HEADER_TEXT",
    "LIBRARY_VERSION",
    "UNIQUE_STORAGE",
    "FootprintCheck",
    "Frame",
    "LibFootprint",
    "PadExtras",
    "body_problem",
    "check_footprint",
    "footprint_primitives",
    "graphic_records",
    "library_body_vertices",
    "library_frame",
    "pad_bytes",
    "pad_layer",
    "write_pcblib",
]
