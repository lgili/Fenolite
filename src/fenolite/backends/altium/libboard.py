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

A PCB document passes a ``StackSpec`` (change c0038, "Four-layer stack"; ``pcb-copper.md``, "Layer stack"):
two or four copper layers, each inner layer a signal layer or an internal plane, with the copper
thicknesses and the dielectrics between them. Without one, the stack is the two-layer stack of c0035.
"""

# evidence: see pcbdoc, pcblib

from __future__ import annotations

import hashlib
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

import fenolite.backends.altium.pcbrecords as rec
from fenolite.backends.altium.ascii import Field, format_record, text_problem

KIND = "Protel_Advanced_PCB_Library"
VERSION = "3.00"
BOARD_VERSION = "5.01"
DATE = "2000-01-01"
TIME = "00:00:00"
"""Fenolite writes one fixed date and time, so equal libraries give equal bytes."""
GUID_SALT = "fenolite.altium.guid:"
MASTER_STACK_NAME = "Master layer stack"
SUBSTACK_NAME = "Board Layer Stack"
ENABLED_MECHANICAL = (13, 14, 15, 16)
"""The mechanical layers of Fenolite's layer map (``pcbrecords.LAYER_MAP``), enabled in every library."""


def enabled_mechanical(used_layers: Collection[int] = ()) -> tuple[int, ...]:
    """The numbers of the enabled mechanical layers of a board record whose primitives lie on
    ``used_layers`` (numbered layers 1 … 74): ``ENABLED_MECHANICAL`` and each of Mechanical 1 to 12 (the
    layers 57 to 68) that is used (change c0126; ``pcb-document.md``, "Mechanical layers in use"). A
    document that uses none of the twelve gives ``ENABLED_MECHANICAL``, and so the bytes of before."""
    used = {layer - 56 for layer in used_layers if 57 <= layer <= 68}
    return tuple(sorted({*ENABLED_MECHANICAL, *used}))


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
_ABOVE, _BELOW = (8, 6, 10), (11, 7, 9)
"""The physical stack above the top copper (paste, overlay, solder) and below the bottom copper (solder,
overlay, paste), as low words of ``0x0103xxxx``."""
COPPER_THICKNESS = 35_560
"""1.4 mil of copper in nanometres, Fenolite's default for every copper layer."""
PULLBACK = "20mil"
"""``PULLBACKDISTANCE`` of an internal plane, as the Altium-saved documents hold it."""
DielectricKind = Literal["unspecified", "core", "prepreg"]
DIELECTRIC_TYPES: dict[str, str] = {"unspecified": "0", "core": "1", "prepreg": "2"}
"""``DIELTYPE`` of a dielectric kind (``pcb-copper.md``, "Layer stack")."""
NO_NET = "(No Net)"
PLANE_COUNT = 16


@dataclass(frozen=True, slots=True)
class Dielectric:
    """One dielectric between two copper layers: its kind, its thickness in nanometres, its dielectric
    constant as a decimal string and its material."""

    kind: DielectricKind
    thickness: int
    epsilon_r: str = "4.800"
    material: str = "FR-4"

    def __post_init__(self) -> None:
        if self.kind not in DIELECTRIC_TYPES:
            raise ValueError(f"a dielectric is unspecified, core or prepreg, not {self.kind!r}")
        if self.thickness <= 0:
            raise ValueError(f"a dielectric needs a positive thickness, not {self.thickness} nm")
        try:
            constant = Decimal(self.epsilon_r)
        except InvalidOperation:
            constant = Decimal(0)
        if not constant.is_finite() or constant <= 0:
            raise ValueError(f"the dielectric constant {self.epsilon_r!r} is not a positive decimal number")
        problem = text_problem(self.material)
        if problem is not None:
            raise ValueError(f"the dielectric material {self.material!r} {problem}")

    def fields(self) -> tuple[Field, ...]:
        constant = Decimal(self.epsilon_r).quantize(Decimal("0.001"))
        return (
            ("DIELTYPE", DIELECTRIC_TYPES[self.kind]),
            ("DIELCONST", str(constant)),
            ("DIELHEIGHT", rec.mil_text(rec.to_units(self.thickness))),
            ("DIELMATERIAL", self.material),
        )


