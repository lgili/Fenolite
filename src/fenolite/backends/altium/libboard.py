# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board record of an Altium PCB library: the property block that opens ``Library/Data`` (change c0035,
capability altium-pcb-writer, "PCB library file").

Written from ``docs/formats/altium/pcb-library.md`` ("The board record of ``Library/Data``") only. Altium
refuses a library whose ``Library/Data`` holds a short property block, so ``board_text`` gives the whole
record that Altium-saved libraries carry: the file keys, the layer stack in its three generations (``V9_``,
``_V8`` and the numbered ``LAYER<n>`` keys), the grid, the layer sets and the 2D view configuration. Every
key and value follows a rule of the fact page; nothing is copied from a file. The only inputs are the file
name and the layers the footprints use, so the bytes are deterministic.
"""

from __future__ import annotations

import hashlib
from collections.abc import Collection

from fenolite.backends.altium.ascii import Field, format_record

KIND = "Protel_Advanced_PCB_Library"
VERSION = "3.00"
BOARD_VERSION = "5.01"
DATE = "2000-01-01"
TIME = "00:00:00"
"""Fenolite writes one fixed date and time, so equal libraries give equal bytes."""
GUID_SALT = "fenolite.altium.guid:"
MASTER_STACK_NAME = "Master layer stack"
ENABLED_MECHANICAL = (13, 14, 15, 16)
"""The mechanical layers of Fenolite's layer map (``pcbrecords.LAYER_MAP``), enabled in every library."""
SNAP_GRID = "50000.000000"
"""5 mil in binary units, the text form Altium uses for the snap grid."""
VIEWPORT = (("VP.LX", 499_000_000), ("VP.HX", 501_000_000), ("VP.LY", 499_000_000), ("VP.HY", 501_000_000))
"""A window of 200 mil around the library origin, which Altium puts at (50 000 mil, 50 000 mil)."""
LINE_BREAK = "\r"
"""One CR stands between the lines of the board record."""
RECORD: Field = ("RECORD", "Board")

