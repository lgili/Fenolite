# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level 8 for the commands (capability design-equivalence, "Level 8 compares rendered presentation";
change c0278): the viewer's scenes of two sides rendered and compared by ``view.fidelity``, as a
``LevelResult`` of the equivalence package.

``fenolite equivalent --level 8`` and ``fenolite verify-source`` call ``presentation_level``; ``cli`` is the
package that may import both ``view`` and ``checks``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fenolite.api.sides import ReadSide
from fenolite.backends import registry
from fenolite.backends.base import BoardFrame
from fenolite.checks.equivalence import PRESENTATION_LEVEL, LevelResult
from fenolite.checks.equivalence.model import Difference
from fenolite.model.design import Design
from fenolite.view import fidelity, themes
from fenolite.view.kicad_schematic import build_kicad_schematic_scene

BOARD = "board"
"""The name of the board scene of a side."""
FRAMED = ("kicad", "altium")
"""The backends whose board frame draws the pads; a built design is drawn with the first."""


def _frame(backend: str) -> BoardFrame | None:
    name = backend if backend in FRAMED else FRAMED[0]
    found = registry.get(name)
    return found if isinstance(found, BoardFrame) else None


def board_scenes(design: Design, backend: str) -> dict[str, Mapping[str, Any]]:
    """The board scene of a design, zones by outline only, under the name ``board``."""
    if design.board is None:
        return {}
    return {BOARD: fidelity.board_scene(design, _frame(backend), name=BOARD, backend=backend)}


def sheet_scenes(root: Path) -> dict[str, Mapping[str, Any]]:
    """The scene of each KiCad schematic sheet under the folder ``root``, by its path relative to it."""
    palette = themes.palette("kicad")
    found: dict[str, Mapping[str, Any]] = {}
    for path in sorted(root.rglob("*.kicad_sch")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith((".", "lib/")) or "/." in rel:
            continue
        data = path.read_bytes()
        found[f"sheet:{rel}"] = build_kicad_schematic_scene(
            data.decode("utf-8"), name=path.name, data=data, palette=palette
        )
    return found


def to_level(found: fidelity.SceneComparison) -> LevelResult:
    """The level-8 result of a scene comparison."""
    differences = tuple(
        Difference(PRESENTATION_LEVEL, f.kind, f.where, f.field, f.a, f.b) for f in found.findings
    )
    return LevelResult(PRESENTATION_LEVEL, found.compared, differences, (), dict(found.summary))


def presentation_level(
    scenes_a: Mapping[str, Mapping[str, Any]],
    scenes_b: Mapping[str, Mapping[str, Any]],
    *,
    pixel_ppm: int,
    pitch_nm: int,
) -> LevelResult:
    """Level 8 over two sets of scenes, board layers at ``pitch_nm``."""
    return to_level(fidelity.compare_scenes(scenes_a, scenes_b, pixel_ppm=pixel_ppm, board_pitch_nm=pitch_nm))


def side_presentation(pixel_ppm: int, pitch_nm: int) -> Any:
    """The ``presentation`` argument of ``fenolite.api.equivalent``: the boards of the two sides."""

    def run(a: ReadSide, b: ReadSide) -> LevelResult:
        return presentation_level(
            board_scenes(a.design, a.backend), board_scenes(b.design, b.backend), pixel_ppm=pixel_ppm,
            pitch_nm=pitch_nm,
        )  # fmt: skip

    return run


__all__ = ["BOARD", "board_scenes", "presentation_level", "sheet_scenes", "side_presentation", "to_level"]
