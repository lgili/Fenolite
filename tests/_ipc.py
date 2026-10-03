# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored IPC-D-356 exports for hermetic tests (change c0020): records made from a board's pads in the
fixed columns of ``docs/formats/kicad/board.md``, with an arbitrary export origin."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.kicad.ipcd356 import Ipcd356, Ipcd356Record
from fenolite.backends.kicad.pcb import read_board
from fenolite.geometry import Transform
from fenolite.model.circuit import Component
from fenolite.model.design import Design

UNIT_NM = 2540
ORIGIN = (1234, -567)
"""An export origin in export units, unknown to the matcher."""


def records(design: Design, *, origin: tuple[int, int] = ORIGIN) -> list[Ipcd356Record]:
    """One ``327`` record per pad of ``design``'s board, as ``pcb export ipcd356`` would write it."""
    assert design.board is not None
    nets = {n.id: n.name for n in design.circuit.nets}
    found: list[Ipcd356Record] = []
    for fp in design.board.footprints:
        component = design.by_id[fp.component_id]
        assert isinstance(component, Component)
        placement = Transform.placement(fp.position, fp.rotation)
        for pad in fp.pads:
            at = placement.apply(pad.position)
            net = nets.get(pad.net_id or "", "N/C")
            found.append(
                Ipcd356Record(
                    code="327",
                    net=net[-14:],
                    ref=component.ref[:6],
                    pin=pad.number[:4],
                    x=round(at.x / UNIT_NM) + origin[0],
                    y=round(-at.y / UNIT_NM) + origin[1],
                    rotation=0,
                    side="top",
                )
            )
    return found


def via(x: int = 0, y: int = 0) -> Ipcd356Record:
    return Ipcd356Record(code="317", net="GND", ref="VIA", pin="", x=x, y=y, rotation=None, side="both")


def export(design: Design, *extra: Ipcd356Record) -> Ipcd356:
    return Ipcd356(UNIT_NM, (*records(design), *extra))


def text(found: list[Ipcd356Record] | tuple[Ipcd356Record, ...]) -> str:
    """The records as IPC-D-356 lines: code, net (14), 3 blanks, reference (6), ``-``, pin (4), the
    midpoint column, then ``A01X±nnnnnnY±nnnnnnR000``."""
    lines = ["C  IPC-D-356 authored for Fenolite tests", "P  UNITS CUST 0"]
    for r in found:
        flag = "M" if r.ref == "VIA" else " "
        access = "00" if r.code == "317" else "01"
        lines.append(
            f"{r.code}{r.net[-14:]:<14}   {r.ref:<6}-{r.pin:<4}{flag}A{access}X{r.x:+07d}Y{r.y:+07d}R000"
        )
    lines.append("999")
    return "\n".join(lines) + "\n"


def for_board(board: Path) -> str:
    """The export text a ``kicad-cli`` would write for the board file at ``board``."""
    return text(records(read_board(board.read_text(encoding="utf-8"), file=board.name)))


__all__ = ["ORIGIN", "UNIT_NM", "export", "for_board", "records", "text", "via"]
