# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Offline, Fenolite-authored reusable schematic symbols and footprint definitions."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model.board import Graphic, Pad
from fenolite.model.circuit import PinType
from fenolite.model.library import FootprintDef, SymbolDef, SymbolGraphic, SymbolPin, SymbolUnit

_NM = 1_000_000
_STROKE = 254_000
_GRID = 2_540_000
_HALF_GRID = 1_270_000


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """Stable metadata for one catalog definition."""

    lib_id: str
    kind: str
    category: str
    summary: str
    evidence: str
    sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _SymbolSpec:
    name: str
    category: str
    reference: str
    summary: str
    sources: tuple[str, ...]


_SYMBOL_SPECS = (
    _SymbolSpec("Resistor", "Passive", "R", "Generic two-terminal resistor", ("S-0314", "S-0343")),
    _SymbolSpec("Capacitor", "Passive", "C", "Generic non-polarized capacitor", ("S-0314",)),
    _SymbolSpec("Capacitor_Polarized", "Passive", "C", "Generic polarized capacitor", ("S-0314",)),
    _SymbolSpec("Capacitor_Ceramic", "Passive", "C", "Generic ceramic capacitor", ("S-0314", "S-0328")),
    _SymbolSpec(
        "Capacitor_Electrolytic",
        "Passive",
        "C",
        "Generic polarized electrolytic capacitor",
        ("S-0314", "S-0329"),
    ),
    _SymbolSpec(
        "Capacitor_Film", "Passive", "C", "Generic non-polarized film capacitor", ("S-0314", "S-0329")
    ),
    _SymbolSpec("Inductor", "Passive", "L", "Generic inductor", ("S-0314",)),
    _SymbolSpec("Common_Mode_Choke", "Passive", "L", "Conceptual two-winding common-mode choke", ("S-0345",)),
    _SymbolSpec("Ferrite_Bead", "Passive", "FB", "Generic two-terminal ferrite bead", ("S-0318",)),
    _SymbolSpec("Diode", "Discrete semiconductor", "D", "Generic two-terminal rectifier diode", ("S-0319",)),
    _SymbolSpec("Zener_Diode", "Discrete semiconductor", "D", "Generic Zener diode", ("S-0319", "S-0344")),
    _SymbolSpec("LED", "Optoelectronic semiconductor", "D", "Generic light-emitting diode", ("S-0319",)),
    _SymbolSpec(
        "Dual_LED_Common_Cathode",
        "Optoelectronic semiconductor",
        "D",
        "Conceptual common cathode dual LED; not a package pinout",
        ("S-0347",),
    ),
    _SymbolSpec(
        "Bridge_Rectifier",
        "Discrete semiconductor",
        "BR",
        "Generic four-terminal bridge rectifier",
        ("S-0329", "S-0342"),
    ),
    _SymbolSpec(
        "Optocoupler",
        "Optoelectronic semiconductor",
        "U",
        "Generic LED-to-photodetector coupler block",
        ("S-0325",),
    ),
    _SymbolSpec("Fuse", "Protection", "F", "Generic two-terminal fuse", ("S-0326",)),
    _SymbolSpec(
        "Varistor", "Protection", "RV", "Generic two-terminal voltage-dependent resistor", ("S-0320",)
    ),
    _SymbolSpec("Surge_Suppressor", "Protection", "D", "Generic two-terminal surge suppressor", ("S-0320",)),
    _SymbolSpec(
        "Gas_Discharge_Tube",
        "Protection",
        "SA",
        "Generic non-polar two-electrode discharge tube",
        ("S-0346",),
    ),
    _SymbolSpec(
        "Operational_Amplifier",
        "Power and control IC",
        "U",
        "Conceptual five-function op amp; not a device pinout",
        ("S-0317", "S-0341"),
    ),
    _SymbolSpec(
        "Comparator", "Power and control IC", "U", "Conceptual comparator; not a device pinout", ("S-0317",)
    ),
    _SymbolSpec(
        "Linear_Regulator",
        "Power and control IC",
        "U",
        "Conceptual three-function linear regulator; not a device pinout",
        ("S-0316", "S-0332"),
    ),
    _SymbolSpec(
        "Offline_Power_Controller",
        "Power and control IC",
        "U",
        "Conceptual offline power-controller block; not a device pinout",
        ("S-0316", "S-0330"),
    ),
    _SymbolSpec(
        "Microcontroller",
        "Power and control IC",
        "U",
        "Conceptual controller block; not a device pinout",
        ("S-0316",),
    ),
    _SymbolSpec(
        "Power_Module",
        "Power and control IC",
        "U",
        "Conceptual power-module block; not a device pinout",
        ("S-0316", "S-0331"),
    ),
    _SymbolSpec(
        "Connector_2", "Electromechanical interface", "J", "Generic two-circuit connector", ("S-0324",)
    ),
    _SymbolSpec(
        "Connector_3", "Electromechanical interface", "J", "Generic three-circuit connector", ("S-0324",)
    ),
    _SymbolSpec(
        "Connector_4", "Electromechanical interface", "J", "Generic four-circuit connector", ("S-0324",)
    ),
    _SymbolSpec(
        "Terminal_1Pin", "Electromechanical interface", "J", "Generic single-circuit terminal", ("S-0324",)
    ),
)

