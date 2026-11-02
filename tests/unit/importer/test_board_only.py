# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprints that share a reference, or have one a script cannot name, through ``fenolite import --to
python`` (capability board-to-code, "Board-only parts in an import"; change c0277): each is a board-only part
named by key, reported once as ``import.board-only``, and the self-check pairs them by placement."""

from __future__ import annotations

from pathlib import Path

from _importcode import build, imported, shared

from fenolite.backends.kicad.sexpr import parse


def test_shared_references_are_board_only_parts(tmp_path: Path) -> None:
    reply = imported(tmp_path, shared(tmp_path / "src"), "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    (found,) = [i for i in (reply.envelope or {})["issues"] if i["code"] == "import.board-only"]
    assert (
        found["severity"] == "info"
        and "3 footprint(s)" in found["message"]
        and "3 of them gain" in found["message"]
    )
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert code.count("board_only=True") == 3
    at = code.index('"REF**"')
    assert "name=" in code[at : code.index(")", at)]
    assert "REF**" not in (tmp_path / "out" / "design.lock").read_text(encoding="utf-8")
    assert build(tmp_path / "out").exit_code == 0
    root = parse((tmp_path / "out" / "built" / "shared.kicad_pcb").read_text(encoding="utf-8"))
    refs: list[str] = []
    for node in root.nodes("footprint"):
        ref = next(p.atoms()[1].value for p in node.nodes("property") if p.atoms()[0].value == "Reference")
        attr = node.find("attr")
        if ref in ("R101", "REF**"):
            assert attr is not None and "board_only" in [a.value for a in attr.atoms()]
        refs.append(ref)
    assert sorted(r for r in refs if r in ("R101", "REF**")) == ["R101", "R101", "REF**"]
