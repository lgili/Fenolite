# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Builders of in-memory records of the Altium readers, for the tests of the import adapter (change c0043).

The adapter reads typed attributes of records, so a test can build the records directly: no byte is framed
here. Property records go through the readers' own typed views (``read_board``, ``component_record`` …), so
that a builder cannot disagree with the reader. Every value is authored for Fenolite.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from fenolite.backends.altium.read.pcb import (
    EVIDENCE,
    ClassRecord,
    ComponentRecord,
    NetRecord,
    PcbDocument,
    PolygonRecord,
    RuleRecord,
    class_record,
    component_record,
    net_record,
    polygon_record,
    rule_record,
)
from fenolite.backends.altium.read.pcbprims import (
    ArcRecord,
    FillRecord,
    PadRecord,
    Prefix,
    Primitive,
    RegionRecord,
    RegionVertex,
    TextRecord,
    TrackRecord,
    ViaRecord,
)
from fenolite.backends.altium.read.pcbprops import PropertyRecord
from fenolite.backends.altium.read.pcbstack import BoardRecord, KeyReader, read_board

MIL = 10_000
"""Units of 1/10 000 mil in one mil."""
SHA = "0" * 64
ZERO = " 0.00000000000000E+0000"


def props(fields: Mapping[str, str] | Sequence[tuple[str, str]], lead: bytes = b"") -> PropertyRecord:
    items = tuple(fields.items()) if isinstance(fields, Mapping) else tuple(fields)
    return PropertyRecord(b"", items, lead)


def prefix(
    layer: int = 1, *, net: int | None = None, component: int | None = None, polygon: int | None = None
) -> Prefix:
    return Prefix(layer, 0, 0, net, polygon, component, False)


def board(
    chain: Sequence[int] = (1, 32),
    *,
    outline: Sequence[tuple[int, int]] = ((0, 0), (1000, 0), (1000, 800), (0, 800)),
    extra: Mapping[str, str] | None = None,
    stack: bool = False,
) -> BoardRecord:
    """A board record whose copper chain is ``chain`` (layer ids) and whose outline is ``outline`` (mil)."""
    fields: dict[str, str] = {"ORIGINX": "1000mil", "ORIGINY": "1000mil"}
    for k, (x, y) in enumerate((*outline, outline[0]) if outline else ()):
        fields |= {f"KIND{k}": "0", f"VX{k}": f"{x}mil", f"VY{k}": f"{y}mil"}
    highest = max([*chain, 32, 74])
    links = {layer: (chain[i - 1] if i else 0, chain[i + 1] if i + 1 < len(chain) else 0) for i, layer in
             enumerate(chain)}  # fmt: skip
    for layer in range(1, highest + 1):
        fields[f"LAYER{layer}NAME"] = f"Layer {layer}"
        before, after = links.get(layer, (0, 0))
        fields[f"LAYER{layer}PREV"] = str(before)
        fields[f"LAYER{layer}NEXT"] = str(after)
        fields[f"LAYER{layer}COPTHICK"] = "1.4mil"
        fields[f"LAYER{layer}DIELCONST"] = "4.800"
        fields[f"LAYER{layer}DIELHEIGHT"] = "12.6mil"
        fields[f"LAYER{layer}DIELMATERIAL"] = "FR-4"
    if stack:
        entry = 0
        for position, layer in enumerate(chain):
            long_id = 0x0100FFFF if layer == 32 else ((0x0101 << 16) | (layer - 38) if layer >= 39 else
                                                      (0x0100 << 16) | layer)  # fmt: skip
            fields |= {f"V9_STACK_LAYER{entry}_NAME": f"Layer {layer}", f"V9_STACK_LAYER{entry}_LAYERID":
                       str(long_id), f"V9_STACK_LAYER{entry}_COPTHICK": "1.4mil"}  # fmt: skip
            entry += 1
            if position + 1 < len(chain):
                fields |= {
                    f"V9_STACK_LAYER{entry}_NAME": f"Dielectric {position + 1}",
                    f"V9_STACK_LAYER{entry}_LAYERID": str((0x0104 << 16) | (position + 1)),
                    f"V9_STACK_LAYER{entry}_DIELCONST": "4.800",
                    f"V9_STACK_LAYER{entry}_DIELHEIGHT": "12.6mil",
                    f"V9_STACK_LAYER{entry}_DIELMATERIAL": "FR-4",
                }
                entry += 1
    fields |= dict(extra or {})
    found, _issues = read_board(props(fields), where="Board6/Data#0")
    return found


