# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Small boards for the Specctra codec tests (change c0023), built through the model API: a two-pad board
with one net between two resistors, its board-frame pads, its outline and the board defaults."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from _placed import Part, design_of, mm, pt

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.specctra.dsn import DsnDefaults, DsnResult, write_dsn
from fenolite.core.coords import Point
from fenolite.model.board import Outline, Track
from fenolite.model.circuit import NetClass
from fenolite.model.design import Design

DEFAULTS = DsnDefaults(width=mm(0.25), clearance=mm(0.2), via_diameter=mm(0.6), via_drill=mm(0.3))
OUTLINE = (pt(0, 0), pt(30, 0), pt(30, 20), pt(0, 20))


@dataclass(frozen=True)
class Bench:
    """A design with what ``write_dsn`` needs beside it."""

    design: Design
    pads: tuple[BoardPad, ...]
    outline: tuple[tuple[Point, ...], ...]
    selected: tuple[str, ...]

    def write(self, **changes: object) -> DsnResult:
        fields = {
            "pads": self.pads,
            "outline": self.outline,
            "selected": self.selected,
            "defaults": DEFAULTS,
            **changes,
        }
        return write_dsn(self.design, **fields)  # type: ignore[arg-type]


def bench(
    design: Design, *, selected: tuple[str, ...] = ("A",), cutouts: tuple[tuple[Point, ...], ...] = ()
) -> Bench:
    """``design`` with the rectangular outline of the benches, its pads and the nets to route."""
    assert design.board is not None
    board = dataclasses.replace(
        design.board,
        outline=Outline(id="out_00000000-0000-4000-8000-000000000001", points=OUTLINE, cutouts=cutouts),
    )
    design = dataclasses.replace(design, board=board)
    return Bench(design, board_pads(design), (OUTLINE, *cutouts), selected)


def two_pads() -> Bench:
    """Two 0603 resistors 10 mm apart; pad 2 of R1 and pad 1 of R2 share the net ``A``."""
    return bench(
        design_of(
            Part("R1", "Mini_R_0603", 10, 10, nets={"2": "A"}),
            Part("R2", "Mini_R_0603", 20, 10, nets={"1": "A"}),
        )
    )


WIDE_CLEARANCE = 2 * DEFAULTS.clearance
"""The clearance of the class ``WIDE`` of ``netless_bench``: twice the default rule."""
NETLESS_GAP = mm(0.3)
"""Between a straight route of ``A`` or ``C`` and the pads of ``B`` on ``netless_bench``: more than the
default rule (0.2 mm) and less than the clearance of ``WIDE`` (0.4 mm)."""


def netless_bench(*, joined: bool = True, target: int = 10) -> Bench:
    """The bench of ``H-G-DSN-NETLESS`` (change c0109): a net outside the job between two routed nets.

    ``B`` joins two pads on the row y = 10 mm and is in the class ``WIDE``, whose clearance is twice the
    default rule; with ``joined`` it is already routed by one track. ``A`` and ``C`` are the job: two pads
    each, 0.905 mm above and below that row, so the straight route of either passes ``NETLESS_GAP`` from
    the pads of ``B``. That is legal for a router that knows only the default rule and too near for KiCad,
    which takes the larger clearance of the two classes; a route that bends 0.1 mm away is legal for both.
    ``target`` is the KiCad major its board is written for (the footprint files of that major).
    """
    wide = NetClass(
        id="cls_00000000-0000-4000-8000-000000000109",
        name="WIDE",
        clearance=WIDE_CLEARANCE,
        track_width=DEFAULTS.width,
    )
    default = NetClass(
        id="cls_00000000-0000-4000-8000-000000000108",
        name="Default",
        clearance=DEFAULTS.clearance,
        track_width=DEFAULTS.width,
        via_diameter=DEFAULTS.via_diameter,
        via_drill=DEFAULTS.via_drill,
    )
    design = design_of(
        Part("RA1", "Mini_R_0603", 10, 9.095, nets={"2": "A"}),
        Part("RA2", "Mini_R_0603", 20, 9.095, nets={"1": "A"}),
        Part("RB1", "Mini_R_0603", 13.2, 10, nets={"2": "B"}),
        Part("RB2", "Mini_R_0603", 16.8, 10, nets={"1": "B"}),
        Part("RC1", "Mini_R_0603", 10, 10.905, nets={"2": "C"}),
        Part("RC2", "Mini_R_0603", 20, 10.905, nets={"1": "C"}),
        classes=(default, wide),
        class_of={"B": "WIDE"},
        target=target,
    )
    assert design.board is not None
    if joined:
        track = Track(
            id="trk_00000000-0000-4000-8000-000000000109",
            start=pt(14, 10),
            end=pt(16, 10),
            width=DEFAULTS.width,
            layer="F.Cu",
            net_id=design.nets_by_name["B"].id,
        )
        design = dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=(track,)))
    return bench(design, selected=("A", "C"))


__all__ = [
    "DEFAULTS",
    "NETLESS_GAP",
    "OUTLINE",
    "WIDE_CLEARANCE",
    "Bench",
    "bench",
    "netless_bench",
    "two_pads",
]
