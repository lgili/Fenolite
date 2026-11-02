# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Verbatim items and placement areas through ``fenolite import --to python`` (change c0277): a ``generated``
tuning pattern is a ``design.verbatim()`` whose members follow its track into the copper table, its group
holds it by key, and a placement rule area keeps its sheet."""

from __future__ import annotations

from pathlib import Path

from _importcode import build, imported, tuned

from fenolite.backends.kicad.sexpr import parse


def _uuid(node) -> str:  # noqa: ANN001
    return node.find("uuid").atoms()[0].value


def test_generated_item_and_placement_area(tmp_path: Path) -> None:
    reply = imported(tmp_path, tuned(tmp_path / "src"), "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert 'design.verbatim(\n    "generated/1",' in code or 'design.verbatim("generated/1",' in code
    assert 'design.group("tuned", "generated/1")' in code
    assert 'placement="/CH1/"' in code and '"auto-placement-area-/CH1/"' in code
    assert build(tmp_path / "out").exit_code == 0
    root = parse((tmp_path / "out" / "built" / "tuned.kicad_pcb").read_text(encoding="utf-8"))
    (generated,) = root.nodes("generated")
    members = generated.find("members")
    assert members is not None
    tracks = {_uuid(t) for t in root.nodes("segment")}
    assert [a.value for a in members.atoms()][0] in tracks
    (group,) = [g for g in root.nodes("group") if g.atoms()[0].value == "tuned"]
    assert [a.value for a in group.find("members").atoms()] == [_uuid(generated)]  # type: ignore[union-attr]
    (area,) = [z for z in root.nodes("zone") if z.find("placement") is not None]
    assert area.find("placement").find("sheetname") == parse('(sheetname "/CH1/")')  # type: ignore[union-attr]