def net(name: str) -> NetRecord:
    return net_record(props({"NAME": name}))


def component(
    ref: str = "R1",
    *,
    x: str = "2000mil",
    y: str = "1500mil",
    rotation: float = 0.0,
    layer: str = "TOP",
    pattern: str = "R_0603",
    unique_id: str = "",
    source_unique_id: str = "",
    extra: Mapping[str, str] | None = None,
) -> ComponentRecord:
    fields = {
        "LAYER": layer,
        "X": x,
        "Y": y,
        "ROTATION": f"{rotation:.14E}",
        "PATTERN": pattern,
        "LOCKED": "FALSE",
        "SOURCEDESIGNATOR": ref,
        "SOURCEUNIQUEID": source_unique_id,
        "SOURCEFOOTPRINTLIBRARY": "Parts.PcbLib",
        "UNIQUEID": unique_id or f"UID{ref}",
    } | dict(extra or {})
    record = props(fields)
    return component_record(record, KeyReader(record, "Components6/Data"))


def net_class(name: str, members: Sequence[str], *, kind: int = 0, superclass: bool = False) -> ClassRecord:
    fields = {"NAME": name, "KIND": str(kind), "SUPERCLASS": "TRUE" if superclass else "FALSE"}
    fields |= {f"M{i}": member for i, member in enumerate(members)}
    record = props(fields)
    return class_record(record, KeyReader(record, "Classes6/Data"))


def polygon(
    vertices: Sequence[tuple[int, int]] = ((100, 100), (900, 100), (900, 700), (100, 700)),
    *,
    layer: str = "TOP",
    net_index: int | None = None,
    name: str = "",
    pour_index: int = 0,
    polygon_type: str = "Polygon",
    extra: Mapping[str, str] | None = None,
) -> PolygonRecord:
    fields = {
        "LAYER": layer,
        "POLYGONTYPE": polygon_type,
        "HATCHSTYLE": "Solid",
        "POURINDEX": str(pour_index),
    }
    for k, (x, y) in enumerate((*vertices, vertices[0])):
        fields |= {f"KIND{k}": "0", f"VX{k}": f"{x}mil", f"VY{k}": f"{y}mil"}
    if name:
        fields["NAME"] = ",".join(str(ord(ch)) for ch in name)
    if net_index is not None:
        fields["NET"] = str(net_index)
    fields |= dict(extra or {})
    record = props(fields)
    return polygon_record(record, KeyReader(record, "Polygons6/Data"))


def rule(kind: str, name: str, **keys: str) -> RuleRecord:
    """A rule record with the header keys of a saved document; ``keys`` add or replace keys."""
    fields = {
        "SELECTION": "FALSE",
        "RULEKIND": kind,
        "NETSCOPE": "DifferentNets" if kind == "Clearance" else "AnyNet",
        "LAYERKIND": "SameLayer",
        "SCOPE1EXPRESSION": "All",
        "SCOPE2EXPRESSION": "All",
        "NAME": name,
        "ENABLED": "TRUE",
        "PRIORITY": "1",
        "COMMENT": "",
        "UNIQUEID": "RULEUID1",
        "DEFINEDBYLOGICALDOCUMENT": "FALSE",
    } | keys
    record = props(fields, lead=b"\x00\x00")
    return rule_record(record, KeyReader(record, "Rules6/Data"))


