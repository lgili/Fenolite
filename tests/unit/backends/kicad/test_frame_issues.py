# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed set of board-frame issue codes and the module's evidence (capability board-frame: "Board-frame
issue codes", "Board-frame evidence"; change c0028)."""

from __future__ import annotations

import ast
from pathlib import Path

from _placed import Part, design_of

from fenolite.backends.kicad import frame
from fenolite.backends.kicad.frame import FRAME_ISSUE_CODES, board_pads, placed_extents
from fenolite.core.errors import Issue
from fenolite.core.evidence import Level

TABLE = {
    "kicad.frame.courtyard-malformed": "warning",
    "kicad.frame.no-courtyard": "info",
    "kicad.frame.shape-approximated": "info",
}


def test_closed_set() -> None:
    """Every code a frame query produces is a key of the table with its severity, every key is produced,
    and the module writes no other ``kicad.frame.*`` literal."""
    assert dict(FRAME_ISSUE_CODES) == TABLE
    design = design_of(
        Part("T1", "Frame_Trapezoid", 0, 0, library="Frame"),
        Part("P1", "Frame_NoCourtyard", 10, 0, library="Frame"),
        Part("P2", "Frame_OpenCourtyard", 20, 0, library="Frame"),
    )
    found: list[Issue] = []
    board_pads(design, issues=found)
    placed_extents(design, issues=found)
    assert {(i.code, i.severity) for i in found} == set(TABLE.items())
    tree = ast.parse(Path(frame.__file__).read_text(encoding="utf-8"))
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("kicad.frame.")
    }
    assert literals == set(TABLE)


def test_evidence_constant() -> None:
    assert frame.EVIDENCE.level is Level.INFERRED
    assert frame.EVIDENCE.hypotheses == (
        "H-G-ROT-DIR",
        "H-G-BOTTOM-PLACE",
        "H-G-PAD-ANGLE-ABS",
        "H-G-FRAME-SHAPE",
        "H-G-FRAME-CRTYD-2",
    )
