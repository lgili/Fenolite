# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A board outline closed by a footprint's ``Edge.Cuts`` through ``fenolite import --to python``
(capability board-to-code, "Outlines closed by a footprint in an import"; change c0277): the code declares
the closed outline, and the build leaves out the edge the footprint draws."""

from __future__ import annotations

from pathlib import Path

from _importcode import build, imported, notched

from fenolite.backends.kicad.sexpr import parse


def test_outline_closed_by_a_footprint(tmp_path: Path) -> None:
    reply = imported(tmp_path, notched(tmp_path / "src"), "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert 'design.board(mm("60"), mm("40"))' in code
    assert build(tmp_path / "out").exit_code == 0
    root = parse((tmp_path / "out" / "built" / "notched.kicad_pcb").read_text(encoding="utf-8"))
    edges = [n for n in root.nodes("gr_line") if n.find("layer") == parse('(layer "Edge.Cuts")')]
    assert len(edges) == 3
    starts = {tuple(a.value for a in n.find("start").atoms()) for n in edges}  # type: ignore[union-attr]
    assert ("100", "140") not in starts and ("100", "100") in starts