def track(
    a: tuple[int, int], b: tuple[int, int], width: int = 10 * MIL, layer: int = 1, **owner: int | None
) -> TrackRecord:
    return TrackRecord(b"", prefix(layer, **owner), a[0], a[1], b[0], b[1], width, None, b"")


def arc(
    centre: tuple[int, int],
    radius: int,
    start: float,
    end: float,
    width: int = 10 * MIL,
    layer: int = 1,
    **owner: int | None,
) -> ArcRecord:
    return ArcRecord(b"", prefix(layer, **owner), centre[0], centre[1], radius, start, end, width, None, b"")


def via(
    at: tuple[int, int],
    diameter: int = 50 * MIL,
    hole: int = 28 * MIL,
    start: int = 1,
    end: int = 32,
    **owner: int | None,
) -> ViaRecord:
    return ViaRecord(b"", prefix(74, **owner), at[0], at[1], diameter, hole, start, end, False, False, b"")


def fill(
    a: tuple[int, int], b: tuple[int, int], rotation: float = 0.0, layer: int = 33, **owner: int | None
) -> FillRecord:
    return FillRecord(b"", prefix(layer, **owner), a[0], a[1], b[0], b[1], rotation, b"")


def region(
    points: Sequence[tuple[float, float]], layer: int = 1, holes: int = 0, **owner: int | None
) -> RegionRecord:
    outline = tuple(RegionVertex(float(x), float(y)) for x, y in points)
    hole = tuple(RegionVertex(1.0, 1.0) for _ in range(3))
    return RegionRecord(
        b"", prefix(layer, **owner), holes, props({}), outline, tuple(hole for _ in range(holes)), None,
        False, b"",
    )  # fmt: skip


def text(
    value: str,
    at: tuple[int, int] = (0, 0),
    *,
    layer: int = 33,
    height: int = 60 * MIL,
    designator: bool = False,
    comment: bool = False,
    **owner: int | None,
) -> TextRecord:
    return TextRecord(
        raw=b"", prefix=prefix(layer, **owner), x=at[0], y=at[1], height=height, stroke_font=1, rotation=0.0,
        mirrored=False, stroke_width=6 * MIL, is_comment=comment, is_designator=designator, font_type=0,
        bold=False, italic=False, font_name="", inverted=False, margin=0, wide_index=None, short_text=value,
        text=value, tail=b"",
    )  # fmt: skip


def pad(
    name: str = "1",
    at: tuple[int, int] = (0, 0),
    *,
    size: tuple[int, int] = (60 * MIL, 60 * MIL),
    mid: tuple[int, int] | None = None,
    bottom: tuple[int, int] | None = None,
    hole: int = 0,
    shape: int = 2,
    layer: int = 1,
    rotation: float = 0.0,
    plated: bool = True,
    stack_mode: int = 0,
    hole_shape: int | None = None,
    slot_length: int = 0,
    slot_rotation: float = 0.0,
    offsets: Mapping[int, tuple[int, int]] | None = None,
    alternate: int = 0,
    corner: int = 0,
    inner: Mapping[int, tuple[int, int]] | None = None,
    **owner: int | None,
) -> PadRecord:
    """A pad; the sixth subrecord's fields are set when ``hole_shape``, ``offsets``, ``alternate`` or
    ``inner`` is given. ``offsets`` and ``inner`` are keyed by the table index."""
    full = hole_shape is not None or offsets is not None or alternate or inner is not None
    hole_offsets = tuple((offsets or {}).get(i, (0, 0)) for i in range(32))
    inner_sizes = tuple((inner or {}).get(i, mid or size) for i in range(29))
    return PadRecord(
        raw=b"", name=name, prefix=prefix(layer, **owner), x=at[0], y=at[1], size_top=size,
        size_mid=mid or size, size_bottom=bottom or size, hole=hole, shape_top=shape, shape_mid=shape,
        shape_bottom=shape, rotation=rotation, plated=plated, stack_mode=stack_mode, paste_expansion=0,
        solder_expansion=0, paste_mode=1, solder_mode=1, hole_rotation=0.0,
        inner_sizes=inner_sizes if full else None,
        inner_shapes=tuple(shape for _ in range(29)) if full else None,
        hole_shape=(hole_shape or 0) if full else None,
        slot_length=slot_length if full else None,
        slot_rotation=slot_rotation if full else None,
        hole_offsets=hole_offsets if full else None,
        alternate_shapes=tuple(alternate for _ in range(32)) if full else None,
        corner_percentages=tuple(corner for _ in range(32)) if full else None,
        tail=(b"", b""),
    )  # fmt: skip


