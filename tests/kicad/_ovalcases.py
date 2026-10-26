# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Is an equal-sized oval pad the copper of a circle pad? (change c0158; hypothesis ``H-K-EQ-OVAL``;
capability design-equivalence, "Tolerances and normalisation", "Pad shape").

The two-layer board is written twice, every surface-mount pad of one size, ``1.6 x 1.6`` mm, as an
``oval`` in one board and as a ``circle`` in the other. ``kicad-cli pcb export gerbers -l F.Cu`` plots each.
The probe ``equiv-oval-disc`` is ``equal`` when the two plots, without their creation dates, differ only in
the aperture of those pads, an obround ``O,DxD`` against a circle ``C,D`` of the same ``D``, and flash at
the same points. An obround is a rectangle whose shorter sides are half circles (S-0125); with two equal
sizes nothing of the rectangle is left, so it is the disc of that diameter (``docs/formats/kicad/gerber.md``).
"""

from __future__ import annotations

import dataclasses
import re
import tempfile
from collections.abc import Callable
from functools import cache
from pathlib import Path

import _gerber

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Size

ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
SIDE = 1_600_000
SHAPES = ("oval", "circle")
_DATE = re.compile(r"CreationDate|Created by KiCad")
_APERTURE = re.compile(r"^%ADD(\d+)([A-Za-z]+),([0-9.]+)(?:X([0-9.]+))?\*%$")


def board_text(shape: str, target: int) -> str:
    """The two-layer board with every pad without a drill turned into a ``shape`` pad of ``SIDE`` square."""
    design = read_board(BOARD.read_text(encoding="utf-8"), file=BOARD.name)
    board = design.board
    assert board is not None
    footprints = tuple(
        dataclasses.replace(
            footprint,
            pads=tuple(
                dataclasses.replace(pad, shape=shape, size=Size(SIDE, SIDE)) if pad.drill is None else pad
                for pad in footprint.pads
            ),
        )
        for footprint in board.footprints
    )
    changed = dataclasses.replace(design, board=dataclasses.replace(board, footprints=footprints))
    return write_board(changed, target=target).text


@cache
def plots() -> dict[str, str]:
    """The ``F.Cu`` Gerber of each board, on the running ``kicad-cli``."""
    from _probes import runner

    cli = runner()
    found: dict[str, str] = {}
    for shape in SHAPES:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.kicad_pcb"
            path.write_text(board_text(shape, cli.major()), encoding="utf-8")
            project = path.with_suffix(".kicad_pro")
            project.write_text("{}\n", encoding="utf-8")
            run = cli.run(
                ["pcb", "export", "gerbers", "-l", "F.Cu", "-o", "g/", path.name],
                files={path.name: path, project.name: project},
            )
        gerber = next((data for name, data in run.outputs.items() if name.endswith(".gtl")), None)
        assert run.ok and gerber is not None, run.stderr
        found[shape] = gerber.decode("utf-8")
    return found


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if not _DATE.search(line)]


def changed_apertures(oval: str, circle: str) -> list[tuple[str, str]] | None:
    """The pairs of lines that differ between the two plots without their dates; ``None`` when the plots
    differ in the number of lines."""
    one, other = _lines(oval), _lines(circle)
    if len(one) != len(other):
        return None
    return [(a, b) for a, b in zip(one, other, strict=True) if a != b]


def disc_pair(a: str, b: str) -> bool:
    """Whether ``a`` defines an obround of two equal sizes and ``b`` a circle of that diameter, under one
    aperture number."""
    first, second = _APERTURE.match(a), _APERTURE.match(b)
    if first is None or second is None or first.group(1) != second.group(1):
        return False
    return (
        first.group(2) == "O"
        and first.group(3) == first.group(4)
        and second.group(2) == "C"
        and second.group(4) is None
        and second.group(3) == first.group(3)
    )


def oval_disc_outcome() -> str:
    found = plots()
    pairs = changed_apertures(found["oval"], found["circle"])
    if not pairs or not all(disc_pair(a, b) for a, b in pairs):
        return "different"
    if _gerber.flashes(found["oval"]) != _gerber.flashes(found["circle"]):
        return "different"
    return "equal"


def oval_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    return {"equiv-oval-disc": (oval_disc_outcome, (9, 10))}


__all__ = [
    "SIDE",
    "board_text",
    "changed_apertures",
    "disc_pair",
    "oval_disc_outcome",
    "oval_probes",
    "plots",
]