_FOOTPRINT_SPECS = (
    ("Chip_0402", "Chip passive", "Generic two-terminal 0402 chip land", ("S-0315", "S-0333")),
    ("Chip_0603", "Chip passive", "Generic two-terminal 0603 chip land", ("S-0315", "S-0333")),
    ("Chip_0805", "Chip passive", "Generic two-terminal 0805 chip land", ("S-0315", "S-0333")),
    ("Chip_1206", "Chip passive", "Generic two-terminal 1206 chip land", ("S-0315", "S-0333")),
    ("SOT23_3", "Small-outline semiconductor", "Three-lead SOT-23 package land", ("S-0322", "S-0334")),
    ("SOT23_5", "Small-outline IC", "Five-lead SOT-23 package land", ("S-0323", "S-0335")),
    ("SC70_5", "Small-outline IC", "Five-lead SC-70 package land", ("S-0323", "S-0335")),
    ("SOT89_3", "Small-outline semiconductor", "Three-lead SOT89 package land", ("S-0322", "S-0338")),
    (
        "SOIC_8",
        "Small-outline IC",
        "Eight-lead 1.27 mm-pitch small-outline package land",
        ("S-0323", "S-0336"),
    ),
    (
        "DO214AC",
        "Diode package",
        "Two-terminal DO-214AC / SMA land from manufacturer suggested layout",
        ("S-0321",),
    ),
    ("LQFP32_P0.8", "Leaded IC", "32-lead LQFP package with 0.8 mm pitch", ("S-0327", "S-0337")),
    (
        "Header_1x2_P2.5",
        "Through-hole connector",
        "Two-position 2.5 mm-pitch generic header land",
        ("S-0324",),
    ),
    (
        "Header_1x3_P2.5",
        "Through-hole connector",
        "Three-position 2.5 mm-pitch generic header land",
        ("S-0324",),
    ),
    (
        "Header_1x4_P2.5",
        "Through-hole connector",
        "Four-position 2.5 mm-pitch generic header land",
        ("S-0324",),
    ),
)

_FOOTPRINT_NAMES = tuple(spec[0] for spec in _FOOTPRINT_SPECS)
ENTRIES = tuple(
    sorted(
        [
            CatalogEntry(
                f"Fenolite:{spec.name}", "symbol", spec.category, spec.summary, "INFERRED", spec.sources
            )
            for spec in _SYMBOL_SPECS
        ]
        + [
            CatalogEntry(f"Fenolite:{name}", "footprint", category, summary, "INFERRED", sources)
            for name, category, summary, sources in _FOOTPRINT_SPECS
        ],
        key=lambda entry: entry.lib_id,
    )
)


def list_entries(*, kind: str | None = None, query: str | None = None) -> tuple[CatalogEntry, ...]:
    """List entries in stable ID order, optionally filtering by kind and case-insensitive text."""
    found = ENTRIES
    if kind is not None:
        found = tuple(entry for entry in found if entry.kind == kind)
    if query:
        needle = query.casefold()
        found = tuple(
            entry
            for entry in found
            if needle in (entry.lib_id + " " + entry.category + " " + entry.summary).casefold()
        )
    return tuple(sorted(found, key=lambda entry: entry.lib_id))


def _pin(
    number: str,
    name: str,
    x: int,
    y: int,
    *,
    etype: PinType = "passive",
    rotation: int = 0,
    length: int = _GRID,
) -> SymbolPin:
    return SymbolPin(number, name, etype, Point(x, y), rotation=rotation, length=length, unit=1, body_style=1)  # type: ignore[arg-type]


