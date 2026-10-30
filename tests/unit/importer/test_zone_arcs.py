# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A zone outline with an arc through ``fenolite import --to python`` (capability board-to-code, "Zone arcs in
an import"; change c0277): the reader keeps the outline in the zone's slots, the import writes it with
``arc_to`` and the build writes the arc again."""

from __future__ import annotations

from pathlib import Path

from _importcode import build, imported, rounded

from fenolite.backends.kicad.sexpr import dumps, parse


def test_zone_arc_is_written(tmp_path: Path) -> None:
    reply = imported(tmp_path, rounded(tmp_path / "src"), "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert 'arc_to((mm("57"), mm("20")), (mm("55"), mm("28")))' in code
    assert build(tmp_path / "out").exit_code == 0
    root = parse((tmp_path / "out" / "built" / "rounded.kicad_pcb").read_text(encoding="utf-8"))
    (zone,) = [z for z in root.nodes("zone") if z.find("keepout") is None]
    pts = zone.find("polygon").find("pts")  # type: ignore[union-attr]
    assert "(arc (start 155 112) (mid 157 120) (end 155 128))" in dumps(pts, style="compact")  # type: ignore[arg-type]
