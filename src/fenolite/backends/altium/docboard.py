# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board record of an Altium PCB document: the one property block of ``Board6/Data`` (change c0035,
capability altium-pcb-writer, "PCB document file").

Written from ``docs/formats/altium/pcb-document.md`` ("The ``Board6`` record") only. Altium Designer refuses
a document whose ``Board6`` holds a short record, so ``board_text`` gives the whole record that Altium-saved
documents carry: a first line with the board keys and the outline, then the lines of a library's board
record (``libboard``) with the sub-stack keys, the drill pair, the routing keys, the view and the closing
keys. Every key and value follows a rule of the fact page; nothing is copied from a file. The inputs are the
file name, the outline, the used layers and the eight-letter id, so the bytes are deterministic.

Change c0038 adds the copper stack (``StackSpec``, "Four-layer stack"): the links of the numbered layers,
the physical lists, the layer sets and ``PLANE<k>NETNAME`` follow it (``pcb-copper.md``, "Layer stack").
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from decimal import Decimal

import fenolite.backends.altium.pcbrecords as rec
from fenolite.backends.altium.ascii import Field
from fenolite.backends.altium.libboard import (
    DATE,
    LINE_BREAK,
    RECORD,
    SNAP_GRID,
    TIME,
    Dielectric,
    StackSpec,
    guid,
    layer_sets,
    legacy_lines,
    plane_net_fields,
    stack_fields,
    view_configurations,
)

KIND = "Protel_Advanced_PCB"
VERSION = "5.01"
VIEW_MARGIN = 100 * rec.UNITS_PER_MIL
"""The window is the outline's box widened by 100 mil on every side (binary units)."""
ZOOM_WIDTH = 1190
"""``ZOOMMULT`` times the window's width in the Altium-saved documents, rounded."""
LAST_WIDTH = "10mil"
MID_LAYERS = range(1, 31)
_LEGACY_COUNT = 82
_COMMON: tuple[Field, ...] = (
    ("SELECTION", "FALSE"),
    ("LAYER", "UNKNOWN"),
    ("LOCKED", "FALSE"),
    ("POLYGONOUTLINE", "FALSE"),
    ("USERROUTED", "TRUE"),
    ("KEEPOUT", "FALSE"),
    ("UNIONINDEX", "0"),
)
"""The seven keys that open most property records of a document; ``LAYER`` varies."""
_FORMULAS: tuple[Field, ...] = (
    (
        "SURFACEMICROSTRIP_I",
        "(60/SQRT(Er*(1-EXP(-1.55*(0.00002+TraceToPlaneDistance)/TraceToPlaneDistance))))"
        "*LN(5.98*TraceToPlaneDistance/(0.8*TraceWidth+TraceHeight))",
    ),
    (
        "SURFACEMICROSTRIP_W",
        "((5.98*TraceToPlaneDistance)/EXP(CharacteristicImpedance/(60/SQRT(Er*(1-EXP(-1.55*(0.00002"
        "+TraceToPlaneDistance)/TraceToPlaneDistance)))))-TraceHeight)/0.8",
    ),
    (
        "SYMMETRICSTRIPLINE_I",
        "(80/SQRT(Er))*LN((1.9*(2*TraceToPlaneDistance+TraceHeight)/(0.8*TraceWidth+TraceHeight)))"
        "*(1-(TraceToPlaneDistance/(4*(PlaneToPlaneDistance-TraceHeight-TraceToPlaneDistance))))",
    ),
    (
        "SYMMETRICSTRIPLINE_W",
        "((1.9*(2*TraceToPlaneDistance+TraceHeight))/(EXP((CharacteristicImpedance/(80/SQRT(Er)))"
        "/(1-(TraceToPlaneDistance/(4*(PlaneToPlaneDistance-TraceHeight-TraceToPlaneDistance))))))"
        "-TraceHeight)/0.8",
    ),
)
"""The impedance formulas every Altium-saved document carries (``pcb-document.md``)."""
_POLYGON_HEAD: tuple[Field, ...] = (
    ("PRIMITIVELOCK", "TRUE"),
    ("POLYGONTYPE", "Polygon"),
    ("POUROVER", "FALSE"),
    ("REMOVEDEAD", "FALSE"),
    ("GRIDSIZE", "10mil"),
    ("TRACKWIDTH", "10mil"),
    ("HATCHSTYLE", "None"),
    ("USEOCTAGONS", "FALSE"),
    ("MINPRIMLENGTH", "3mil"),
)
_POLYGON_TAIL: tuple[Field, ...] = (
    ("SHELVED", "FALSE"),
    ("RESTORELAYER", "UNKNOWN"),
    ("RESTORENET", ""),
    ("REMOVEISLANDSBYAREA", "TRUE"),
    ("REMOVENECKS", "TRUE"),
    ("AREATHRESHOLD", "250000000000.000000"),
    ("ARCRESOLUTION", "0.5mil"),
    ("NECKWIDTHTHRESHOLD", "5mil"),
    ("POUROVERSTYLE", "2"),
    ("NAME", ""),
    ("POURINDEX", "-1"),
    ("IGNOREVIOLATIONS", "FALSE"),
    ("SPLITLINECOUNT", "0"),
)
_SHEET: tuple[Field, ...] = (
    ("SHEETX", "1000mil"),
    ("SHEETY", "1000mil"),
    ("SHEETWIDTH", "10000mil"),
    ("SHEETHEIGHT", "8000mil"),
    ("SHOWSHEET", "FALSE"),
    ("LOCKSHEET", "TRUE"),
)
_SNAP: tuple[Field, ...] = (
    ("EGRANGE", "8mil"),
    ("EGMULT", "0.000000"),
    ("EGENABLED", "TRUE"),
    ("EGSNAPTOBOARDOUTLINE", "FALSE"),
    ("EGSNAPTOARCCENTERS", "TRUE"),
    ("EGUSEALLLAYERS", "FALSE"),
    ("OGSNAPENABLED", "TRUE"),
    ("MGSNAPENABLED", "FALSE"),
    ("POINTGUIDEENABLED", "FALSE"),
    ("GRIDSNAPENABLED", "TRUE"),
    ("NEAROBJECTSENABLED", "FALSE"),
    ("FAROBJECTSENABLED", "TRUE"),
    ("NEAROBJECTSET", "011110100011000000000000001"),
    ("FAROBJECTSET", "001100000000000000000000000"),
    ("NEARDISTANCE", "200mil"),
    ("DRILLSYMBOLASENUM", "0"),
    ("DRILLSYMBOLSIZE", "200000"),
    ("HOLESHAPEHASHSIZE", "0"),
    ("VIEWPORTSAREVISIBLE", "TRUE"),
)
_TEARDROPS: tuple[Field, ...] = (
    ("TEARDROPPARAM_PERCENTFORVIAS_LENGTH", "30.000000"),
    ("TEARDROPPARAM_PERCENTFORVIAS_WIDTH", "70.000000"),
    ("TEARDROPPARAM_PERCENTFORPADS_LENGTH", "100.000000"),
    ("TEARDROPPARAM_PERCENTFORPADS_WIDTH", "200.000000"),
    ("TEARDROPPARAM_PERCENTFORTRACKS_LENGTH", "100.000000"),
    ("TEARDROPPARAM_PERCENTFORTRACKS_WIDTH", "-1.000000"),
    ("TEARDROPPARAM_PERCENTFORTJUNCTIONS_LENGTH", "100.000000"),
    ("TEARDROPPARAM_PERCENTFORTJUNCTIONS_WIDTH", "300.000000"),
    ("TEARDROPPARAM_FLAGSEX", "1002"),
    ("SPLITLINECOUNT", "0"),
)


