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

# evidence: see pcbdoc

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction

import fenolite.backends.altium.pcbrecords as rec
from fenolite.backends.altium.ascii import Field
from fenolite.backends.altium.libboard import (
    DATE,
    ENABLED_MECHANICAL,
    LINE_BREAK,
    RECORD,
    SNAP_GRID,
    TIME,
    Dielectric,
    StackSpec,
    enabled_mechanical,
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


OutlineArc = tuple[int, int, int, int, int]
"""An arc vertex of an outline (change c0441): centre X and Y and radius in binary units in the Altium
frame, and the start and end angles in microdegrees, the counter-clockwise sweep from the start angle to
the end angle (``pcb-document.md``, "Board outline arcs")."""


def _outline(
    vertices: Sequence[tuple[int, int]], arcs: Mapping[int, OutlineArc] | None = None
) -> list[Field]:
    """The eight keys per vertex, the first vertex repeated last as a line vertex. ``arcs`` maps the index
    of a vertex to its arc, which runs from that vertex to the next."""
    zero = angle_text(0)
    arcs = arcs or {}
    fields: list[Field] = []
    for index, (x, y) in enumerate((*vertices, vertices[0])):
        arc = arcs.get(index) if index < len(vertices) else None
        if arc is None:
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
            continue
        cx, cy, radius, start, end = arc
        fields += [
            (f"KIND{index}", "1"),
            (f"VX{index}", rec.mil_text(x)),
            (f"VY{index}", rec.mil_text(y)),
            (f"CX{index}", rec.mil_text(cx)),
            (f"CY{index}", rec.mil_text(cy)),
            (f"SA{index}", angle_text(start)),
            (f"EA{index}", angle_text(end)),
            (f"R{index}", rec.mil_text(radius)),
        ]
    return fields


_POUR_HEAD: tuple[Field, ...] = (
    ("PRIMITIVELOCK", "TRUE"),
    ("POLYGONTYPE", "Polygon"),
    ("POUROVER", "TRUE"),
    ("REMOVEDEAD", "TRUE"),
    ("GRIDSIZE", "20mil"),
    ("TRACKWIDTH", "8mil"),
    ("HATCHSTYLE", "Solid"),
    ("USEOCTAGONS", "FALSE"),
    ("MINPRIMLENGTH", "3mil"),
)
"""The keys of a solid polygon pour before its vertices (``pcb-copper.md``, "Polygon pour")."""
HATCH_STYLES = ("Solid", "45Degree", "90Degree", "Horizontal", "Vertical", "None")
"""The ``HATCHSTYLE`` values (``pcb-copper.md``, "Polygon pour")."""
_POUR_TAIL: tuple[Field, ...] = (*_POLYGON_TAIL[:8], ("POUROVERSTYLE", "1"))
"""The keys after the vertices that a pour shares with the board outline, up to ``POUROVERSTYLE``; a pour
sets ``REMOVEISLANDSBYAREA``, ``AREATHRESHOLD`` and ``NECKWIDTHTHRESHOLD`` from its zone (change c0446)."""
SQUARE_NM_PER_UNIT = Fraction(127, 50) ** 2
"""Square nanometres per square file unit (0.0001 mil squared): ``AREATHRESHOLD``'s unit (``pcb-pour.md``,
I12)."""
DEFAULT_AREA_THRESHOLD = "250000000000.000000"
"""The ``AREATHRESHOLD`` of a pour that removes no island by area: Altium's own value, 2500 mil²."""
LEGACY_ISLANDS_NM2 = 1_612_900_000_000
"""2500 mil² in square nanometres: the island area of a pour whose zone has the default settings, the bytes
that c0035 wrote and the kit verified (change c0446)."""
LEGACY_NECK_NM = 127_000
"""5 mil: the neck width of a pour whose zone has the default settings (change c0446)."""


def area_threshold_text(area_nm2: int) -> str:
    """An area in square nanometres as ``AREATHRESHOLD`` text: square file units with six decimals, rounded
    half to even (``100_000_000_000`` → ``15500031000.062000``, 0.1 mm², which Altium saves as
    ``15500031000.062008``; change c0446)."""
    units = Fraction(area_nm2) / SQUARE_NM_PER_UNIT
    value = Decimal(units.numerator) / Decimal(units.denominator)
    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))