_SIGNAL, _PLANE, _MECHANICAL, _MISC, _DIELECTRIC = (
    0x0100_0000,
    0x0101_0000,
    0x0102_0000,
    0x0103_0000,
    0x0104_0000,
)
_BOTTOM = _SIGNAL + 0xFFFF
_COPPER: tuple[Field, ...] = (("COPTHICK", "1.4mil"),)
_CORE: tuple[Field, ...] = (
    ("DIELTYPE", "0"),
    ("DIELCONST", "4.800"),
    ("DIELHEIGHT", "12.6mil"),
    ("DIELMATERIAL", "FR-4"),
)
_RESIST: tuple[Field, ...] = (
    ("DIELTYPE", "3"),
    ("DIELCONST", "3.500"),
    ("DIELHEIGHT", "0.4mil"),
    ("DIELMATERIAL", "Solder Resist"),
)
_MISC_NAMES = {
    6: "Top Overlay",
    7: "Bottom Overlay",
    8: "Top Paste",
    9: "Bottom Paste",
    10: "Top Solder",
    11: "Bottom Solder",
    12: "Drill Guide",
    13: "Keep-Out Layer",
    14: "Drill Drawing",
    15: "Multi-Layer",
    16: "Connections",
    17: "Background",
    18: "DRC Error Markers",
    19: "Selections",
    20: "Visible Grid 1",
    21: "Visible Grid 2",
    22: "Pad Holes",
    23: "Via Holes",
    24: "Top Pad Master",
    25: "Bottom Pad Master",
    26: "DRC Detail Markers",
}
"""The low word of the long ids ``0x0103xxxx`` and their layer names."""
_LEGACY_MISC = {33: 6, 34: 7, 35: 8, 36: 9, 37: 10, 38: 11, 55: 12, 56: 13, 73: 14}
_LEGACY_MISC.update({74 + i: 15 + i for i in range(9)})
_PHYSICAL = (8, 6, 10, None, None, None, 11, 7, 9)
"""The physical stack from top to bottom as low words of ``0x0103xxxx``; ``None`` marks, in order, the top
copper, the dielectric and the bottom copper."""
_OPACITY_NAMES = (
    ("TOPLAYER", *(f"MIDLAYER{i}" for i in range(1, 31)), "BOTTOMLAYER")
    + ("TOPOVERLAY", "BOTTOMOVERLAY", "TOPPASTE", "BOTTOMPASTE", "TOPSOLDER", "BOTTOMSOLDER")
    + tuple(f"INTERNALPLANE{i}" for i in range(1, 17))
    + ("DRILLGUIDE", "KEEPOUTLAYER")
    + tuple(f"MECHANICAL{i}" for i in range(1, 17))
    + ("DRILLDRAWING", "MULTILAYER", "CONNECTLAYER", "BACKGROUNDLAYER", "DRCERRORLAYER", "HIGHLIGHTLAYER")
    + ("GRIDCOLOR1", "GRIDCOLOR10", "PADHOLELAYER", "VIAHOLELAYER")
)
_OPACITY = "1.00;" * 16 + "0.40;" + "1.00;" * 6
_LEGACY_COUNT = 82
_CHUNK = 5
"""The numbered layers are written five at a time, each later group opened by ``RECORD=Board``."""
_VIEW_2D: tuple[Field, ...] = (
    ("DISPLAYSPECIALSTRINGS", "FALSE"),
    ("SHOWTESTPOINTS", "FALSE"),
    ("SHOWORIGINMARKER", "TRUE"),
    ("EYEDIST", "2000"),
    ("SHOWSTATUSINFO", "TRUE"),
    ("SHOWPADNETS", "TRUE"),
    ("SHOWPADNUMBERS", "TRUE"),
    ("SHOWVIANETS", "TRUE"),
    ("USETRANSPARENTLAYERS", "FALSE"),
    ("PLANEDRAWMODE", "2"),
    ("DISPLAYNETNAMESONTRACKS", "1"),
    ("FROMTOSDISPLAYMODE", "0"),
    ("PADTYPESDISPLAYMODE", "0"),
    ("SINGLELAYERMODESTATE", "3"),
    ("ORIGINMARKERCOLOR", "16777215"),
    ("SHOWCOMPONENTREFPOINT", "FALSE"),
    ("COMPONENTREFPOINTCOLOR", "16777215"),
    ("POSITIVETOPSOLDERMASK", "FALSE"),
    ("POSITIVEBOTTOMSOLDERMASK", "FALSE"),
    ("TOPPOSITIVESOLDERMASKALPHA", "0.500000"),
    ("BOTTOMPOSITIVESOLDERMASKALPHA", "0.500000"),
    ("ALLCONNECTIONSINSINGLELAYERMODE", "TRUE"),
    ("MULTICOLOREDCONNECTIONS", "FALSE"),
)
_VIEW_3D: tuple[Field, ...] = (
    ("POSITIVETOPSOLDERMASK", "TRUE"),
    ("POSITIVEBOTTOMSOLDERMASK", "TRUE"),
    ("SHOWCOMPONENTBODIES", "SYSTEM"),
    ("SHOWCOMPONENTSTEPMODELS", "SYSTEM"),
    ("COMPONENTMODELPREFERENCE", "0"),
    ("SHOWCOMPONENTSNAPMARKERS", "TRUE"),
    ("SHOWCOMPONENTAXES", "TRUE"),
    ("SHOWBOARDCORE", "TRUE"),
    ("SHOWBOARDPREPREG", "TRUE"),
    ("SHOWTOPSILKSCREEN", "TRUE"),
    ("SHOWBOTSILKSCREEN", "TRUE"),
    ("SHOWORIGINMARKER", "TRUE"),
    ("EYEDIST", "2000"),
    ("SHOWCUTOUTS", "TRUE"),
    ("SHOWROUTETOOLPATH", "TRUE"),
    ("SHOWROOMS3D", "FALSE"),
    ("USESYSCOLORSFOR3D", "FALSE"),
    ("WORKSPACECOLOR", "16777215"),
    ("BOARDCORECOLOR", "0"),
    ("BOARDPREPREGCOLOR", "0"),
    ("TOPSOLDERMASKCOLOR", "3307556"),
    ("BOTSOLDERMASKCOLOR", "3307556"),
    ("COPPERCOLOR", "2402753"),
    ("TOPSILKSCREENCOLOR", "16448250"),
    ("BOTSILKSCREENCOLOR", "16448250"),
    ("WORKSPACELUMINANCEVARIATION", "30"),
    ("WORKSPACECOLOROPACITY", "1.000000"),
    ("BOARDCORECOLOROPACITY", "0.500000"),
    ("BOARDPREPREGCOLOROPACITY", "0.500000"),
    ("TOPSOLDERMASKCOLOROPACITY", "0.600000"),
    ("BOTSOLDERMASKCOLOROPACITY", "0.600000"),
    ("COPPERCOLOROPACITY", "1.000000"),
    ("TOPSILKSCREENCOLOROPACITY", "1.000000"),
    ("BOTSILKSCREENCOLOROPACITY", "1.000000"),
    ("BOARDTHICKNESSSCALING", "1.000000"),
    ("SHOWMECHANICALLAYERS", "FALSE"),
    ("MECHANICALLAYERSOPACITY", "1.000000"),
)
_TAIL: tuple[Field, ...] = (
    ("LOOKAT.X", "0.000000"),
    ("LOOKAT.Y", "0.000000"),
    ("LOOKAT.Z", "0.000000"),
    ("EYEROTATION.X", "0.000000"),
    ("EYEROTATION.Y", "0.000000"),
    ("EYEROTATION.Z", "0.000000"),
    ("ZOOMMULT", "0.000001"),
    ("VIEWSIZE.X", "402"),
    ("VIEWSIZE.Y", "365"),
    ("EGRANGE", "8mil"),
    ("EGMULT", "0.000000"),
    ("EGENABLED", "TRUE"),
    ("EGSNAPTOBOARDOUTLINE", "FALSE"),
    ("EGSNAPTOARCCENTERS", "FALSE"),
    ("EGUSEALLLAYERS", "FALSE"),
    ("OGSNAPENABLED", "FALSE"),
    ("MGSNAPENABLED", "FALSE"),
    ("POINTGUIDEENABLED", "FALSE"),
    ("GRIDSNAPENABLED", "TRUE"),
    ("NEAROBJECTSENABLED", "TRUE"),
    ("FAROBJECTSENABLED", "TRUE"),
    ("NEAROBJECTSET", "011111100011100000000000001"),
    ("FAROBJECTSET", "001100000000000000000000000"),
    ("NEARDISTANCE", "1000mil"),
    ("BOARDVERSION", BOARD_VERSION),
    ("VAULTGUID", ""),
    ("FOLDERGUID", ""),
    ("LIFECYCLEDEFINITIONGUID", ""),
    ("REVISIONNAMINGSCHEMEGUID", ""),
)


