# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The QFN and BGA benches of the feasibility gate of change c0110 (design, Context, "QFN bench" and "BGA
bench"; measurements 5 and 6). Authored for Fenolite with round values; the parts are those of
``_gateparts``.

- **QFN**: 50 mm by 40 mm, four copper layers; a QFN-48 of 0.5 mm pitch (``U1``) whose exposed pad is on
  ``GND``, and a header of 2 by 20 positions at 1.27 mm (``J1``); 40 signal nets ``Q01`` to ``Q40`` leave
  ``U1`` on all four sides; pins 6, 18, 30 and 42 are ``GND``, 7, 19, 31 and 43 ``VCC``. The class ``SIG``
  has 0.15 mm width and clearance and a 0.5/0.25 mm via.
- **BGA**: 60 mm by 50 mm, four copper layers; a BGA of 11 by 11 balls at 0.8 mm (``U1``, 0.35 mm balls)
  between two headers of 2 by 25 positions (``J1``, ``J2``); the 96 balls of the three outer rings are the
  signals ``B01`` to ``B96``, the inner 25 alternate ``GND`` and ``VCC``. The class ``SIG`` has 0.1 mm width
  and clearance and a 0.4/0.2 mm via, and a board-wide ``hole_clearance`` rule of 0.15 mm holds (Context,
  measurement 6).

``GND`` is a zone on ``In1.Cu`` and ``VCC`` one on ``In2.Cu``. With ``planes=True`` (the default) the two
inner layers are planes (c0107), and the gate joins the SMD pads of ``GND`` and ``VCC`` to them with c0107's
fan-out before it routes the signals; with ``planes=False`` every layer is a signal layer (the narrow-wire
probe of measurement 5).
"""

from __future__ import annotations

from _gateparts import bga121, bga_names, bga_ring, header, qfn48, symbol_for

from fenolite.dsl import Design, Net, Part, connect, mm, nm

QFN_GND = (6, 18, 30, 42)
QFN_VCC = (7, 19, 31, 43)
QFN_SIGNALS = tuple(f"Q{n:02d}" for n in range(1, 41))
BGA_SIGNALS = tuple(f"B{n:02d}" for n in range(1, 97))
SIZES = {
    "qfn": {"width": 150_000, "clearance": 150_000, "via": (500_000, 250_000)},
    "bga": {"width": 100_000, "clearance": 100_000, "via": (400_000, 200_000)},
}
LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
PLANE_LAYERS = ("In1.Cu", "In2.Cu")


def signals(kind: str) -> tuple[str, ...]:
    return QFN_SIGNALS if kind == "qfn" else BGA_SIGNALS


def _board(design: Design, width: int, height: int, gnd: Net, vcc: Net, planes: bool) -> None:
    if planes:
        design.board(mm(width), mm(height), copper=4, planes={"In1.Cu": gnd, "In2.Cu": vcc})
    else:
        design.board(mm(width), mm(height), copper=4)
    design.zone(gnd, layers=("In1.Cu",))
    design.zone(vcc, layers=("In2.Cu",))


def _classes(design: Design, kind: str, nets: dict[str, Net], gnd: Net, vcc: Net) -> None:
    size = SIZES[kind]
    width, clearance = nm(size["width"]), nm(size["clearance"])  # type: ignore[arg-type]
    diameter, drill = (nm(value) for value in size["via"])  # type: ignore[union-attr]
    design.rules.netclass(
        "SIG", clearance=clearance, track_width=width, via_diameter=diameter, via_drill=drill,
        nets=tuple(nets[name] for name in signals(kind)),
    )  # fmt: skip
    design.rules.netclass(
        "PWR", clearance=clearance, track_width=width, via_diameter=diameter, via_drill=drill, nets=(gnd, vcc)
    )
    design.rules.minimum(clearance=clearance, track_width=width, via_diameter=diameter, via_drill=drill)


def qfn_design(planes: bool = True) -> Design:
    """The QFN bench as a design script gives it."""
    design = Design("qfnbench")
    gnd, vcc = Net("GND"), Net("VCC")
    _board(design, 50, 40, gnd, vcc, planes)
    part, connector = qfn48(), header(2, 20)
    design.add_footprint(part)
    design.add_footprint(connector)
    u_symbol = symbol_for(part, [str(n) for n in range(1, 50)], "U")
    j_symbol = symbol_for(connector, [str(n) for n in range(1, 41)], "J")
    u1 = Part("U1", u_symbol.lib_id, footprint=part.lib_id, value="QFN48")
    j1 = Part("J1", j_symbol.lib_id, footprint=connector.lib_id, value="HDR40")
    design.add(u_symbol, j_symbol, u1, j1)
    nets = {name: Net(name) for name in QFN_SIGNALS}
    pins = [n for n in range(1, 49) if n not in QFN_GND and n not in QFN_VCC]
    for index, (pin, name) in enumerate(zip(pins, QFN_SIGNALS, strict=True), start=1):
        connect(nets[name], u1[pin], j1[index])
    connect(gnd, *(u1[pin] for pin in (*QFN_GND, 49)))
    connect(vcc, *(u1[pin] for pin in QFN_VCC))
    _classes(design, "qfn", nets, gnd, vcc)
    u1.place(mm(18), mm(20))
    j1.place(mm(40), mm(20))
    return design


def bga_design(planes: bool = True) -> Design:
    """The BGA bench as a design script gives it."""
    design = Design("bgabench")
    gnd, vcc = Net("GND"), Net("VCC")
    _board(design, 60, 50, gnd, vcc, planes)
    part, connector = bga121(), header(2, 25)
    design.add_footprint(part)
    design.add_footprint(connector)
    balls = bga_names()
    u_symbol = symbol_for(part, balls, "U")
    j_symbol = symbol_for(connector, [str(n) for n in range(1, 51)], "J")
    u1 = Part("U1", u_symbol.lib_id, footprint=part.lib_id, value="BGA121")
    j1 = Part("J1", j_symbol.lib_id, footprint=connector.lib_id, value="HDR50")
    j2 = Part("J2", j_symbol.lib_id, footprint=connector.lib_id, value="HDR50")
    design.add(u_symbol, j_symbol, u1, j1, j2)
    nets = {name: Net(name) for name in BGA_SIGNALS}
    outer = [ball for ball in balls if bga_ring(ball) < 3]
    inner = [ball for ball in balls if bga_ring(ball) >= 3]
    for index, (ball, name) in enumerate(zip(outer, BGA_SIGNALS, strict=True)):
        connector_part, pin = (j1, index + 1) if index < 48 else (j2, index - 47)
        connect(nets[name], u1[ball], connector_part[pin])
    for ball in inner:
        row, column = "ABCDEFGHJKL".index(ball[0]), int(ball[1:])
        connect(gnd if (row + column) % 2 == 0 else vcc, u1[ball])
    _classes(design, "bga", nets, gnd, vcc)
    design.rules.rule("hole-clearance", "hole_clearance", min=mm(0.15))
    u1.place(mm(30), mm(25))
    j1.place(mm(8), mm(25))
    j2.place(mm(52), mm(25))
    return design


def bench_design(kind: str, planes: bool = True) -> Design:
    """The bench ``kind`` (``qfn`` or ``bga``)."""
    return qfn_design(planes) if kind == "qfn" else bga_design(planes)


__all__ = [
    "BGA_SIGNALS",
    "LAYERS",
    "PLANE_LAYERS",
    "QFN_SIGNALS",
    "SIZES",
    "bench_design",
    "bga_design",
    "qfn_design",
    "signals",
]