def document(
    board_record: BoardRecord | None = None,
    *,
    nets: Sequence[str] = (),
    components: Sequence[ComponentRecord] = (),
    classes: Sequence[ClassRecord] = (),
    rules: Sequence[RuleRecord] = (),
    polygons: Sequence[PolygonRecord] = (),
    pads: Sequence[Primitive] = (),
    vias: Sequence[Primitive] = (),
    tracks: Sequence[Primitive] = (),
    arcs: Sequence[Primitive] = (),
    texts: Sequence[Primitive] = (),
    fills: Sequence[Primitive] = (),
    regions: Sequence[Primitive] = (),
    pad_unique_ids: Mapping[int, str] | None = None,
    storages: Mapping[str, Mapping[str, bytes]] | None = None,
) -> PcbDocument:
    """A PCB document of the given records; every other part is empty."""
    return PcbDocument(
        header_text=None,
        unique_id=None,
        board=board_record or board(),
        nets=tuple(net(name) for name in nets),
        components=tuple(components),
        classes=tuple(classes),
        rules=tuple(rules),
        polygons=tuple(polygons),
        pads=tuple(pads),  # type: ignore[arg-type]
        vias=tuple(vias),  # type: ignore[arg-type]
        tracks=tuple(tracks),  # type: ignore[arg-type]
        arcs=tuple(arcs),  # type: ignore[arg-type]
        texts=tuple(texts),  # type: ignore[arg-type]
        fills=tuple(fills),  # type: ignore[arg-type]
        regions=tuple(regions),  # type: ignore[arg-type]
        shape_regions=(),
        wide_strings=MappingProxyType({}),
        pad_unique_ids=MappingProxyType(dict(pad_unique_ids or {})),
        storages=MappingProxyType(dict(storages or {})),
        issues=(),
        evidence=EVIDENCE,
    )


def body_bytes(
    points: Sequence[tuple[float, float]] = ((0, 0), (1000, 0), (1000, 500), (0, 500)),
    *,
    component: int | None = 0,
    layer: int = 69,
    fields: Mapping[str, str] | None = None,
    shape_based: bool = False,
    tail: bytes = b"",
) -> bytes:
    """One component-body primitive (type 12) as ``docs/formats/altium/pcb-bodies.md`` frames it: the
    prefix, five zero bytes, the property text and the outline (``points`` in mil)."""
    import struct

    keys = {
        "V7_LAYER": "MECHANICAL13",
        "NAME": " ",
        "KIND": "0",
        "STANDOFFHEIGHT": "0mil",
        "OVERALLHEIGHT": "40mil",
        "BODYPROJECTION": "0",
        "IDENTIFIER": "",
        "MODELID": "{00000000-0000-0000-0000-000000000000}",
        "MODEL.EMBED": "FALSE",
        "MODEL.NAME": "",
    } | dict(fields or {})
    text = ("|" + "|".join(f"{key}={value}" for key, value in keys.items())).encode("iso-8859-1") + b"\0"
    body = struct.pack("<BBBHHH", layer, 0, 0, 0xFFFF, 0xFFFF, 0xFFFF if component is None else component)
    body += bytes(9) + struct.pack("<I", len(text)) + text + struct.pack("<I", len(points))
    for x, y in points:
        if shape_based:
            body += struct.pack("<B5i2d", 0, int(x * MIL), int(y * MIL), 0, 0, 0, 0.0, 0.0)
        else:
            body += struct.pack("<2d", x * MIL, y * MIL)
    if shape_based:
        x, y = points[0]
        body += struct.pack("<B5i2d", 0, int(x * MIL), int(y * MIL), 0, 0, 0, 0.0, 0.0)
    body += tail
    return b"\x0c" + struct.pack("<I", len(body)) + body