def guid(key: str) -> str:
    """A GUID in braces and upper case from the SHA-256 of ``fenolite.altium.guid:<key>``: its first 16
    bytes as 8-4-4-4-12 hexadecimal digits."""
    digest = hashlib.sha256((GUID_SALT + key).encode("utf-8")).hexdigest().upper()
    return "{" + "-".join((digest[:8], digest[8:12], digest[12:16], digest[16:20], digest[20:32])) + "}"


def _bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def long_id(layer: int) -> int:
    """The long layer id of a numbered layer 1 … 82 (``pcb-library.md``, "Long layer ids")."""
    if layer == 32:
        return _BOTTOM
    if 1 <= layer <= 31:
        return _SIGNAL + layer
    if 39 <= layer <= 54:
        return _PLANE + layer - 38
    if 57 <= layer <= 72:
        return _MECHANICAL + layer - 56
    if layer in _LEGACY_MISC:
        return _MISC + _LEGACY_MISC[layer]
    raise ValueError(f"layer {layer} has no long id")


def _name(long: int) -> str:
    group, low = long & 0xFFFF_0000, long & 0xFFFF
    if long == _BOTTOM:
        return "Bottom Layer"
    if group == _SIGNAL:
        return "Top Layer" if low == 1 else f"Mid-Layer {low - 1}"
    if group == _PLANE:
        return f"Internal Plane {low}"
    if group == _MECHANICAL:
        return f"Mechanical {low}"
    if group == _DIELECTRIC:
        return f"Dielectric {low}"
    return _MISC_NAMES[low]


def _legacy_name(layer: int) -> str:
    return _name(long_id(layer))


def _stack_ids() -> list[int]:
    """The nine layers of the physical stack, top to bottom."""
    copper = iter((_SIGNAL + 1, _DIELECTRIC + 1, _BOTTOM))
    return [_MISC + low if low is not None else next(copper) for low in _PHYSICAL]