@dataclass(frozen=True, slots=True)
class StackSpec:
    """The copper stack of a document. ``copper`` holds the Altium ids from top to bottom, as
    ``pcbrecords.copper_stack`` gives them; ``thicknesses`` one copper thickness per layer and
    ``dielectrics`` one dielectric between each pair of neighbours (nanometres); ``plane_nets`` one net name
    per plane of ``copper``, in plane order. ``ValueError`` names what does not fit."""

    copper: tuple[int, ...]
    thicknesses: tuple[int, ...]
    dielectrics: tuple[Dielectric, ...]
    plane_nets: tuple[str, ...] = ()
    drill_pairs: tuple[tuple[int, int], ...] = ()
    """The drill pairs besides the pair of the outer layers (change c0085): the two copper ids of each
    span of a blind or buried via, the upper layer first, in stack order and without repeats."""

    def __post_init__(self) -> None:
        if not valid_stack(self.copper):
            raise ValueError(
                f"the copper layers {self.copper!r} are not a stack that is written: the top layer 1, "
                "then each inner layer as Mid-Layer k (k + 1) at position k or as the next internal plane "
                "from 39, then the bottom layer 32, an even count with at most 16 signal layers"
            )
        for low, high in self.drill_pairs:
            if (
                low not in self.copper
                or high not in self.copper
                or not (self.copper.index(low) < self.copper.index(high))
            ):
                raise ValueError(f"the drill pair {low}, {high} is not two layers of the stack in order")
        if (
            len(set(self.drill_pairs)) != len(self.drill_pairs)
            or (
                self.copper[0],
                self.copper[-1],
            )
            in self.drill_pairs
        ):
            raise ValueError("the drill pairs repeat a pair or hold the pair of the outer layers")
        if len(self.thicknesses) != len(self.copper) or any(t <= 0 for t in self.thicknesses):
            raise ValueError(
                f"a stack of {len(self.copper)} copper layers needs as many positive thicknesses"
            )
        if len(self.dielectrics) != len(self.copper) - 1:
            raise ValueError(
                f"a stack of {len(self.copper)} copper layers needs {len(self.copper) - 1} dielectrics, "
                f"not {len(self.dielectrics)}"
            )
        planes = self.planes
        if len(self.plane_nets) < len(planes):
            missing = ", ".join(rec.LAYER_NAMES[i] for i in planes[len(self.plane_nets) :])
            raise ValueError(f"{missing} has no net: the stack needs one plane net per plane")
        if len(self.plane_nets) > len(planes):
            raise ValueError(f"the stack has {len(planes)} plane(s) and {len(self.plane_nets)} plane nets")
        for name in self.plane_nets:
            problem = text_problem(name)
            if problem is not None:
                raise ValueError(f"the plane net {name!r} {problem}")

    @property
    def planes(self) -> tuple[int, ...]:
        """The ids of the internal planes of the stack, top to bottom."""
        return tuple(layer for layer in self.copper if layer >= rec.FIRST_PLANE)

    @classmethod
    def default(cls, copper: tuple[int, ...], plane_nets: tuple[str, ...] = ()) -> StackSpec:
        """Fenolite's default values: 1.4 mil copper; for two layers the dielectric of c0035 (12.6 mil,
        ``4.800``, ``FR-4``, kind ``unspecified``); for four layers a prepreg of 0.2 mm, a core of 1.0 mm
        and a prepreg of 0.2 mm; for more layers (change c0085) prepregs of 0.2 mm and cores in turn,
        the outermost a prepreg, the cores sharing 1.0 mm."""
        if len(copper) == 2:
            dielectrics: tuple[Dielectric, ...] = (Dielectric("unspecified", 320_040),)
        else:
            cores = (len(copper) - 1) // 2
            dielectrics = tuple(
                Dielectric("core", 1_000_000 // cores) if index % 2 else Dielectric("prepreg", 200_000)
                for index in range(len(copper) - 1)
            )
        return cls(tuple(copper), (COPPER_THICKNESS,) * len(copper), dielectrics, plane_nets)


def valid_stack(copper: tuple[int, ...]) -> bool:
    """Whether ``copper`` is a stack ``pcbrecords.copper_stack`` gives: 1, the inner ids, 32."""
    if len(copper) < 2 or copper[0] != rec.TOP_LAYER or copper[-1] != rec.BOTTOM_LAYER:
        return False
    planes = [layer for layer in copper[1:-1] if layer >= rec.FIRST_PLANE]
    if rec.stack_problem(len(copper), len(planes)) is not None:
        return False
    plane = rec.FIRST_PLANE
    for position, layer in enumerate(copper[1:-1], start=1):
        if layer == plane:
            plane += 1
        elif layer != position + 1:
            return False
    return True


STACKS: tuple[tuple[int, ...], ...] = (
    rec.copper_stack(rec.COPPER_STACKS[0]),
    rec.copper_stack(rec.COPPER_STACKS[1]),
    rec.copper_stack(rec.COPPER_STACKS[1], ("In1.Cu",)),
    rec.copper_stack(rec.COPPER_STACKS[1], ("In2.Cu",)),
    rec.copper_stack(rec.COPPER_STACKS[1], ("In1.Cu", "In2.Cu")),
)
"""The copper stacks of two and of four layers, as Altium ids (``valid_stack`` tells every stack that is
written)."""
_TWO_LAYERS = StackSpec.default(STACKS[0])


def _stack(stack: StackSpec | None) -> StackSpec:
    return _TWO_LAYERS if stack is None else stack


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


def _stack_ids(stack: StackSpec | None = None) -> list[int]:
    """The layers of the physical stack, top to bottom: paste, overlay and solder, then the copper layers
    with ``Dielectric <n>`` between neighbours (numbered from the top), then solder, overlay and paste;
    nine layers for two copper layers, thirteen for four."""
    copper: list[int] = []
    for position, layer in enumerate(_stack(stack).copper):
        if position:
            copper.append(_DIELECTRIC + position)
        copper.append(long_id(layer))
    return [*(_MISC + low for low in _ABOVE), *copper, *(_MISC + low for low in _BELOW)]


def _cache_ids(stack: StackSpec | None = None) -> list[int]:
    """The layers of the ``V9_CACHE`` list in its order: the 102 layers of a two-layer document (the outer
    run with ``Dielectric 1``, every mid layer, every plane, …), then the further dielectrics of the stack.
    Every layer appears once: a mid layer or a plane of the stack keeps its place in its run and carries
    its stack keys (``pcb-copper.md``, "Layer stack")."""
    head = [_MISC + low for low in (15, 16, 17, 18, 26, 19, 20, 21, 22, 23, 24, 25)]
    outer = [
        *(_MISC + low for low in _ABOVE),
        _SIGNAL + 1,
        _DIELECTRIC + 1,
        _BOTTOM,
        *(_MISC + low for low in _BELOW),
    ]
    mids = [_SIGNAL + i for i in range(2, 32)]
    planes = [_PLANE + i for i in range(1, 17)]
    first = [_MECHANICAL + i for i in range(1, 17)]
    later = [_MECHANICAL + i for i in range(17, 33)]
    more = [_DIELECTRIC + n for n in range(2, len(_stack(stack).dielectrics) + 1)]
    return head + outer + mids + planes + [_MISC + 12, _MISC + 13] + first + [_MISC + 14] + later + more


def _v8_ids(stack: StackSpec | None = None) -> list[int]:
    """The layers of the ``LAYER_V8`` list in its order (56 for two copper layers)."""
    first = [_MECHANICAL + i for i in range(1, 17)]
    misc = [_MISC + low for low in (14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26)]
    later = [_MECHANICAL + i for i in range(17, 33)]
    return _stack_ids(stack) + [_MISC + 12, _MISC + 13] + first + misc + later


def _copper_thickness(stack: StackSpec, long: int) -> tuple[Field, ...]:
    """``COPTHICK`` of a copper layer: its thickness in the stack, else the default 1.4 mil."""
    for layer, thickness in zip(stack.copper, stack.thicknesses, strict=True):
        if long_id(layer) == long:
            return (("COPTHICK", rec.mil_text(rec.to_units(thickness))),)
    return _COPPER


def _layer_fields(
    prefix: str,
    sep: str,
    long: int,
    used: Collection[int],
    substack: str | None = None,
    stack: StackSpec | None = None,
) -> list[Field]:
    """The keys of one layer of a ``V9`` list (``sep`` ``_``) or of the ``_V8`` list (``sep`` empty). With
    ``substack`` (a document's sub-stack GUID) a layer of the physical stack first gets its two sub-stack
    keys (``pcb-document.md``, "The ``Board6`` record"). A signal mid layer of the stack has
    ``COMPONENTPLACEMENT=1``, an unused one ``0``; a plane has its pull-back distance; a dielectric of the
    stack has the values of ``stack`` (``pcb-copper.md``, "Layer stack")."""
    spec = _stack(stack)
    physical = _stack_ids(spec)
    group, low = long & 0xFFFF_0000, long & 0xFFFF
    fields: list[Field] = [
        ("ID", guid(f"layer:{long}")),
        ("NAME", _name(long)),
        ("LAYERID", str(long)),
        ("USEDBYPRIMS", _bool(long in used)),
    ]
    if group == _SIGNAL:
        placement = "1" if low == 1 else "2" if long == _BOTTOM else "1" if long in physical else "0"
        fields += [*_copper_thickness(spec, long), ("COMPONENTPLACEMENT", placement)]
    elif group == _PLANE:
        fields += [*_copper_thickness(spec, long), ("PULLBACKDISTANCE", PULLBACK)]
    elif group == _DIELECTRIC:
        fields += spec.dielectrics[low - 1].fields()
    elif group == _MECHANICAL:
        # Mechanical 1 to 12 are enabled when a primitive lies on them (change c0126)
        fields.append(("MECHENABLED", _bool(low in ENABLED_MECHANICAL or (low <= 12 and long in used))))
    elif low in (10, 11):
        fields += [*_RESIST, ("COVERLAY_EXPANSION", "0mil")]
    out = [(f"{prefix}{sep}{key}", value) for key, value in fields]
    if substack is not None and long in physical:
        out[:0] = [(f"{prefix}_{substack}CONTEXT", "0"), (f"{prefix}_{substack}USEDBYPRIMS", "FALSE")]
    return out


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


def _substack(prefix: str, sep: str, substack: str) -> list[Field]:
    fields: tuple[Field, ...] = (
        ("ID", substack),
        ("NAME", SUBSTACK_NAME),
        ("SHOWTOPDIELECTRIC", "FALSE"),
        ("SHOWBOTTOMDIELECTRIC", "FALSE"),
        ("ISFLEX", "FALSE"),
        ("SERVICE", "FALSE"),
        ("USEDBYPRIMS", "FALSE"),
        ("TYPE", "1"),
    )
    return [(f"{prefix}{sep}{key}", value) for key, value in fields]


def stack_fields(
    used_layers: Collection[int] = (), substack: str | None = None, stack: StackSpec | None = None
) -> list[Field]:
    """The layer stack in its ``V9`` and ``_V8`` generations and the keys that close it: the master stack,
    the physical stack, the cache list, the ``_V8`` list, the top and bottom dielectric and the style keys.
    ``used_layers`` are numbered layers (1 … 74); ``substack`` is a document's sub-stack GUID, which adds
    the sub-stack keys (a library has none); ``stack`` is the copper stack (``None``: two layers)."""
    used = {long_id(layer) for layer in used_layers}
    out = _master("V9_MASTERSTACK", "_")
    if substack is not None:
        out += _substack("V9_SUBSTACK0", "_", substack)
    for index, long in enumerate(_stack_ids(stack)):
        out += _layer_fields(f"V9_STACK_LAYER{index}", "_", long, used, substack, stack)
    for index, long in enumerate(_cache_ids(stack)):
        out += _layer_fields(f"V9_CACHE_LAYER{index}", "_", long, used, substack, stack)
    out += _master("LAYERMASTERSTACK_V8", "")
    if substack is not None:
        out += _substack("LAYERSUBSTACK_V8_0", "", substack)
    for index, long in enumerate(_v8_ids(stack)):
        out += _layer_fields(f"LAYER_V8_{index}", "", long, used, substack, stack)
    for side in ("TOP", "BOTTOM"):
        out += [(f"{side}{key.removeprefix('DIEL')}", value) for key, value in _RESIST]
    out += [("LAYERSTACKSTYLE", "0"), ("SHOWTOPDIELECTRIC", "FALSE"), ("SHOWBOTTOMDIELECTRIC", "FALSE")]
    return out


def legacy_lines(
    stack: StackSpec | None = None, mechanical: Sequence[int] = ENABLED_MECHANICAL
) -> list[list[Field]]:
    """The numbered layers and the ``LAYERV7_`` layers as lines: the first line holds layers 1 to 5 and no
    ``RECORD=Board``; each later line starts with it. The copper layers of ``stack`` are linked in order.
    ``mechanical`` are the numbers of the enabled mechanical layers (``enabled_mechanical``)."""
    lines: list[list[Field]] = [[]]
    for item in _legacy_layers(stack, mechanical):
        if item == RECORD:
            lines.append([])
        lines[-1].append(item)
    return lines


def layer_sets(stack: StackSpec | None = None, mechanical: Sequence[int] = ENABLED_MECHANICAL) -> list[Field]:
    """``LAYERSETSCOUNT`` and the five layer sets; the signal mid layers and the planes of ``stack`` are
    listed in their sets, and so are the enabled mechanical layers ``mechanical``."""
    return _layer_sets(stack, mechanical)


def plane_net_fields(stack: StackSpec | None = None) -> list[Field]:
    """``PLANE<n>NETNAME`` for n = 1 … 16: the net of each plane of ``stack``, ``(No Net)`` otherwise."""
    nets = _stack(stack).plane_nets
    return [
        (f"PLANE{index}NETNAME", nets[index - 1] if index <= len(nets) else NO_NET)
        for index in range(1, PLANE_COUNT + 1)
    ]


def view_configurations() -> list[list[Field]]:
    """The four lines of the 2D and 3D view configurations and their file names."""
    view_3d: list[Field] = [
        ("CFGALL.CONFIGURATIONKIND", "3"),
        ("CFGALL.CONFIGURATIONDESC", "Enter%20description%20of%20new%20view%20configuration"),
        *((f"CFG3D.{key}", value) for key, value in _VIEW_3D),
    ]
    return [
        [RECORD, ("2DCONFIGTYPE", ".config_2dsimple"), ("2DCONFIGURATION", _nested(_view_2d()))],
        [RECORD, ("2DCONFIGFULLFILENAME", "(Not Saved)")],
        [RECORD, ("3DCONFIGTYPE", ".config_3d"), ("3DCONFIGURATION", _nested(view_3d))],
        [RECORD, ("3DCONFIGFULLFILENAME", "(Not Saved)")],
    ]


def _legacy_layers(
    stack: StackSpec | None = None, mechanical: Sequence[int] = ENABLED_MECHANICAL
) -> list[Field]:
    """``LAYER<n>…`` for n = 1 … 82 in groups of five, and the sixteen ``LAYERV7_<i>…`` layers. The copper
    layers of ``stack`` are linked from top to bottom; each carries its thickness and, but for the bottom,
    the dielectric below it."""
    spec = _stack(stack)
    chain = (0, *spec.copper, 0)
    links = {layer: (chain[i], chain[i + 2]) for i, layer in enumerate(spec.copper)}
    below = dict(zip(spec.copper, spec.dielectrics, strict=False))
    links.update({n: (0, 1) for n in (33, 35, 37)})
    links.update({n: (32, 0) for n in (34, 36, 38)})
    enabled = {56 + n for n in mechanical}
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
            *(_copper_thickness(spec, long_id(layer)) if layer in spec.copper else _COPPER),
            *(below[layer].fields() if layer in below else _CORE),
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


def _layer_sets(stack: StackSpec | None = None, enabled: Sequence[int] = ENABLED_MECHANICAL) -> list[Field]:
    inner = _stack(stack).copper[1:-1]
    mids = [f"MidLayer{layer - 1}" for layer in inner if layer < rec.FIRST_PLANE]
    planes = [f"InternalPlane{layer - rec.FIRST_PLANE + 1}" for layer in inner if layer >= rec.FIRST_PLANE]
    mechanical = [f"Mechanical{n}" for n in enabled]
    top = ["MultiLayer", "TopPaste", "TopOverlay", "TopSolder"]
    bottom = ["BottomSolder", "BottomOverlay", "BottomPaste", "DrillGuide", "KeepOutLayer"]
    low, rest = bottom[:3], bottom[3:]
    all_layers = [*top, "TopLayer", *mids, "BottomLayer", *low, *planes, *rest, *mechanical, "DrillDrawing"]
    sets: tuple[tuple[str, list[str], str], ...] = (
        ("&All Layers", all_layers, "TOP"),
        ("&Signal Layers", ["MultiLayer", "TopLayer", *mids, "BottomLayer"], "TOP"),
        ("&Plane Layers", planes, "PLANE1" if planes else "UNKNOWN"),
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
    head: list[Field] = [
        ("FILENAME", filename),
        ("KIND", KIND),
        ("VERSION", VERSION),
        ("DATE", DATE),
        ("TIME", TIME),
        *stack_fields(used_layers),
    ]
    first, *later = legacy_lines()
    lines = [head + first, *later]
    view = _view_2d()
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
        *view_configurations(),
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
    "COPPER_THICKNESS",
    "DATE",
    "DIELECTRIC_TYPES",
    "Dielectric",
    "NO_NET",
    "STACKS",
    "StackSpec",
    "ENABLED_MECHANICAL",
    "enabled_mechanical",
    "KIND",
    "LINE_BREAK",
    "RECORD",
    "SNAP_GRID",
    "TIME",
    "VERSION",
    "board_fields",
    "board_records",
    "board_text",
    "guid",
    "layer_sets",
    "legacy_lines",
    "long_id",
    "plane_net_fields",
    "stack_fields",
    "view_configurations",
]