def common_fields(layer: str) -> list[Field]:
    """The seven common keys of a document's property record with ``LAYER=<layer>``."""
    return [(key, layer if key == "LAYER" else value) for key, value in _COMMON]


def angle_text(udeg: int) -> str:
    """Microdegrees in ``[0, 360)`` in Altium's angle form: a space, one digit, 14 decimals and a signed
    four-digit exponent (`` 2.70000000000000E+0002``)."""
    value = Decimal(udeg % 360_000_000) / 1_000_000
    if value == 0:
        return " 0.00000000000000E+0000"
    exponent = value.adjusted()
    mantissa = value.scaleb(-exponent).quantize(Decimal(1).scaleb(-14))
    sign = "-" if exponent < 0 else "+"
    return f" {mantissa}E{sign}{abs(exponent):04d}"


def _six(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001")))


def _outline(vertices: Sequence[tuple[int, int]]) -> list[Field]:
    zero = angle_text(0)
    fields: list[Field] = []
    for index, (x, y) in enumerate((*vertices, vertices[0])):
        fields += [
            (f"KIND{index}", "0"),
            (f"VX{index}", rec.mil_text(x)),
            (f"VY{index}", rec.mil_text(y)),
            (f"CX{index}", "0mil"),
            (f"CY{index}", "0mil"),
            (f"SA{index}", zero),
            (f"EA{index}", zero),
            (f"R{index}", "0mil"),
        ]
    return fields


def _routing(stack: StackSpec | None = None) -> list[Field]:
    fields: list[Field] = [RECORD, ("TOGGLELAYERS", "1" * _LEGACY_COUNT)]
    for index in range(1, 11):
        fields += [(f"PLACEMARKERX{index}", "-0.0001mil"), (f"PLACEMARKERY{index}", "-0.0001mil")]
    fields += [(f"SELECTIONMEMORYLOCK{index}", "FALSE") for index in range(1, 9)]
    fields += [*_FORMULAS, ("ELECTRICALGRIDSNAPTOBO", "FALSE"), ("ELECTRICALGRIDUSEALLLAYERS", "FALSE")]
    fields += [
        ("ROUTINGDIRECTIONTOP LAYER", "Automatic"),
        *((f"ROUTINGDIRECTIONMID LAYER {index}", "Automatic") for index in MID_LAYERS),
        ("ROUTINGDIRECTIONBOTTOM LAYER", "Automatic"),
        ("TOPLAYER_MRLASTWIDTH", LAST_WIDTH),
        *((f"MIDLAYER{index}_MRLASTWIDTH", LAST_WIDTH) for index in MID_LAYERS),
        ("BOTTOMLAYER_MRLASTWIDTH", LAST_WIDTH),
        ("MRLASTVIASIZE", "50mil"),
        ("MRLASTVIAHOLE", "28mil"),
        ("LASTTARGETLENGTH", "99999mil"),
        ("SHOWDEFAULTSETS", "TRUE"),
        *layer_sets(stack),
        ("BOARDINSIGHTVIEWCONFIGURATIONNAME", ""),
    ]
    return fields


def board_records(
    filename: str,
    vertices: Sequence[tuple[int, int]],
    origin: tuple[int, int],
    *,
    unique_id: str,
    used_layers: Collection[int] = (),
    stack: StackSpec | None = None,
) -> list[list[Field]]:
    """The ``Board6`` record as its 27 lines, in Altium's order. ``filename`` is the document's file name
    (no folder); ``vertices`` is the outline in binary units in the Altium frame, without the closing
    vertex; ``origin`` is ``ORIGINX``/``ORIGINY`` in binary units; ``unique_id`` is the board's eight-letter
    id; ``used_layers`` are the numbered layers (1 … 74) that primitives lie on; ``stack`` is the copper
    stack (``None``: the two-layer stack of c0035, whose bytes it keeps). ``ValueError`` for fewer than
    three vertices."""
    if len(vertices) < 3:
        raise ValueError("a board outline needs at least three points")
    origin_x, origin_y = rec.mil_text(origin[0]), rec.mil_text(origin[1])
    substack = guid("substack")
    head: list[Field] = [
        *common_fields("UNKNOWN"),
        ("FILENAME", filename),
        ("KIND", KIND),
        ("VERSION", VERSION),
        ("DATE", DATE),
        ("TIME", TIME),
        ("ORIGINX", origin_x),
        ("ORIGINY", origin_y),
        ("BIGVISIBLEGRIDSIZE", "0.000"),
        ("VISIBLEGRIDSIZE", "0.000"),
        ("ELECTRICALGRIDRANGE", "8mil"),
        ("ELECTRICALGRIDENABLED", "TRUE"),
        ("SNAPGRIDSIZE", SNAP_GRID),
        ("SNAPGRIDSIZEX", SNAP_GRID),
        ("SNAPGRIDSIZEY", SNAP_GRID),
        ("TRACKGRIDSIZE", "200000.000000"),
        ("VIAGRIDSIZE", "200000.000000"),
        ("COMPONENTGRIDSIZE", SNAP_GRID),
        ("COMPONENTGRIDSIZEX", SNAP_GRID),
        ("COMPONENTGRIDSIZEY", SNAP_GRID),
        ("DOTGRID", "TRUE"),
        ("DISPLAYUNIT", "1"),
        ("DESIGNATORDISPLAYMODE", "0"),
        *common_fields("TOP"),
        *_POLYGON_HEAD,
        *_outline(vertices),
        *_POLYGON_TAIL,
        *_SHEET,
        *plane_net_fields(stack),
    ]
    first, *later = legacy_lines(stack)
    later[-1] += [
        ("LAYERPAIR0LOW", "TOP"),
        ("LAYERPAIR0HIGH", "BOTTOM"),
        ("LAYERPAIR0DRILLGUIDE", "FALSE"),
        ("LAYERPAIR0DRILLDRAWING", "FALSE"),
        ("LAYERPAIR0SUBSTACK_0", substack),
    ]
    low_x = min(x for x, _ in vertices) - VIEW_MARGIN
    high_x = max(x for x, _ in vertices) + VIEW_MARGIN
    low_y = min(y for _, y in vertices) - VIEW_MARGIN
    high_y = max(y for _, y in vertices) + VIEW_MARGIN
    width, height = high_x - low_x, high_y - low_y
    tail: list[Field] = [
        RECORD,
        ("LOOKAT.X", _six(Decimal(low_x + high_x) / 2)),
        ("LOOKAT.Y", _six(Decimal(low_y + high_y) / 2)),
        ("LOOKAT.Z", "0.000000"),
        ("EYEROTATION.X", "0.000000"),
        ("EYEROTATION.Y", "0.000000"),
        ("EYEROTATION.Z", "0.000000"),
        ("ZOOMMULT", _six(Decimal(ZOOM_WIDTH) / width)),
        ("VIEWSIZE.X", str(width)),
        ("VIEWSIZE.Y", str(height)),
        ("GR0_TYPE", "CartesianGrid"),
        ("GR0_NAME", "Global Board Snap Grid"),
        ("GR0_COLOR", "6049101"),
        ("GR0_COLORLGE", "9473425"),
        ("GR0_PRIO", "50"),
        ("GR0_OX", origin_x),
        ("GR0_OY", origin_y),
        ("GR0_DRAWMODE", "1"),
        ("GR0_DRAWMODELARGE", "1"),
        ("GR0_ENABLED", "TRUE"),
        ("GR0_MULT", "1"),
        ("GR0_MULTLARGE", "5"),
        ("GR0_DISPLAYUNIT", "1"),
        ("GR0_COMP", "TRUE"),
        ("GR0_GSX", SNAP_GRID),
        ("GR0_GSY", SNAP_GRID),
        ("GR0_QSX", "99999mil"),
        ("GR0_QSY", "99999mil"),
        ("GR0_ROT", "0.000000"),
        ("GR0_FLAGS", "15"),
        *_SNAP,
        ("UNIQUEID", unique_id),
        ("PINPAIRCOUNT", "0"),
        *_TEARDROPS,
    ]
    return [
        head,
        [RECORD, *stack_fields(used_layers, substack, stack), *first],
        *later,
        _routing(stack),
        [
            RECORD,
            ("VISIBLEGRIDMULTFACTOR", "1.000"),
            ("BIGVISIBLEGRIDMULTFACTOR", "5.000"),
            ("ELECTRICALGRIDMULTFACT", "0.000"),
            ("OUTLINEMODELCRC", "0"),
            ("OUTLINEMODELNAME", ""),
        ],
        [RECORD, ("CURRENT2D3DVIEWSTATE", "2D")],
        [
            RECORD,
            ("VP.LX", str(low_x)),
            ("VP.HX", str(high_x)),
            ("VP.LY", str(low_y)),
            ("VP.HY", str(high_y)),
        ],
        *view_configurations(),
        tail,
    ]


def format_line(fields: Sequence[Field]) -> str:
    """One line of the record as ``|KEY=VALUE`` fields. A key may hold spaces (the routing directions);
    ``ValueError`` for a key or value that is not printable 7-bit ASCII or holds ``|``, or a key with
    ``=``."""
    parts: list[str] = []
    for key, value in fields:
        text = key + value
        if not key or "=" in key or "|" in text or not all(0x20 <= ord(ch) <= 0x7E for ch in text):
            raise ValueError(f"the field {key!r}={value!r} cannot be written in a board record")
        parts.append(f"|{key}={value}")
    return "".join(parts)


def board_fields(
    filename: str,
    vertices: Sequence[tuple[int, int]],
    origin: tuple[int, int],
    *,
    unique_id: str,
    used_layers: Collection[int] = (),
    stack: StackSpec | None = None,
) -> list[Field]:
    """Every field of ``board_records`` in order, the lines joined."""
    lines = board_records(
        filename, vertices, origin, unique_id=unique_id, used_layers=used_layers, stack=stack
    )
    return [item for line in lines for item in line]


def board_text(
    filename: str,
    vertices: Sequence[tuple[int, int]],
    origin: tuple[int, int],
    *,
    unique_id: str,
    used_layers: Collection[int] = (),
    stack: StackSpec | None = None,
) -> str:
    """The text of the ``Board6`` record: each line as ``|KEY=VALUE`` fields, the lines joined by one CR."""
    lines = board_records(
        filename, vertices, origin, unique_id=unique_id, used_layers=used_layers, stack=stack
    )
    return LINE_BREAK.join(format_line(line) for line in lines)


__all__ = [
    "KIND",
    "Dielectric",
    "StackSpec",
    "VERSION",
    "VIEW_MARGIN",
    "ZOOM_WIDTH",
    "angle_text",
    "board_fields",
    "board_records",
    "board_text",
    "common_fields",
    "format_line",
]