def _cache_ids() -> list[int]:
    """The 102 layers of the ``V9_CACHE`` list in its order."""
    head = [_MISC + low for low in (15, 16, 17, 18, 26, 19, 20, 21, 22, 23, 24, 25)]
    mids = [_SIGNAL + i for i in range(2, 32)]
    planes = [_PLANE + i for i in range(1, 17)]
    first = [_MECHANICAL + i for i in range(1, 17)]
    later = [_MECHANICAL + i for i in range(17, 33)]
    return head + _stack_ids() + mids + planes + [_MISC + 12, _MISC + 13] + first + [_MISC + 14] + later


def _v8_ids() -> list[int]:
    """The 56 layers of the ``LAYER_V8`` list in its order."""
    first = [_MECHANICAL + i for i in range(1, 17)]
    misc = [_MISC + low for low in (14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26)]
    later = [_MECHANICAL + i for i in range(17, 33)]
    return _stack_ids() + [_MISC + 12, _MISC + 13] + first + misc + later


def _layer_fields(prefix: str, sep: str, long: int, used: Collection[int]) -> list[Field]:
    """The keys of one layer of a ``V9`` list (``sep`` ``_``) or of the ``_V8`` list (``sep`` empty)."""
    group, low = long & 0xFFFF_0000, long & 0xFFFF
    fields: list[Field] = [
        ("ID", guid(f"layer:{long}")),
        ("NAME", _name(long)),
        ("LAYERID", str(long)),
        ("USEDBYPRIMS", _bool(long in used)),
    ]
    if group == _SIGNAL:
        placement = "1" if low == 1 else "2" if long == _BOTTOM else "0"
        fields += [*_COPPER, ("COMPONENTPLACEMENT", placement)]
    elif group == _PLANE:
        fields += [*_COPPER, ("PULLBACKDISTANCE", "20mil")]
    elif group == _DIELECTRIC:
        fields += _CORE
    elif group == _MECHANICAL:
        fields.append(("MECHENABLED", _bool(low in ENABLED_MECHANICAL)))
    elif low in (10, 11):
        fields += [*_RESIST, ("COVERLAY_EXPANSION", "0mil")]
    return [(f"{prefix}{sep}{key}", value) for key, value in fields]


def _master(prefix: str, sep: str) -> list[Field]:
    fields: tuple[Field, ...] = (
        ("STYLE", "0"),
        ("ID", guid("masterstack")),
        ("NAME", MASTER_STACK_NAME),
        ("SHOWTOPDIELECTRIC", "FALSE"),
        ("SHOWBOTTOMDIELECTRIC", "FALSE"),
        ("ISFLEX", "FALSE"),
    )
    return [(f"{prefix}{sep}{key}", value) for key, value in fields]


def _legacy_layers() -> list[Field]:
    """``LAYER<n>…`` for n = 1 … 82 in groups of five, and the sixteen ``LAYERV7_<i>…`` layers."""
    links = {1: (0, 32), 32: (1, 0)}
    links.update({n: (0, 1) for n in (33, 35, 37)})
    links.update({n: (32, 0) for n in (34, 36, 38)})
    enabled = {56 + n for n in ENABLED_MECHANICAL}
    out: list[Field] = []
    for layer in range(1, _LEGACY_COUNT + 1):
        if layer > 1 and layer % _CHUNK == 1:
            out.append(RECORD)
        prev, following = links.get(layer, (0, 0))
        fields: tuple[Field, ...] = (
            ("NAME", _legacy_name(layer)),
            ("PREV", str(prev)),
            ("NEXT", str(following)),
            ("MECHENABLED", _bool(layer in enabled)),
            *_COPPER,
            *_CORE,
        )
        out += [(f"LAYER{layer}{key}", value) for key, value in fields]
    for index in range(16):
        number = 17 + index
        fields = (
            ("LAYERID", str(_MECHANICAL + number)),
            ("NAME", f"Mechanical {number}"),
            ("PREV", str(_MISC)),
            ("NEXT", str(_MISC)),
            ("MECHENABLED", "FALSE"),
            *_COPPER,
            *_CORE,
        )
        out += [(f"LAYERV7_{index}{key}", value) for key, value in fields]
    return out


