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
from fenolite.model.board import Outline
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


__all__ = ["DEFAULTS", "OUTLINE", "Bench", "bench", "two_pads"]