def footprint(
    name: str = "FP",
    primitives: Sequence[Primitive] = (),
    *,
    description: str = "",
    height: str = "",
    unique_ids: Mapping[int, str] | None = None,
):  # noqa: ANN201 (the reader's class is imported below, next to its only user)
    """One library footprint of the given primitives."""
    from fenolite.backends.altium.read.pcblib import LibFootprint
    from fenolite.backends.altium.read.pcbprops import parse_mil

    fields = {"PATTERN": name, "HEIGHT": height, "DESCRIPTION": description}
    return LibFootprint(
        name=name,
        storage=name,
        parameters=props({key: value for key, value in fields.items() if value}),
        description=description or None,
        height=parse_mil(height) if height else None,
        primitives=tuple(primitives),
        unique_ids=MappingProxyType(dict(unique_ids or {})),
        wide_strings=MappingProxyType({}),
        streams=MappingProxyType({}),
        name_block=b"",
        trailing=b"",
    )


def pcb_library(*footprints: object):  # noqa: ANN201
    """A PCB library of the given footprints."""
    from fenolite.backends.altium.read.pcblib import EVIDENCE as LIB_EVIDENCE
    from fenolite.backends.altium.read.pcblib import PcbLibrary

    return PcbLibrary(
        header_text=None,
        version=None,
        unique_id=None,
        board=board(),
        names=tuple(f.name for f in footprints),  # type: ignore[attr-defined]
        footprints=tuple(footprints),  # type: ignore[arg-type]
        storages=MappingProxyType({}),
        issues=(),
        evidence=LIB_EVIDENCE,
    )


# --- schematic sheets (change c0043): authored records read by the product reader ------------------------