def _layer_sets() -> list[Field]:
    mechanical = [f"Mechanical{n}" for n in ENABLED_MECHANICAL]
    top = ["MultiLayer", "TopPaste", "TopOverlay", "TopSolder"]
    bottom = ["BottomSolder", "BottomOverlay", "BottomPaste", "DrillGuide", "KeepOutLayer"]
    sets: tuple[tuple[str, list[str], str], ...] = (
        ("&All Layers", [*top, "TopLayer", "BottomLayer", *bottom, *mechanical, "DrillDrawing"], "TOP"),
        ("&Signal Layers", ["MultiLayer", "TopLayer", "BottomLayer"], "TOP"),
        ("&Plane Layers", [], "UNKNOWN"),
        ("&NonSignal Layers", [*top, *bottom, "DrillDrawing"], "MULTILAYER"),
        ("&Mechanical Layers", mechanical, mechanical[0].upper()),
    )
    out: list[Field] = [("LAYERSETSCOUNT", str(len(sets)))]
    for number, (name, layers, active) in enumerate(sets, start=1):
        out += [
            (f"LAYERSET{number}NAME", name),
            (f"LAYERSET{number}LAYERS", ",".join(layers)),
            (f"LAYERSET{number}ACTIVELAYER.7", active),
            (f"LAYERSET{number}ISCURRENT", "FALSE"),
            (f"LAYERSET{number}ISLOCKED", "TRUE"),
            (f"LAYERSET{number}FLIPBOARD", "FALSE"),
        ]
    return out


def _layer_hash(ids: list[int]) -> str:
    return "SerializeLayerHash.Version=2,ClassName=TLayerHash," + ",".join(f"{i}=1" for i in ids)


def _toggle_set() -> str:
    signal = [_SIGNAL + i for i in range(1, 32)] + [_BOTTOM]
    mechanical = [_MECHANICAL + i for i in range(1, 17)]
    planes = [_PLANE + i for i in range(1, 17)]
    standard = [_MISC + 26] + [_MISC + i for i in range(6, 24)]
    groups = (("Signal", signal), ("Mechanical", mechanical), ("Internal", planes), ("Standard", standard))
    text = "_".join(f"{name}.All~0_{name}.Include~{_layer_hash(ids)}" for name, ids in groups)
    return text + "_Dielectric.All~0"


def _view_2d() -> list[Field]:
    """The 2D view configuration: ``CFGALL`` and ``CFG2D`` keys."""
    boolean_set = "SerializeLayerHash.Version~2,ClassName~TLayerToBoolean,25165826~0"
    out: list[Field] = [
        ("CFGALL.CONFIGURATIONKIND", "1"),
        ("CFGALL.CONFIGURATIONDESC", "Altium%20Standard%202D"),
        ("CFG2D.PRIMDRAWMODE", "0" * 23),
    ]
    out += [(f"CFG2D.LAYEROPACITY.{name}", _OPACITY) for name in _OPACITY_NAMES]
    out += [("CFG2D.TOGGLELAYERS", "1" * _LEGACY_COUNT), ("CFG2D.TOGGLELAYERS.SET", _toggle_set())]
    out += [(f"CFG2D.WORKSPACECOLALPHA{i}", "1.0") for i in (*range(12), 13, 14)]
    out += [
        ("CFG2D.MECHLAYERINSINGLELAYERMODE", "0" * 16),
        ("CFG2D.MECHLAYERINSINGLELAYERMODE.SET", boolean_set),
        ("CFG2D.MECHLAYERLINKEDTOSHEET", "0" * 16),
        ("CFG2D.MECHLAYERLINKEDTOSHEET.SET", boolean_set),
        ("CFG2D.CURRENTLAYER", "TOP"),
    ]
    return out + [(f"CFG2D.{key}", value) for key, value in _VIEW_2D]


def _nested(fields: list[Field]) -> str:
    """Fields as one value: ``RECORD=Board`` first, each field opened by a backtick, ``;`` written ``?``."""
    return "".join(f"`{key}={value.replace(';', '?')}" for key, value in [RECORD, *fields])


