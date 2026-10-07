# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independently authored functional symbols; coordinates here are integer micrometres.

Terminal numbers are conceptual roles, never an automatic device/package pinout.
Public functional references are registered in docs/catalog/target-20-symbols.md.
"""

from __future__ import annotations

from itertools import pairwise

from fenolite.core.coords import Point
from fenolite.model.circuit import PinType
from fenolite.model.library import SymbolGraphic, SymbolPin

SYMBOL_SPECS: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    ("BJT_NPN", "Discrete semiconductor", "Q", "Conceptual NPN B/C/E; not a device pinout", ("S-0423",)),
    ("BJT_PNP", "Discrete semiconductor", "Q", "Conceptual PNP B/C/E; not a device pinout", ("S-0424",)),
    (
        "MOSFET_N_Channel",
        "Discrete semiconductor",
        "Q",
        "Conceptual N-channel enhancement G/D/S; not a device pinout",
        ("S-0425",),
    ),
    (
        "MOSFET_P_Channel",
        "Discrete semiconductor",
        "Q",
        "Conceptual P-channel enhancement G/D/S; not a device pinout",
        ("S-0426",),
    ),
    (
        "IGBT",
        "Discrete semiconductor",
        "Q",
        "Conceptual bare IGBT G/C/E, no integrated diode; not a device pinout",
        ("S-0427",),
    ),
    ("SCR", "Discrete semiconductor", "Q", "Conceptual SCR A/K/G; not a device pinout", ("S-0428",)),
    ("TRIAC", "Discrete semiconductor", "Q", "Conceptual TRIAC MT2/MT1/G; not a device pinout", ("S-0429",)),
    (
        "Schottky_Diode",
        "Discrete semiconductor",
        "D",
        "Conceptual Schottky A/K; not a device pinout",
        ("S-0430",),
    ),
    (
        "TVS_Bidirectional",
        "Protection",
        "D",
        "Conceptual non-polar bidirectional TVS A/B; not a device pinout",
        ("S-0431",),
    ),
    (
        "Potentiometer",
        "Passive",
        "RV",
        "Conceptual adjustable resistance A/W/B; not a device pinout",
        ("S-0432",),
    ),
    (
        "Thermistor_NTC",
        "Passive",
        "RT",
        "Conceptual negative temperature coefficient resistor; not a device pinout",
        ("S-0433",),
    ),
    (
        "Thermistor_PTC",
        "Passive",
        "RT",
        "Conceptual positive temperature coefficient resistor; not a device pinout",
        ("S-0434",),
    ),
    ("Crystal", "Passive", "Y", "Conceptual two-electrode crystal X1/X2; not a device pinout", ("S-0416",)),
    (
        "Switch_SPST",
        "Electromechanical interface",
        "SW",
        "Conceptual SPST contact, open at rest; not a device pinout",
        ("S-0435",),
    ),
    (
        "Switch_SPDT",
        "Electromechanical interface",
        "SW",
        "Conceptual SPDT COM/NC/NO, COM-NC at rest; not a device pinout",
        ("S-0435",),
    ),
    (
        "Pushbutton_NO",
        "Electromechanical interface",
        "SW",
        "Conceptual four-terminal normally open button, common 1-2 and 3-4; not a device pinout",
        ("S-0417", "S-0418"),
    ),
    (
        "Relay_SPDT",
        "Electromechanical interface",
        "K",
        "Conceptual five-function SPDT relay, COM-NC unenergized; not a device pinout",
        ("S-0436",),
    ),
    (
        "Transformer",
        "Passive",
        "T",
        "Conceptual two-winding transformer P1/P2/S1/S2; not a device pinout",
        ("S-0437",),
    ),
    (
        "Photodiode",
        "Optoelectronic semiconductor",
        "D",
        "Conceptual incident-light photodiode A/K; not a device pinout",
        ("S-0438", "S-0440"),
    ),
    (
        "Phototransistor",
        "Optoelectronic semiconductor",
        "Q",
        "Conceptual incident-light NPN phototransistor C/E; not a device pinout",
        ("S-0439", "S-0440"),
    ),
)


def _point(x: int, y: int) -> Point:
    return Point(x * 1000, y * 1000)


def _line(a: tuple[int, int], b: tuple[int, int], width: int = 254) -> SymbolGraphic:
    return SymbolGraphic("line", (_point(*a), _point(*b)), width * 1000)


def _path(points: tuple[tuple[int, int], ...]) -> tuple[SymbolGraphic, ...]:
    return tuple(_line(a, b) for a, b in pairwise(points))


def _polygon(*points: tuple[int, int]) -> SymbolGraphic:
    # Background fill matches the current KiCad writer; never claim foreground fill.
    return SymbolGraphic("polygon", tuple(_point(*p) for p in points), 254_000, True)


def _head(tail: tuple[int, int], tip: tuple[int, int]) -> SymbolGraphic:
    """An outline triangle pointing from tail to tip, using integer geometry only."""
    dx, dy = tip[0] - tail[0], tip[1] - tail[1]
    norm = max(abs(dx), abs(dy))
    bx, by = tip[0] - dx * 650 // norm, tip[1] - dy * 650 // norm
    wx, wy = -dy * 300 // norm, dx * 300 // norm
    return _polygon(tip, (bx + wx, by + wy), (bx - wx, by - wy))


def _pin(
    number: str, name: str, x: int, y: int, rotation: int, length: int = 2540, etype: PinType = "passive"
) -> SymbolPin:
    return SymbolPin(
        number,
        name,
        etype,
        _point(x, y),
        rotation=rotation * 1_000_000,
        length=length * 1000,
        unit=1,
        body_style=1,
    )


def _transistor_pins(gate: str, upper: str, lower: str) -> tuple[SymbolPin, ...]:
    return (
        _pin("1", gate, -5080, 0, 0, etype="input"),
        _pin("2", upper, 2540, 5080, 270),
        _pin("3", lower, 2540, -5080, 90),
    )


def _bjt(pnp: bool = False) -> tuple[SymbolGraphic, ...]:
    graphics = _path(((-2540, 0), (-1270, 0))) + (
        _line((-1270, -1905), (-1270, 1905)),
        _line((-1270, 1270), (2540, 2540)),
        _line((-1270, -1270), (2540, -2540)),
    )
    tail, tip = ((1775, -2285), (875, -1985)) if pnp else ((875, -1985), (1775, -2285))
    return (*graphics, _head(tail, tip))


def _mosfet(p_channel: bool) -> tuple[SymbolGraphic, ...]:
    graphics = [
        _line((-2540, 0), (-1270, 0)),
        _line((-1270, -1905), (-1270, 1905)),
        *(_line((0, low), (0, high)) for low, high in ((-1905, -1016), (-508, 508), (1016, 1905))),
        *_path(((0, 1524), (2540, 1524), (2540, 2540))),
        *_path(((0, -1524), (2540, -1524), (2540, -2540))),
        *_path(((0, 0), (2540, 0), (2540, -1524))),
        _head((650, 0), (1500, 0)) if p_channel else _head((1500, 0), (650, 0)),
        *_path(((2540, 1524), (3810, 1524), (3810, 600))),
        *_path(((2540, -1524), (3810, -1524), (3810, -600))),
    ]
    direction = -1 if p_channel else 1
    graphics += [
        _polygon((3210, -direction * 600), (4410, -direction * 600), (3810, direction * 600)),
        _line((3210, direction * 600), (4410, direction * 600)),
    ]
    return tuple(graphics)


def _thyristor(triac: bool) -> tuple[tuple[SymbolPin, ...], tuple[SymbolGraphic, ...]]:
    pins = (
        _pin("1", "MT2" if triac else "A", 0, 5080, 270),
        _pin("2", "MT1" if triac else "K", 0, -5080, 90),
        _pin("3", "G", -5080, -2540, 0, etype="input"),
    )
    if not triac:
        graphics = (
            _polygon((-1270, 1270), (1270, 1270), (0, -1270)),
            _line((-1270, -1270), (1270, -1270)),
            _line((0, 2540), (0, 1270)),
            _line((0, -1270), (0, -2540)),
            _line((-2540, -2540), (0, -1270)),
        )
    else:
        graphics = (
            _polygon((-1905, 1270), (-635, 1270), (-1270, -1270)),
            _line((-1905, -1270), (-635, -1270)),
            _polygon((635, -1270), (1905, -1270), (1270, 1270)),
            _line((635, 1270), (1905, 1270)),
            *_path(((-1270, 1270), (-1270, 2540), (1270, 2540), (1270, 1270))),
            *_path(((-1270, -1270), (-1270, -2540), (1270, -2540), (1270, -1270))),
            _line((-2540, -2540), (-1270, -1270)),
        )
    return pins, graphics


def _circle(x: int, y: int, radius: int = 170, width: int = 254) -> SymbolGraphic:
    return SymbolGraphic("circle", (_point(x, y), _point(x + radius, y)), width * 1000)


def _resistance() -> tuple[SymbolGraphic, ...]:
    return _path(
        (
            (-2540, 0),
            (-1905, 1050),
            (-1270, -1050),
            (-635, 1050),
            (0, -1050),
            (635, 1050),
            (1270, -1050),
            (1905, 1050),
            (2540, 0),
        )
    )


def _two_pins() -> tuple[SymbolPin, ...]:
    return (_pin("1", "A", -5080, 0, 0), _pin("2", "B", 5080, 0, 180))


def _winding(x: int, direction: int) -> tuple[SymbolGraphic, ...]:
    # Same Fenolite-authored smooth lobe sampling used by the existing inductor.
    heights = (0, 248, 486, 705, 898, 1057, 1174, 1246, 1270, 1246, 1174, 1057, 898, 705, 486, 248, 0)
    return tuple(
        _line(
            (x + direction * heights[step], -2540 + coil * 1270 + step * 1270 // 16),
            (x + direction * heights[step + 1], -2540 + coil * 1270 + (step + 1) * 1270 // 16),
        )
        for coil in range(4)
        for step in range(16)
    )


def _light_arrows(phototransistor: bool = False) -> tuple[SymbolGraphic, ...]:
    arrows = (
        (((-4500, 3200), (-2600, 1800)), ((-4500, 1600), (-2600, 200)))
        if phototransistor
        else (((-1500, 4000), (-500, 2700)), ((500, 4000), (1500, 2700)))
    )
    return tuple(g for tail, tip in arrows for g in (_line(tail, tip), _head(tail, tip)))


def _contacts(spdt: bool) -> tuple[tuple[SymbolPin, ...], tuple[SymbolGraphic, ...]]:
    if not spdt:
        return _two_pins(), (
            _line((-2540, 0), (-2200, 0)),
            _line((2200, 0), (2540, 0)),
            _line((-2200, 0), (1905, 1905)),
            _circle(-2200, 0),
            _circle(2200, 0),
        )
    return (
        _pin("1", "COM", -5080, 0, 0),
        _pin("2", "NC", 5080, 2540, 180),
        _pin("3", "NO", 5080, -2540, 180),
    ), (
        _line((-2540, 0), (-2200, 0)),
        _line((2200, 2540), (2540, 2540)),
        _line((2200, -2540), (2540, -2540)),
        _line((-2200, 0), (2200, 2540)),
        _circle(-2200, 0),
        _circle(2200, 2540),
        _circle(2200, -2540),
    )


def _relay() -> tuple[tuple[SymbolPin, ...], tuple[SymbolGraphic, ...]]:
    pins = (
        _pin("1", "COIL1", -3810, 5080, 270),
        _pin("2", "COIL2", -3810, -5080, 90),
        _pin("3", "COM", -1270, -5080, 90),
        _pin("4", "NC", 5080, 2540, 180),
        _pin("5", "NO", 5080, 0, 180),
    )
    return pins, (
        *_winding(-3810, 1),
        _line((-1270, -2540), (-1270, -1270)),
        _line((2200, 2540), (2540, 2540)),
        _line((2200, 0), (2540, 0)),
        _line((-1270, -1270), (2200, 2540)),
        *(_line((x, 0), (x + 200, 0), 180) for x in (-2400, -1980, -1560, -1140, -720)),
        _circle(-1270, -1270),
        _circle(2200, 2540),
        _circle(2200, 0),
    )


def symbol_graph(name: str) -> tuple[tuple[SymbolPin, ...], tuple[SymbolGraphic, ...]] | None:
    """Return this expansion's geometry, or None for a different catalog family."""
    if name in ("BJT_NPN", "BJT_PNP"):
        return _transistor_pins("B", "C", "E"), _bjt(name == "BJT_PNP")
    if name in ("MOSFET_N_Channel", "MOSFET_P_Channel"):
        return _transistor_pins("G", "D", "S"), _mosfet(name == "MOSFET_P_Channel")
    if name == "IGBT":
        return _transistor_pins("G", "C", "E"), (
            _line((-2540, 0), (-2032, 0)),
            _line((-2032, -1905), (-2032, 1905)),
            _line((-1270, -1905), (-1270, 1905)),
            _line((-1270, 1270), (2540, 2540)),
            _line((-1270, -1270), (2540, -2540)),
            _head((875, -1985), (1775, -2285)),
        )
    if name in ("SCR", "TRIAC"):
        return _thyristor(name == "TRIAC")
    if name == "Schottky_Diode":
        # The pins of the catalog's Diode: on a shorter cathode pin the pin number lies on the hook.
        return (
            _pin("1", "A", -5080, 0, 0, 3810),
            _pin("2", "K", 5080, 0, 180, 3810),
        ), (
            _polygon((-1270, -1700), (1270, 0), (-1270, 1700)),
            *_path(((1905, 1050), (1905, 1700), (1270, 1700), (1270, -1700), (635, -1700), (635, -1050))),
        )
    if name == "TVS_Bidirectional":
        return (
            _pin("1", "A", -5080, 0, 0),
            _pin("2", "B", 5080, 0, 180),
        ), (
            _polygon((-2540, -1270), (0, 0), (-2540, 1270)),
            _polygon((2540, -1270), (0, 0), (2540, 1270)),
            *_path(((-635, 1500), (0, 1500), (0, -1500), (635, -1500))),
        )

    if name in ("Potentiometer", "Thermistor_NTC", "Thermistor_PTC"):
        graphics = _resistance()
        if name == "Potentiometer":
            return (
                _pin("1", "A", -5080, 0, 0),
                _pin("2", "W", 635, 5080, 270),
                _pin("3", "B", 5080, 0, 180),
            ), (*graphics, _line((635, 2540), (635, 1050)), _head((635, 2540), (635, 1050)))
        marks = (
            *_path(((-2540, -1905), (-1905, -1905), (1905, 1905))),
            _line((750, 2500), (1550, 2500)),
            _line((2350, 3000), (3550, 3000)),
            _line((2950, 3000), (2950, 1900)),
        )
        if name == "Thermistor_PTC":
            marks += (_line((1150, 2100), (1150, 2900)),)
        return _two_pins(), (*graphics, *marks)
    if name == "Crystal":
        return (_pin("1", "X1", -5080, 0, 0), _pin("2", "X2", 5080, 0, 180)), (
            _line((-2540, -1905), (-2540, 1905)),
            _line((2540, -1905), (2540, 1905)),
            SymbolGraphic("rect", (_point(-1016, -2540), _point(1016, 2540)), 254_000),
        )
    if name in ("Switch_SPST", "Switch_SPDT"):
        return _contacts(name == "Switch_SPDT")
    if name == "Pushbutton_NO":
        return (
            _pin("1", "A1", -5080, 2540, 0),
            _pin("2", "A2", -5080, -2540, 0),
            _pin("3", "B1", 5080, 2540, 180),
            _pin("4", "B2", 5080, -2540, 180),
        ), (
            _line((-2540, -2540), (-2540, 2540)),
            _line((2540, -2540), (2540, 2540)),
            _line((-2540, 0), (-1905, 0)),
            _line((1905, 0), (2540, 0)),
            _line((-1905, 1270), (1905, 1270)),
            _line((0, 1270), (0, 3500)),
            _line((-1270, 3500), (1270, 3500)),
            _circle(-1905, 0),
            _circle(1905, 0),
        )
    if name == "Relay_SPDT":
        return _relay()
    if name == "Transformer":
        return (
            _pin("1", "P1", -2540, 5080, 270),
            _pin("2", "P2", -2540, -5080, 90),
            _pin("3", "S1", 2540, 5080, 270),
            _pin("4", "S2", 2540, -5080, 90),
        ), (
            *_winding(-2540, 1),
            *_winding(2540, -1),
            _line((-400, -2540), (-400, 2540), 180),
            _line((400, -2540), (400, 2540), 180),
            _circle(-3100, 1905, 160, 320),
            _circle(3100, 1905, 160, 320),
        )
    if name == "Photodiode":
        return (_pin("1", "A", -5080, 0, 0), _pin("2", "K", 5080, 0, 180)), (
            _line((-2540, 0), (-1270, 0)),
            _line((1270, 0), (2540, 0)),
            _polygon((-1270, -1700), (1270, 0), (-1270, 1700)),
            _line((1270, -1905), (1270, 1905)),
            *_light_arrows(),
        )
    if name == "Phototransistor":
        return (_pin("1", "C", 2540, 5080, 270), _pin("2", "E", 2540, -5080, 90)), (
            *_bjt()[1:],
            *_light_arrows(True),
        )
    return None