def _line(a: tuple[int, int], b: tuple[int, int], width: int = _STROKE) -> SymbolGraphic:
    return SymbolGraphic("line", (Point(*a), Point(*b)), width)


def _rect(x1: int, y1: int, x2: int, y2: int, width: int = _STROKE, *, filled: bool = False) -> SymbolGraphic:
    return SymbolGraphic("rect", (Point(x1, y1), Point(x2, y2)), width, filled)


def _coil_path(start_x: int, baseline: int, direction: int) -> tuple[SymbolGraphic, ...]:
    heights = (
        0,
        248_000,
        486_000,
        705_000,
        898_000,
        1_057_000,
        1_174_000,
        1_246_000,
        1_270_000,
        1_246_000,
        1_174_000,
        1_057_000,
        898_000,
        705_000,
        486_000,
        248_000,
        0,
    )
    return tuple(
        _line(
            (start_x + coil * _HALF_GRID + step * 79_375, baseline + direction * heights[step]),
            (start_x + coil * _HALF_GRID + (step + 1) * 79_375, baseline + direction * heights[step + 1]),
        )
        for coil in range(4)
        for step in range(16)
    )


def _symbol_graph(name: str) -> tuple[tuple[SymbolPin, ...], tuple[SymbolGraphic, ...]]:
    def left(
        number: str,
        label: str,
        y: int = 0,
        etype: PinType = "passive",
        *,
        outer: int = 2 * _GRID,
        length: int = _GRID,
    ) -> SymbolPin:
        return _pin(number, label, -outer, y, etype=etype, rotation=0, length=length)

    def right(
        number: str,
        label: str,
        y: int = 0,
        etype: PinType = "passive",
        *,
        outer: int = 2 * _GRID,
        length: int = _GRID,
    ) -> SymbolPin:
        return _pin(number, label, outer, y, etype=etype, rotation=180_000_000, length=length)

    two = (left("1", "A"), right("2", "B"))
    if name in {
        "Resistor",
        "Capacitor",
        "Capacitor_Polarized",
        "Capacitor_Ceramic",
        "Capacitor_Electrolytic",
        "Capacitor_Film",
        "Inductor",
        "Ferrite_Bead",
        "Fuse",
        "Varistor",
        "Surge_Suppressor",
    }:
        if name == "Resistor":
            vertices = (
                (-_GRID, 0),
                (-1_905_000, 1_050_000),
                (-1_270_000, -1_050_000),
                (-635_000, 1_050_000),
                (0, -1_050_000),
                (635_000, 1_050_000),
                (1_270_000, -1_050_000),
                (1_905_000, 1_050_000),
                (_GRID, 0),
            )
            return two, tuple(_line(a, b) for a, b in pairwise(vertices))
        if name in {
            "Capacitor",
            "Capacitor_Ceramic",
            "Capacitor_Film",
            "Capacitor_Polarized",
            "Capacitor_Electrolytic",
        }:
            polarized = name in {"Capacitor_Polarized", "Capacitor_Electrolytic"}
            graphics = (
                _line((-_HALF_GRID, -_GRID), (-_HALF_GRID, _GRID)),
                _line((_HALF_GRID, -_GRID), (_HALF_GRID, _GRID), 635_000 if polarized else _STROKE),
            )
            if polarized:
                graphics += (
                    _line((-2_200_000, 1_500_000), (-2_200_000, 2_300_000)),
                    _line((-2_600_000, 1_900_000), (-1_800_000, 1_900_000)),
                )
            labels = ("+", "-") if polarized else ("A", "B")
            return (
                left("1", labels[0], length=3 * _HALF_GRID),
                right("2", labels[1], length=3 * _HALF_GRID),
            ), graphics
        if name == "Inductor":
            return two, _coil_path(-_GRID, 0, 1)
        if name == "Ferrite_Bead":
            return two, (
                _rect(-_GRID, -_HALF_GRID, _GRID, _HALF_GRID),
                _line((-900_000, 800_000), (500_000, -800_000)),
                _line((-100_000, 800_000), (1_300_000, -800_000)),
            )
        if name == "Fuse":
            vertices = (
                (-_GRID, 0),
                (-2_100_000, 300_000),
                (-1_650_000, 650_000),
                (-1_200_000, 800_000),
                (-750_000, 680_000),
                (-350_000, 340_000),
                (0, 0),
                (350_000, -340_000),
                (750_000, -680_000),
                (1_200_000, -800_000),
                (1_650_000, -650_000),
                (2_100_000, -300_000),
                (_GRID, 0),
            )
            return two, tuple(_line(a, b) for a, b in pairwise(vertices))
        if name == "Varistor":
            return two, (
                _rect(-_GRID, -_HALF_GRID, _GRID, _HALF_GRID),
                _line((-1_700_000, 1_800_000), (1_700_000, -1_800_000)),
                _line((1_700_000, -1_800_000), (2_100_000, -1_800_000)),
            )
        if name == "Surge_Suppressor":
            return two, (
                _rect(-_GRID, -_HALF_GRID, _GRID, _HALF_GRID),
                _line((-1_200_000, 650_000), (0, 0)),
                _line((-1_200_000, -650_000), (0, 0)),
                _line((0, 0), (1_200_000, 650_000)),
                _line((0, 0), (1_200_000, -650_000)),
            )
    if name == "Common_Mode_Choke":
        pins = (
            left("1", "A1", 2 * _GRID, outer=3 * _GRID),
            left("2", "A2", -2 * _GRID, outer=3 * _GRID),
            right("3", "B1", 2 * _GRID, outer=3 * _GRID),
            right("4", "B2", -2 * _GRID, outer=3 * _GRID),
        )
        return pins, (
            _line((-2 * _GRID, 2 * _GRID), (-_GRID, 2 * _GRID)),
            *_coil_path(-_GRID, 2 * _GRID, 1),
            _line((_GRID, 2 * _GRID), (2 * _GRID, 2 * _GRID)),
            _line((-2 * _GRID, -2 * _GRID), (-_GRID, -2 * _GRID)),
            *_coil_path(-_GRID, -2 * _GRID, -1),
            _line((_GRID, -2 * _GRID), (2 * _GRID, -2 * _GRID)),
            _line((-_GRID, 750_000), (_GRID, 750_000)),
            _line((-_GRID, -750_000), (_GRID, -750_000)),
        )
    if name == "Gas_Discharge_Tube":
        return two, (
            SymbolGraphic("circle", (Point(0, 0), Point(_GRID, 0)), _STROKE),
            _line((-_GRID, 0), (-1_400_000, 0)),
            _line((-1_400_000, -850_000), (-600_000, 0)),
            _line((-1_400_000, 850_000), (-600_000, 0)),
            _line((_GRID, 0), (1_400_000, 0)),
            _line((1_400_000, -850_000), (600_000, 0)),
            _line((1_400_000, 850_000), (600_000, 0)),
        )
    if name in {"Diode", "Zener_Diode", "LED"}:
        pins = (left("1", "A", length=3 * _HALF_GRID), right("2", "K", length=3 * _HALF_GRID))
        diode_body = SymbolGraphic(
            "polygon",
            (Point(-_HALF_GRID, -1_700_000), Point(_HALF_GRID, 0), Point(-_HALF_GRID, 1_700_000)),
            _STROKE,
            True,
        )
        if name == "Zener_Diode":
            graphics = (
                diode_body,
                _line((900_000, -1_900_000), (_HALF_GRID, -1_400_000)),
                _line((_HALF_GRID, -1_400_000), (_HALF_GRID, 1_400_000)),
                _line((_HALF_GRID, 1_400_000), (1_640_000, 1_900_000)),
            )
        else:
            graphics = (diode_body, _line((_HALF_GRID, -1_900_000), (_HALF_GRID, 1_900_000)))
        if name == "LED":
            graphics += (
                _line((-400_000, 2_000_000), (800_000, 3_200_000)),
                _line((800_000, 2_000_000), (2_000_000, 3_200_000)),
                _line((800_000, 3_200_000), (400_000, 3_100_000)),
                _line((800_000, 3_200_000), (700_000, 2_800_000)),
                _line((2_000_000, 3_200_000), (1_600_000, 3_100_000)),
                _line((2_000_000, 3_200_000), (1_900_000, 2_800_000)),
            )
        return pins, graphics
    if name == "Bridge_Rectifier":

        def diode_branch(start: tuple[int, int], end: tuple[int, int]) -> tuple[SymbolGraphic, ...]:
            sx = 1 if end[0] > start[0] else -1
            sy = 1 if end[1] > start[1] else -1
            base = (start[0] + sx * 1_905_000, start[1] + sy * 1_905_000)
            cathode = (start[0] + sx * 3_175_000, start[1] + sy * 3_175_000)
            side = (-sy * 450_000, sx * 450_000)
            return (
                _line(start, base),
                SymbolGraphic(
                    "polygon",
                    (
                        Point(base[0] + side[0], base[1] + side[1]),
                        Point(*cathode),
                        Point(base[0] - side[0], base[1] - side[1]),
                    ),
                    _STROKE,
                ),
                _line(
                    (cathode[0] + side[0], cathode[1] + side[1]),
                    (cathode[0] - side[0], cathode[1] - side[1]),
                ),
                _line(cathode, end),
            )

        pins = (
            left("1", "~", outer=3 * _GRID),
            right("2", "~", outer=3 * _GRID),
            _pin("3", "+", 0, 3 * _GRID, rotation=270_000_000),
            _pin("4", "-", 0, -3 * _GRID, rotation=90_000_000),
        )
        left_ac, right_ac = (-2 * _GRID, 0), (2 * _GRID, 0)
        positive, negative = (0, 2 * _GRID), (0, -2 * _GRID)
        return pins, (
            *diode_branch(left_ac, positive),
            *diode_branch(right_ac, positive),
            *diode_branch(negative, left_ac),
            *diode_branch(negative, right_ac),
        )
    if name == "Optocoupler":
        pins = (
            left("1", "A", _GRID, outer=3 * _GRID),
            left("2", "K", -_GRID, outer=3 * _GRID),
            right("3", "C", _GRID, outer=3 * _GRID),
            right("4", "E", -_GRID, outer=3 * _GRID),
        )
        return pins, (
            _rect(-2 * _GRID, -2 * _GRID, 2 * _GRID, 2 * _GRID, filled=True),
            _line((-2 * _GRID, _GRID), (-4_250_000, _GRID)),
            _line((-4_250_000, _GRID), (-4_250_000, 0)),
            _line((-4_250_000, 0), (-3_250_000, 0)),
            SymbolGraphic(
                "polygon",
                (Point(-3_250_000, -900_000), Point(-1_750_000, 0), Point(-3_250_000, 900_000)),
                _STROKE,
                True,
            ),
            _line((-1_750_000, -1_100_000), (-1_750_000, 1_100_000)),
            _line((-1_750_000, 0), (-1_750_000, -_GRID)),
            _line((-1_750_000, -_GRID), (-2 * _GRID, -_GRID)),
            _line((-900_000, 1_100_000), (1_000_000, 1_100_000)),
            _line((1_000_000, 1_100_000), (550_000, 1_400_000)),
            _line((1_000_000, 1_100_000), (550_000, 800_000)),
            _line((-900_000, 300_000), (1_000_000, 300_000)),
            _line((1_000_000, 300_000), (550_000, 600_000)),
            _line((1_000_000, 300_000), (550_000, 0)),
            _line((1_900_000, -1_150_000), (1_900_000, 1_150_000)),
            _line((1_900_000, 700_000), (3_200_000, _GRID)),
            _line((3_200_000, _GRID), (2 * _GRID, _GRID)),
            _line((1_900_000, -700_000), (3_200_000, -_GRID)),
            _line((3_200_000, -_GRID), (2 * _GRID, -_GRID)),
        )
    if name == "Dual_LED_Common_Cathode":
        pins = (
            left("1", "A1", _GRID, "input", outer=3 * _GRID),
            left("2", "A2", -_GRID, "input", outer=3 * _GRID),
            right("3", "K", 0, "passive", outer=3 * _GRID),
        )
        graphics = [_rect(-2 * _GRID, -2 * _GRID, 2 * _GRID, 2 * _GRID, filled=True)]
        for y in (_GRID, -_GRID):
            graphics.extend(
                (
                    _line((-2 * _GRID, y), (-1_100_000, y)),
                    SymbolGraphic(
                        "polygon",
                        (Point(-1_100_000, y - 650_000), Point(0, y), Point(-1_100_000, y + 650_000)),
                        _STROKE,
                        True,
                    ),
                    _line((0, y - 750_000), (0, y + 750_000)),
                    _line((0, y), (1_400_000, y)),
                )
            )
        graphics.extend(
            (
                _line((1_400_000, -_GRID), (1_400_000, _GRID)),
                _line((1_400_000, 0), (2 * _GRID, 0)),
            )
        )
        return pins, tuple(graphics)
    if name in {"Operational_Amplifier", "Comparator"}:
        pins = (
            right("1", "", etype="output", outer=3 * _GRID),
            left("2", "+", _GRID, "input", outer=3 * _GRID, length=3 * _HALF_GRID),
            left("3", "-", -_GRID, "input", outer=3 * _GRID, length=3 * _HALF_GRID),
            _pin("4", "V+", 0, 3 * _GRID, etype="power_in", rotation=270_000_000, length=2 * _GRID),
            _pin("5", "V-", 0, -3 * _GRID, etype="power_in", rotation=90_000_000, length=2 * _GRID),
        )
        return pins, (
            SymbolGraphic(
                "polygon",
                (
                    Point(-3 * _HALF_GRID, -2 * _GRID),
                    Point(-3 * _HALF_GRID, 2 * _GRID),
                    Point(3 * _HALF_GRID, 0),
                ),
                _STROKE,
            ),
            _line((3 * _HALF_GRID, 0), (2 * _GRID, 0)),
        )
    if name == "Linear_Regulator":
        pins = (
            left("1", "IN", etype="power_in", outer=3 * _GRID, length=3 * _HALF_GRID),
            _pin("2", "GND", 0, -3 * _GRID, etype="power_in", rotation=90_000_000, length=3 * _HALF_GRID),
            right("3", "OUT", etype="power_out", outer=3 * _GRID, length=3 * _HALF_GRID),
        )
        return pins, (_rect(-3 * _HALF_GRID, -3 * _HALF_GRID, 3 * _HALF_GRID, 3 * _HALF_GRID, filled=True),)
    if name == "Offline_Power_Controller":
        pins = (
            left("1", "VIN", _GRID, "power_in", outer=3 * _GRID),
            left("2", "GND", -_GRID, outer=3 * _GRID),
            right("3", "SW", _GRID, "output", outer=3 * _GRID),
            right("4", "FB", -_GRID, "input", outer=3 * _GRID),
        )
        return pins, (_rect(-2 * _GRID, -2 * _GRID, 2 * _GRID, 2 * _GRID, filled=True),)
    if name == "Microcontroller":
        ys = (2 * _GRID, _GRID, -_GRID, -2 * _GRID)
        pins = tuple(
            left(str(i + 1), label, y, outer=4 * _GRID)
            for i, (label, y) in enumerate(zip(("VDD", "VSS", "RESET", "IO1"), ys, strict=True))
        ) + tuple(
            right(str(i + 5), label, y, outer=4 * _GRID)
            for i, (label, y) in enumerate(zip(("IO2", "CLK", "ADC", "UART"), ys, strict=True))
        )
        return pins, (_rect(-3 * _GRID, -3 * _GRID, 3 * _GRID, 3 * _GRID, filled=True),)
    if name == "Power_Module":
        labels = ("DC+", "DC-", "U", "V", "W", "IN1", "IN2", "IN3")
        ys = (2 * _GRID, _GRID, -_GRID, -2 * _GRID)
        pins = tuple(
            left(str(i + 1), label, ys[i], outer=4 * _GRID) for i, label in enumerate(labels[:4])
        ) + tuple(right(str(i + 5), label, ys[i], outer=4 * _GRID) for i, label in enumerate(labels[4:]))
        return pins, (_rect(-3 * _GRID, -3 * _GRID, 3 * _GRID, 3 * _GRID, filled=True),)
    if name.startswith("Connector_"):
        count = int(name.rsplit("_", 1)[1])
        ys = tuple(((count - 1 - 2 * i) * _GRID) // 2 for i in range(count))
        pins = tuple(left(str(i + 1), "Passive", y) for i, y in enumerate(ys))
        graphics = (
            _rect(-_GRID, ys[-1] - _HALF_GRID, _HALF_GRID, ys[0] + _HALF_GRID, filled=True),
            *(_rect(-_GRID, y - 635_000, -_HALF_GRID, y + 635_000) for y in ys),
        )
        return pins, graphics
    if name == "Terminal_1Pin":
        return (left("1", "Passive", length=4_130_000),), (
            _rect(-950_000, -950_000, 950_000, 950_000),
            _line((100_000, -450_000), (100_000, 450_000)),
        )
    raise KeyError(name)


def _symbol(spec: _SymbolSpec) -> SymbolDef:
    pins, graphics = _symbol_graph(spec.name)
    return SymbolDef(
        id=derived_id("sym", "fenolite.catalog", f"Fenolite:{spec.name}"),
        native_ids={"fenolite": f"Fenolite:{spec.name}"},
        name=spec.name,
        library="Fenolite",
        properties={"Reference": spec.reference, "Value": spec.name, "Description": spec.summary},
        units=(SymbolUnit(1, 1),),
        pins=pins,
        graphics=graphics,
        pin_names_hidden=spec.category in {"Passive", "Protection", "Electromechanical interface"}
        or spec.name in {"Diode", "Zener_Diode", "LED"},
    )


def _pad(
    name: str,
    number: str,
    x: int,
    y: int,
    sx: int,
    sy: int,
    *,
    drill: int | None = None,
    pad_id: str | None = None,
) -> Pad:
    kind = "thru_hole" if drill is not None else "smd"
    layers = ("*.Cu", "*.Mask") if drill is not None else ("F.Cu", "F.Paste", "F.Mask")
    return Pad(
        id=derived_id("pad", "fenolite.catalog", f"{name}:{pad_id or number}"),
        number=number,
        shape="circle" if drill is not None else "rect",
        size=Size(sx, sy),
        position=Point(x, y),
        kind=kind,  # type: ignore[arg-type]
        drill=drill,
        layers=layers,
    )


def _outline(name: str, half_x: int, half_y: int, *, courtyard: bool = False) -> tuple[Graphic, ...]:
    layer = "F.CrtYd" if courtyard else "F.Fab"
    width = 50_000 if courtyard else 100_000
    return (
        Graphic(
            id=derived_id("gfx", "fenolite.catalog", f"{name}:{layer}"),
            kind="rect",
            layer=layer,
            points=(Point(-half_x, -half_y), Point(half_x, half_y)),
            width=width,
        ),
    )


def _make_footprint(
    name: str, pads: tuple[Pad, ...], body_x: int, body_y: int, *, through_hole: bool = False
) -> FootprintDef:
    desc = next(spec[2] for spec in _FOOTPRINT_SPECS if spec[0] == name)
    extent_x = max((body_x // 2, *(abs(p.position.x) + p.size.w // 2 for p in pads)))
    extent_y = max((body_y // 2, *(abs(p.position.y) + p.size.h // 2 for p in pads)))
    graphics = _outline(name, body_x // 2, body_y // 2) + _outline(
        name, extent_x + 500_000, extent_y + 500_000, courtyard=True
    )
    return FootprintDef(
        id=derived_id("fpd", "fenolite.catalog", f"Fenolite:{name}"),
        native_ids={"fenolite": f"Fenolite:{name}"},
        name=name,
        library="Fenolite",
        description=f"{desc}; land pattern remains INFERRED and requires part-specific review",
        kind="through_hole" if through_hole else "smd",
        pads=pads,
        graphics=graphics,
    )


def _chip_footprint(size_name: str) -> FootprintDef:
    # Yageo bodies and Vishay IPC-7351 reflow resistor-land example; generic use remains INFERRED.
    body_um = {"0402": (1000, 500), "0603": (1600, 800), "0805": (2000, 1250), "1206": (3100, 1600)}
    land_um = {
        "0402": (400, 550, 600),
        "0603": (700, 900, 1000),
        "0805": (1000, 900, 1450),
        "1206": (1750, 1150, 1800),
    }
    length_um, width_um = body_um[size_name]
    gap_um, pad_length_um, pad_width_um = land_um[size_name]
    center = (gap_um + pad_length_um) * 1000 // 2
    pads = tuple(
        _pad(f"Chip_{size_name}", number, x, 0, pad_length_um * 1000, pad_width_um * 1000)
        for number, x in (("1", -center), ("2", center))
    )
    return _make_footprint(f"Chip_{size_name}", pads, length_um * 1000, width_um * 1000)


def _row_pads(name: str, count: int, pitch: int, row_spacing: int, sx: int, sy: int) -> tuple[Pad, ...]:
    """Create counter-clockwise numbered dual-row pads starting at the upper-left position."""
    per_side = count // 2
    offsets = tuple(((per_side - 1 - 2 * i) * pitch) // 2 for i in range(per_side))
    coords: list[tuple[int, int]] = []
    coords.extend((-row_spacing // 2, y) for y in offsets)
    coords.extend((row_spacing // 2, y) for y in reversed(offsets))
    return tuple(_pad(name, str(i + 1), x, y, sx, sy) for i, (x, y) in enumerate(coords))


def _footprint(name: str) -> FootprintDef:
    if name.startswith("Chip_"):
        return _chip_footprint(name.rsplit("_", 1)[1])
    if name == "SOT23_3":
        pads = (
            _pad(name, "1", -1_050_000, 950_000, 1_300_000, 600_000),
            _pad(name, "2", -1_050_000, -950_000, 1_300_000, 600_000),
            _pad(name, "3", 1_050_000, 0, 1_300_000, 600_000),
        )
        return _make_footprint(name, pads, 1_300_000, 2_900_000)
    if name in {"SOT23_5", "SC70_5"}:
        small = name == "SC70_5"
        pitch = 650_000 if small else 950_000
        row = 2_200_000 if small else 2_600_000
        sx, sy = (950_000, 400_000) if small else (1_100_000, 600_000)
        ys = (pitch, 0, -pitch)
        pads = tuple(_pad(name, str(i + 1), -row // 2, y, sx, sy) for i, y in enumerate(ys)) + tuple(
            _pad(name, str(i + 4), row // 2, y, sx, sy) for i, y in enumerate((-pitch, pitch))
        )
        if small:
            return _make_footprint(name, pads, 1_250_000, 2_000_000)
        return _make_footprint(name, pads, 1_600_000, 2_900_000)
    if name == "SOT89_3":
        # Diodes SOT89 reference T-shaped terminal 2, split into overlapping same-number rectangles.
        pads = (
            _pad(name, "1", -1_500_000, -1_450_000, 580_000, 1_630_000),
            _pad(name, "2", 0, -1_490_000, 760_000, 1_550_000),
            _pad(name, "3", 1_500_000, -1_450_000, 580_000, 1_630_000),
            _pad(name, "2", 0, 750_000, 1_933_000, 3_030_000, pad_id="tab"),
        )
        return _make_footprint(name, pads, 4_500_000, 2_500_000)
    if name == "SOIC_8":
        pads = _row_pads(name, 8, 1_270_000, 5_400_000, 1_550_000, 600_000)
        return _make_footprint(name, pads, 3_900_000, 4_900_000)
    if name == "DO214AC":
        # Diodes Inc. suggested reference land dimensions; verify against the exact device and process.
        pads = (
            _pad(name, "1", -1_800_000, 0, 2_000_000, 2_100_000),
            _pad(name, "2", 1_800_000, 0, 2_000_000, 2_100_000),
        )
        return _make_footprint(name, pads, 4_500_000, 2_600_000)
    if name == "LQFP32_P0.8":
        count, pitch = 8, 800_000
        half_span = (count - 1) * pitch // 2
        coords: list[tuple[int, int]] = []
        coords.extend((-4_200_000, y) for y in range(half_span, -half_span - 1, -pitch))
        coords.extend((x, -4_200_000) for x in range(-half_span, half_span + 1, pitch))
        coords.extend((4_200_000, y) for y in range(-half_span, half_span + 1, pitch))
        coords.extend((x, 4_200_000) for x in range(half_span, -half_span - 1, -pitch))
        pads = tuple(
            _pad(
                name,
                str(i + 1),
                x,
                y,
                1_500_000 if abs(x) == 4_200_000 else 550_000,
                550_000 if abs(x) == 4_200_000 else 1_500_000,
            )
            for i, (x, y) in enumerate(coords)
        )
        return _make_footprint(name, pads, 7_000_000, 7_000_000)
    if name.startswith("Header_1x"):
        count = int(name.split("x", 1)[1].split("_", 1)[0])
        pitch = 2_500_000
        pads = tuple(
            _pad(
                name, str(i + 1), 0, ((count - 1 - 2 * i) * pitch) // 2, 1_800_000, 1_800_000, drill=1_000_000
            )
            for i in range(count)
        )
        return _make_footprint(
            name, pads, 2_500_000, max(2_500_000, (count - 1) * pitch + 2_000_000), through_hole=True
        )
    raise KeyError(name)


def get_symbol(lib_id: str) -> SymbolDef:
    """Return a built-in generic symbol by stable ``library:name`` ID."""
    if not lib_id.startswith("Fenolite:"):
        raise KeyError(lib_id)
    name = lib_id.split(":", 1)[1]
    spec = next((spec for spec in _SYMBOL_SPECS if spec.name == name), None)
    if spec is None:
        raise KeyError(lib_id)
    return _symbol(spec)


def get_footprint(lib_id: str) -> FootprintDef:
    """Return a built-in generic footprint by stable ``library:name`` ID."""
    if not lib_id.startswith("Fenolite:"):
        raise KeyError(lib_id)
    name = lib_id.split(":", 1)[1]
    if name not in _FOOTPRINT_NAMES:
        raise KeyError(lib_id)
    return _footprint(name)


__all__ = ["CatalogEntry", "ENTRIES", "get_footprint", "get_symbol", "list_entries"]