def name_codes(text: str) -> str:
    """A polygon's ``NAME`` value: the character codes of ``text`` in decimal, joined by commas."""
    return ",".join(str(ord(ch)) for ch in text)


def polygon_fields(
    layer_text: str,
    vertices: Sequence[tuple[int, int]],
    *,
    name: str,
    pour_index: int,
    net: int | None = None,
    auto_name: bool = False,
    remove_dead: bool = True,
    optimal_void_rotation: bool = True,
    pour_over: str = "1",
    islands: int | None = LEGACY_ISLANDS_NM2,
    neck: int = LEGACY_NECK_NM,
    arcs: Mapping[int, OutlineArc] | None = None,
    arc_resolution: str | None = None,
    hatch: tuple[str, int, int] | None = None,
) -> list[Field]:
    """The fields of one unpoured, solid polygon pour of ``Polygons6`` (``pcb-copper.md``, "Polygon pour"):
    the key set of the board outline with a net, a name and a pour index. ``layer_text`` is the ``LAYER``
    text (``TOP``, ``MID1`` …); ``vertices`` are in binary units in the Altium frame, without the closing
    vertex; ``net`` is the net's index (``None``: no ``NET`` key); ``auto_name`` adds ``AUTONAME=TRUE``.
    ``remove_dead`` off writes ``REMOVEDEAD=FALSE``: the pour keeps its islands (change c0085).
    ``optimal_void_rotation`` off writes ``OPTIMALVOIDROTATION=FALSE``, the form of a computed pour (change
    c0215, input I15). ``pour_over`` is ``POUROVERSTYLE`` (``0``, ``1`` or ``2``, input I8), with
    ``POUROVER=TRUE`` for ``1`` only, as the saved documents pair them. ``islands`` is the area in square
    nanometres below which a piece is removed (``REMOVEISLANDSBYAREA=TRUE`` with its ``AREATHRESHOLD``;
    ``None``: ``FALSE``) and ``neck`` the neck width in nanometres (``NECKWIDTHTHRESHOLD``; change c0446).
    ``ValueError`` for fewer than three vertices, another ``pour_over``, or an area or width that is not
    positive. ``arcs`` maps a vertex index to the arc that runs from it to the next, and ``arc_resolution``
    is the ``ARCRESOLUTION`` text: the source's arc vertices, written back by a conversion (change c0463,
    task 1.3). ``hatch`` is ``(HATCHSTYLE, GRIDSIZE, TRACKWIDTH)``, the two lengths in nanometres: a hatched
    polygon (change c0463, task 3.1; ``ValueError`` for another style or a length that is not positive);
    ``None`` writes the solid pour's ``Solid``, 20 mil and 8 mil."""
    if len(vertices) < 3:
        raise ValueError("a polygon needs at least three points")
    if pour_over not in ("0", "1", "2"):
        raise ValueError(f"POUROVERSTYLE is 0, 1 or 2, not {pour_over!r}")
    if (islands is not None and islands <= 0) or neck <= 0:
        raise ValueError("an island area and a neck width are positive")
    if hatch is not None and (hatch[0] not in HATCH_STYLES or hatch[1] <= 0 or hatch[2] <= 0):
        raise ValueError(f"a hatch is one of {', '.join(HATCH_STYLES)} with a positive grid and track width")
    fixed = {
        "REMOVEDEAD": "TRUE" if remove_dead else "FALSE",
        "POUROVER": "TRUE" if pour_over == "1" else "FALSE",
        "REMOVEISLANDSBYAREA": "FALSE" if islands is None else "TRUE",
        "AREATHRESHOLD": DEFAULT_AREA_THRESHOLD if islands is None else area_threshold_text(islands),
        "NECKWIDTHTHRESHOLD": rec.mil_text(rec.to_units(neck)),
    }
    if arc_resolution is not None:
        fixed["ARCRESOLUTION"] = arc_resolution
    if hatch is not None:
        fixed["HATCHSTYLE"] = hatch[0]
        fixed["GRIDSIZE"] = rec.mil_text(rec.to_units(hatch[1]))
        fixed["TRACKWIDTH"] = rec.mil_text(rec.to_units(hatch[2]))
    head = [(key, fixed.get(key, value)) for key, value in _POUR_HEAD]
    fields: list[Field] = [
        *common_fields(layer_text),
        *head,
        *_outline(vertices, arcs),
        *((key, fixed.get(key, value)) for key, value in _POUR_TAIL[:-1]),
        ("POUROVERSTYLE", pour_over),
        ("NAME", name_codes(name)),
        ("POURINDEX", str(pour_index)),
        ("IGNOREVIOLATIONS", "FALSE"),
    ]
    if auto_name:
        fields.append(("AUTONAME", "TRUE"))
    fields.append(("OPTIMALVOIDROTATION", "TRUE" if optimal_void_rotation else "FALSE"))
    if net is not None:
        fields.append(("NET", str(net)))
    return fields