class Sheet:
    """A schematic sheet authored record by record and read by ``read.sch.read_schematic``. Coordinates are
    in schematic units of 10 mil. A pin is given by its electrical end and has length 0, so its location is
    that end. Harness records go to the ``Additional`` stream, as a saved sheet holds them."""

    def __init__(self, file: str = "sheet.SchDoc") -> None:
        from _altium_sch_build import SHEET

        self.file = file
        self.records: list[str] = [SHEET]
        self.additional: list[str] = []
        self._uid = 0

    def uid(self) -> str:
        self._uid += 1
        return f"{self.file[:3].upper()}{self._uid:05d}"

    def add(self, text: str) -> int:
        self.records.append(text)
        return len(self.records) - 1

    def component(
        self,
        ref: str,
        pins: Sequence[tuple[str, int, int]] = (),
        *,
        value: str = "",
        uid: str = "",
        part: int = 1,
        parts: int = 1,
        libref: str = "PART",
        library: str = "",
        footprint: str = "",
        designator: bool = True,
        extra: str = "",
        parameters: Mapping[str, str] | None = None,
        pin_fields: Mapping[str, str] | None = None,
        pin_map: Mapping[str, Sequence[str]] | None = None,
    ) -> int:
        """A component record with its designator, comment, parameters, pins ``(designator, x, y)`` and
        footprint model, whose map list holds one map record per pin of ``pin_map`` (pin designator to pad
        names); returns the record index."""
        index = self.add(
            f"|RECORD=1|LIBREFERENCE={libref}|PARTCOUNT={parts + 1}|DISPLAYMODECOUNT=1|OWNERPARTID=-1"
            f"|LOCATION.X=0|LOCATION.Y=0|CURRENTPARTID={part}|SOURCELIBRARYNAME={library}"
            f"|UNIQUEID={uid or self.uid()}{extra}"
        )
        if designator:
            self.add(f"|RECORD=34|OWNERINDEX={index}|OWNERPARTID=-1|NAME=Designator|TEXT={ref}")
        self.add(f"|RECORD=41|OWNERINDEX={index}|OWNERPARTID=-1|NAME=Comment|TEXT={value}")
        for name, text in (parameters or {}).items():
            self.add(f"|RECORD=41|OWNERINDEX={index}|OWNERPARTID=-1|NAME={name}|TEXT={text}")
        for item in pins:
            number, x, y = item[0], item[1], item[2]
            owner = item[3] if len(item) > 3 else part  # type: ignore[misc]
            keys = {
                "FORMALTYPE": "1",
                "ELECTRICAL": "4",
                "PINCONGLOMERATE": "0",
                "PINLENGTH": "0",
                "LOCATION.X": str(x),
                "LOCATION.Y": str(y),
                "NAME": f"P{number}",
                "DESIGNATOR": number,
            } | dict((pin_fields or {}).get(number, {}))  # type: ignore[call-overload]
            fields = "".join(f"|{key}={value}" for key, value in keys.items())
            self.add(f"|RECORD=2|OWNERINDEX={index}|OWNERPARTID={owner}{fields}")
        if footprint:
            models = self.add(f"|RECORD=44|OWNERINDEX={index}")
            model = self.add(
                f"|RECORD=45|OWNERINDEX={models}|MODELNAME={footprint}|MODELTYPE=PCBLIB|ISCURRENT=T"
                "|DATAFILECOUNT=1|MODELDATAFILEENTITY0=" + footprint + "|MODELDATAFILEKIND0=PCBLib"
                "|MODELDATAFILE0=Lib\\Parts.PcbLib"
            )
            if pin_map is not None:
                listed = self.add(f"|RECORD=46|OWNERINDEX={model}")
                for pin, pads in pin_map.items():
                    names = "".join(f"|DESIMP{n}={pad}" for n, pad in enumerate(pads))
                    self.add(f"|RECORD=47|OWNERINDEX={listed}|DESINTF={pin}|DESIMPCOUNT={len(pads)}{names}")
        return index

    def _points(self, points: Sequence[tuple[int, int]]) -> str:
        text = f"|LOCATIONCOUNT={len(points)}"
        return text + "".join(f"|X{i}={x}|Y{i}={y}" for i, (x, y) in enumerate(points, 1))

    def wire(self, *points: tuple[int, int]) -> int:
        return self.add("|RECORD=27|OWNERPARTID=-1|LINEWIDTH=1" + self._points(points))

    def bus(self, *points: tuple[int, int]) -> int:
        return self.add("|RECORD=26|OWNERPARTID=-1|LINEWIDTH=3" + self._points(points))

    def bus_entry(self, a: tuple[int, int], b: tuple[int, int]) -> int:
        return self.add(
            f"|RECORD=37|OWNERPARTID=-1|LOCATION.X={a[0]}|LOCATION.Y={a[1]}|CORNER.X={b[0]}|CORNER.Y={b[1]}"
        )

    def junction(self, x: int, y: int) -> int:
        return self.add(f"|RECORD=29|OWNERPARTID=-1|LOCATION.X={x}|LOCATION.Y={y}")

    def label(self, text: str, x: int, y: int) -> int:
        return self.add(f"|RECORD=25|OWNERPARTID=-1|LOCATION.X={x}|LOCATION.Y={y}|TEXT={text}")

    def power(self, text: str, x: int, y: int, *, off_sheet: bool = False) -> int:
        flag = "|ISCROSSSHEETCONNECTOR=T" if off_sheet else ""
        return self.add(f"|RECORD=17|OWNERPARTID=-1|LOCATION.X={x}|LOCATION.Y={y}|TEXT={text}{flag}")

    def port(self, name: str, x: int, y: int, *, width: int = 30, style: int = 0, harness: str = "") -> int:
        extra = (f"|STYLE={style}" if style else "") + (f"|HARNESSTYPE={harness}" if harness else "")
        return self.add(
            f"|RECORD=18|OWNERPARTID=-1|LOCATION.X={x}|LOCATION.Y={y}|WIDTH={width}|HEIGHT=10|NAME={name}"
            f"|UNIQUEID={self.uid()}{extra}"
        )

    def no_erc(self, x: int, y: int) -> int:
        return self.add(f"|RECORD=22|OWNERPARTID=-1|LOCATION.X={x}|LOCATION.Y={y}|ISACTIVE=T")

    def symbol(
        self,
        name: str,
        file: str,
        at: tuple[int, int],
        size: tuple[int, int] = (100, 100),
        entries: Sequence[tuple[str, int, int] | tuple[str, int, int, str]] = (),
        *,
        uid: str = "",
        named: bool = True,
    ) -> int:
        """A sheet symbol whose top-left corner is ``at``, with entries ``(name, side, steps of 10 units
        from the corner[, harness type])``; returns the record index."""
        index = self.add(
            f"|RECORD=15|OWNERPARTID=-1|LOCATION.X={at[0]}|LOCATION.Y={at[1]}|XSIZE={size[0]}|YSIZE={size[1]}"
            f"|UNIQUEID={uid or self.uid()}"
        )
        if named:
            self.add(f"|RECORD=32|OWNERINDEX={index}|OWNERPARTID=-1|TEXT={name}")
        self.add(f"|RECORD=33|OWNERINDEX={index}|OWNERPARTID=-1|TEXT={file}")
        for entry in entries:
            harness = f"|HARNESSTYPE={entry[3]}" if len(entry) > 3 else ""  # type: ignore[misc]
            side = f"|SIDE={entry[1]}" if entry[1] else ""
            self.add(
                f"|RECORD=16|OWNERINDEX={index}|OWNERPARTID=-1{side}|DISTANCEFROMTOP={entry[2]}"
                f"|NAME={entry[0]}{harness}"
            )
        return index

    def connector(
        self,
        kind: str,
        at: tuple[int, int],
        size: tuple[int, int],
        entries: Sequence[tuple[str, int]],
        *,
        side: int = 1,
        primary: int = 10,
    ) -> int:
        """A harness connector whose top-left corner is ``at``: its connection point lies on ``side``,
        ``primary`` units below the corner, and its entries ``(name, steps of 10 units)`` on the other
        side."""
        index = len(self.additional)
        side_key = f"|HARNESSCONNECTORSIDE={side}" if side else ""
        self.additional.append(
            f"|RECORD=215|OWNERPARTID=-1|LOCATION.X={at[0]}|LOCATION.Y={at[1]}|XSIZE={size[0]}|YSIZE={size[1]}"
            f"|PRIMARYCONNECTIONPOSITION={primary}{side_key}"
        )
        other = 0 if side == 1 else 1
        for name, steps in entries:
            entry_side = f"|SIDE={other}" if other else ""
            self.additional.append(
                f"|RECORD=216|OWNERINDEX={index}|OWNERINDEXADDITIONALLIST=T|OWNERPARTID=-1{entry_side}"
                f"|DISTANCEFROMTOP={steps}|NAME={name}"
            )
        self.additional.append(
            f"|RECORD=217|OWNERINDEX={index}|OWNERINDEXADDITIONALLIST=T|OWNERPARTID=-1|TEXT={kind}"
        )
        return index

    def harness_line(self, *points: tuple[int, int]) -> None:
        self.additional.append("|RECORD=218|OWNERPARTID=-1|LINEWIDTH=3" + self._points(points))

    def data(self) -> bytes:
        from _altium_sch_build import schdoc

        return schdoc(self.records, additional=self.additional or None)

    def document(self):  # noqa: ANN201
        from fenolite.backends.altium.read.sch import read_schematic

        return read_schematic(self.data(), file=self.file)

    def input(self):  # noqa: ANN201
        """The sheet as a ``SheetInput`` of the adapter."""
        import hashlib

        from fenolite.backends.altium.adapter.netlist import SheetInput

        data = self.data()
        return SheetInput(self.file, hashlib.sha256(data).hexdigest(), self.document())
