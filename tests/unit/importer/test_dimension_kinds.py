# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Radial dimensions, leaders and centre marks through ``fenolite import --to python`` (capability
board-to-code; change c0277): the reader models them, the import writes the ones whose format and style
the build writes, and the build writes them again."""

from __future__ import annotations

from pathlib import Path

from _importcode import build, dimensioned, imported

from fenolite.backends.kicad.pcb import read_board


def test_kinds_are_written(tmp_path: Path) -> None:
    reply = imported(tmp_path, dimensioned(tmp_path / "src"), "--allow-lossy", "--confirm")
    assert reply.exit_code == 0, reply.error
    unexpressed = {u["kind"]: u["count"] for u in reply.result["unexpressed"]}
    assert unexpressed == {"dimension-style": 1}  # the radial dimension with "4x R "
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    flat = " ".join(code.split())
    assert 'design.radial_dimension( "Dwgs.User/dimension/1"' in flat and 'leader_length=mm("2.5")' in flat
    assert 'design.leader( "Cmts.User/dimension/1"' in flat and 'text="0.3mm Thickness"' in flat
    assert 'text_at=(mm("25.7"), mm("47"))' in flat  # placed by hand, not 2 mm past the knee
    assert 'design.center_mark("Dwgs.User/dimension/2"' in flat
    assert build(tmp_path / "out").exit_code == 0
    back = read_board(tmp_path / "out" / "built" / "dimensioned.kicad_pcb")
    assert back.board is not None
    found = sorted((d.kind, d.leader_length, d.text, d.frame) for d in back.board.dimensions)
    assert found == [
        ("center", None, None, None),
        ("leader", None, "0.3mm Thickness", "none"),
        ("radial", 2_500_000, None, None),
    ]