def board_records(filename: str, used_layers: Collection[int] = ()) -> list[list[Field]]:
    """The board record of a library as its lines, in Altium's order: the first line holds the file keys,
    the stacks and the first five numbered layers; every later line starts with ``RECORD=Board``.
    ``filename`` is the library's file name (no folder); ``used_layers`` are the numbered layers (1 … 74)
    that primitives lie on."""
    used = {long_id(layer) for layer in used_layers}
    head: list[Field] = [
        ("FILENAME", filename),
        ("KIND", KIND),
        ("VERSION", VERSION),
        ("DATE", DATE),
        ("TIME", TIME),
    ]
    head += _master("V9_MASTERSTACK", "_")
    for index, long in enumerate(_stack_ids()):
        head += _layer_fields(f"V9_STACK_LAYER{index}", "_", long, used)
    for index, long in enumerate(_cache_ids()):
        head += _layer_fields(f"V9_CACHE_LAYER{index}", "_", long, used)
    head += _master("LAYERMASTERSTACK_V8", "")
    for index, long in enumerate(_v8_ids()):
        head += _layer_fields(f"LAYER_V8_{index}", "", long, used)
    for side in ("TOP", "BOTTOM"):
        head += [(f"{side}{key.removeprefix('DIEL')}", value) for key, value in _RESIST]
    head += [("LAYERSTACKSTYLE", "0"), ("SHOWTOPDIELECTRIC", "FALSE"), ("SHOWBOTTOMDIELECTRIC", "FALSE")]
    lines = [head]
    for item in _legacy_layers():
        if item == RECORD:
            lines.append([])
        lines[-1].append(item)
    view = _view_2d()
    view_3d: list[Field] = [
        ("CFGALL.CONFIGURATIONKIND", "3"),
        ("CFGALL.CONFIGURATIONDESC", "Enter%20description%20of%20new%20view%20configuration"),
        *((f"CFG3D.{key}", value) for key, value in _VIEW_3D),
    ]
    grid: list[Field] = [
        RECORD,
        ("BIGVISIBLEGRIDSIZE", "0.000"),
        ("VISIBLEGRIDSIZE", "0.000"),
        ("SNAPGRIDSIZE", SNAP_GRID),
        ("SNAPGRIDSIZEX", SNAP_GRID),
        ("SNAPGRIDSIZEY", SNAP_GRID),
        ("ELECTRICALGRIDRANGE", "8mil"),
        ("ELECTRICALGRIDENABLED", "FALSE"),
        ("DOTGRID", "FALSE"),
        ("DOTGRIDLARGE", "FALSE"),
        ("DISPLAYUNIT", "0"),
        ("TOGGLELAYERS", "1" * _LEGACY_COUNT),
        ("SHOWDEFAULTSETS", "TRUE"),
        *_layer_sets(),
        RECORD,
        *view,
        ("BOARDINSIGHTVIEWCONFIGURATIONNAME", ""),
        ("VISIBLEGRIDMULTFACTOR", "1.000"),
        ("BIGVISIBLEGRIDMULTFACTOR", "5.000"),
    ]
    lines += [
        grid,
        [RECORD, ("CURRENT2D3DVIEWSTATE", "2D")],
        [RECORD, *((key, str(value)) for key, value in VIEWPORT)],
        [RECORD, ("2DCONFIGTYPE", ".config_2dsimple"), ("2DCONFIGURATION", _nested(view))],
        [RECORD, ("2DCONFIGFULLFILENAME", "(Not Saved)")],
        [RECORD, ("3DCONFIGTYPE", ".config_3d"), ("3DCONFIGURATION", _nested(view_3d))],
        [RECORD, ("3DCONFIGFULLFILENAME", "(Not Saved)")],
        [RECORD, *_TAIL],
    ]
    return lines


def board_fields(filename: str, used_layers: Collection[int] = ()) -> list[Field]:
    """Every field of ``board_records`` in order, the lines joined."""
    return [item for line in board_records(filename, used_layers) for item in line]


def board_text(filename: str, used_layers: Collection[int] = ()) -> str:
    """The text of the board record: each line as ``|KEY=VALUE`` fields, the lines joined by one CR."""
    return LINE_BREAK.join(format_record(line) for line in board_records(filename, used_layers))


__all__ = [
    "BOARD_VERSION",
    "DATE",
    "ENABLED_MECHANICAL",
    "KIND",
    "LINE_BREAK",
    "TIME",
    "VERSION",
    "board_fields",
    "board_records",
    "board_text",
    "guid",
    "long_id",
]