SPLIT_PLANE = "Split Plane"
"""The ``POLYGONTYPE`` of the polygon that gives an internal plane its net (``pcb-copper.md``)."""


def split_plane_fields(layer_text: str, vertices: Sequence[tuple[int, int]], net: int) -> list[Field]:
    """The fields of one ``Split Plane`` polygon of ``Polygons6`` (change c0389, task 2.7; ``pcb-copper.md``,
    "Layer stack"): the seven common keys on the plane's ``LAYER`` (``PLANE1`` …), ``PRIMITIVELOCK=TRUE``,
    ``POLYGONTYPE=Split Plane``, the closed straight vertices and ``NET``, the order of the saved plane
    (S-1653). ``vertices`` are in binary units in the Altium frame, without the closing vertex; ``net`` is the
    net's index. ``ValueError`` for fewer than three vertices."""
    if len(vertices) < 3:
        raise ValueError("a split plane needs at least three points")
    return [
        *common_fields(layer_text),
        ("PRIMITIVELOCK", "TRUE"),
        ("POLYGONTYPE", SPLIT_PLANE),
        *_outline(vertices),
        ("NET", str(net)),
    ]


def _routing(stack: StackSpec | None = None, mechanical: Sequence[int] = ENABLED_MECHANICAL) -> list[Field]:
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
        *layer_sets(stack, mechanical),
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
    arcs: Mapping[int, OutlineArc] | None = None,
    pin_pairs: Sequence[Field] = (),
    mechanical: Sequence[int] | None = None,
) -> list[list[Field]]:
    """The ``Board6`` record as its 27 lines, in Altium's order. ``filename`` is the document's file name
    (no folder); ``vertices`` is the outline in binary units in the Altium frame, without the closing
    vertex, and ``arcs`` its arc vertices by index (change c0441); ``origin`` is ``ORIGINX``/``ORIGINY``
    in binary units; ``unique_id`` is the board's eight-letter id; ``used_layers`` are the numbered layers
    (1 … 74) that primitives lie on; ``stack`` is the copper stack (``None``: the two-layer stack of c0035,
    whose bytes it keeps). ``pin_pairs`` (change c0461) are the ``PINPAIRCOUNT`` and ``PINPAIR…<k>`` keys of
    the xSignals a conversion carried, in place of ``PINPAIRCOUNT=0``, as the source holds them after
    ``UNIQUEID``. ``mechanical`` (change c0464) are the numbers of the enabled mechanical layers, in place
    of those ``used_layers`` give (``enabled_mechanical``). ``ValueError`` for fewer than three vertices."""
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
        *_outline(vertices, arcs),
        *_POLYGON_TAIL,
        *_SHEET,
        *plane_net_fields(stack),
    ]
    mechanical = tuple(sorted(mechanical)) if mechanical is not None else enabled_mechanical(used_layers)
    first, *later = legacy_lines(stack, mechanical)
    later[-1] += [
        ("LAYERPAIR0LOW", "TOP"),
        ("LAYERPAIR0HIGH", "BOTTOM"),
        ("LAYERPAIR0DRILLGUIDE", "FALSE"),
        ("LAYERPAIR0DRILLDRAWING", "FALSE"),
        ("LAYERPAIR0SUBSTACK_0", substack),
    ]
    for number, (low, high) in enumerate(stack.drill_pairs if stack is not None else (), start=1):
        later[-1] += [  # change c0085, "Blind and buried via records"
            (f"LAYERPAIR{number}LOW", rec.layer_text(low)),
            (f"LAYERPAIR{number}HIGH", rec.layer_text(high)),
            (f"LAYERPAIR{number}DRILLGUIDE", "FALSE"),
            (f"LAYERPAIR{number}DRILLDRAWING", "FALSE"),
            (f"LAYERPAIR{number}SUBSTACK_0", substack),
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
        *(pin_pairs or (("PINPAIRCOUNT", "0"),)),
        *_TEARDROPS,
    ]
    return [
        head,
        [RECORD, *stack_fields(used_layers, substack, stack, mechanical), *first],
        *later,
        _routing(stack, mechanical),
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


OWNED_KEY = re.compile(
    r"RECORD|SELECTION|LAYER|LOCKED|POLYGONOUTLINE|USERROUTED|KEEPOUT|UNIONINDEX|PRIMITIVELOCK|SPLITLINECOUNT"
    r"|FILENAME|KIND|VERSION|DATE|TIME|UNIQUEID|ORIGIN[XY]|(?:KIND|VX|VY|CX|CY|SA|EA|R)\d+"
    r"|SHEET(?:X|Y|WIDTH|HEIGHT)|LOOKAT\.[XYZ]|EYEROTATION\.[XYZ]|ZOOMMULT|VIEWSIZE\.[XY]|VP\.[LH][XY]"
    r"|GR\d+_O[XY]|GU\d+_.*|PLACEMARKER[XY]\d+|MOVIE.*|3DMOVIESCOUNT|CURRENT3DMOVIEID"
    r"|LAYER\d+.*|LAYERV\d+_.*|LAYER_V\d+_.*|LAYERMASTERSTACK_.*|LAYERSUBSTACK_.*|LAYERPAIR\d+.*|LAYERSET.*"
    r"|LAYERSTACKSTYLE|LAYERCOUNT|V\d+_.*|MECHPAIR.*|PLANE\d+.*|(?:TOP|BOTTOM)(?:CONST|HEIGHT|MATERIAL|TYPE)"
    r"|SHOW(?:TOP|BOTTOM)DIELECTRIC|ROUTINGDIRECTION.*|MIDLAYER\d+_MRLASTWIDTH|TOGGLELAYERS|PINPAIR.*"
)
"""The keys of ``Board6`` the writer decides (change c0464): the document's identity, the keys a record
holds twice, the frame (origin, outline, sheet, camera and viewport, grid origins, guides, place markers,
movies), the layer stack and its tables, layer sets and pairs, planes, the layer-bound keys and the
xSignals of change c0461. A conversion never takes them from the source; every other key is a setting."""
ANCHOR = "@"
"""The key that opens a run of carried settings in ``Board6.Settings``: its value is the source key the run
followed (change c0464). No Altium key is ``@``."""


def writable_field(key: str, value: str) -> bool:
    """Whether ``format_line`` writes the field: a key and value of printable 7-bit ASCII without ``|``, a
    key without ``=``."""
    text = key + value
    return bool(key) and "=" not in key and "|" not in text and all(0x20 <= ord(ch) <= 0x7E for ch in text)


def with_settings(lines: Sequence[Sequence[Field]], settings: Sequence[Field]) -> list[list[Field]]:
    """``lines`` (``board_records``) with the carried settings of a source (change c0464,
    ``Board6.Settings``) merged in order: ``@=<key>`` moves the anchor to ``<key>`` when the record holds it
    once; an owned key (``OWNED_KEY``), a key the record holds twice and a field ``format_line`` refuses are
    skipped; a key the record holds once takes the carried value; any other key is written after the anchor,
    on its line (at the end of the first line before any anchor). Each written or replaced key becomes the
    anchor."""
    found = [list(line) for line in lines]
    counts: dict[str, int] = {}
    for line in found:
        for key, _ in line:
            counts[key] = counts.get(key, 0) + 1

    def where(key: str) -> tuple[int, int] | None:
        if counts.get(key) != 1:
            return None
        for row, line in enumerate(found):
            for column, (name, _) in enumerate(line):
                if name == key:
                    return row, column
        return None

    anchor: tuple[int, int] | None = None
    for key, value in settings:
        if key == ANCHOR:
            anchor = where(value) or anchor
            continue
        if OWNED_KEY.fullmatch(key) or counts.get(key, 0) > 1 or not writable_field(key, value):
            continue
        at = where(key)
        if at is not None:
            found[at[0]][at[1]] = (key, value)
            anchor = at
            continue
        row, column = anchor if anchor is not None else (0, len(found[0]) - 1)
        found[row].insert(column + 1, (key, value))
        counts[key] = 1
        anchor = (row, column + 1)
    return found


def format_line(fields: Sequence[Field]) -> str:
    """One line of the record as ``|KEY=VALUE`` fields. A key may hold spaces (the routing directions);
    ``ValueError`` for a key or value that is not printable 7-bit ASCII or holds ``|``, or a key with
    ``=``."""
    parts: list[str] = []
    for key, value in fields:
        if not writable_field(key, value):
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
    arcs: Mapping[int, OutlineArc] | None = None,
) -> list[Field]:
    """Every field of ``board_records`` in order, the lines joined."""
    lines = board_records(
        filename, vertices, origin, unique_id=unique_id, used_layers=used_layers, stack=stack, arcs=arcs
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
    layer_names: Mapping[int, str] | None = None,
    arcs: Mapping[int, OutlineArc] | None = None,
    pin_pairs: Sequence[Field] = (),
    settings: Sequence[Field] = (),
    mechanical: Sequence[int] | None = None,
    copper_names: Mapping[int, str] | None = None,
) -> str:
    """The text of the ``Board6`` record: each line as ``|KEY=VALUE`` fields, the lines joined by one CR.
    ``settings`` are the carried settings of a source (change c0464, ``with_settings``), merged before the
    mechanical layers are named; ``mechanical`` are the enabled mechanical layers (``board_records``).
    ``copper_names`` names copper layers by id: signal layers (1 … 32) and internal planes (39 … 54, change
    c0466)."""
    lines = board_records(
        filename,
        vertices,
        origin,
        unique_id=unique_id,
        used_layers=used_layers,
        stack=stack,
        arcs=arcs,
        pin_pairs=pin_pairs,
        mechanical=mechanical,
    )
    if settings:
        lines = with_settings(lines, settings)
    names = {
        f"Mechanical {number}": name
        for layer, name in (layer_names or {}).items()
        if (number := rec.mechanical_number(layer)) is not None  # 17 to 32 too (change c0450, task 4.4)
    }
    names |= {
        rec.LAYER_NAMES[layer]: name
        for layer, name in (copper_names or {}).items()
        if 1 <= layer <= 32 or 39 <= layer <= 54
    }
    if names:
        lines = [[(key, names.get(value, value)) for key, value in line] for line in lines]
    return LINE_BREAK.join(format_line(line) for line in lines)


__all__ = [
    "ANCHOR",
    "HATCH_STYLES",
    "KIND",
    "OWNED_KEY",
    "OutlineArc",
    "SPLIT_PLANE",
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
    "name_codes",
    "polygon_fields",
    "area_threshold_text",
    "split_plane_fields",
    "with_settings",
    "writable_field",
]
