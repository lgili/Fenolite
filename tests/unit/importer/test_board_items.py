# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board items of change c0277 through ``fenolite import --to python``: user layers and a text on one, a
copper graphic of a net, a filled polygon without an outline, a dimension in automatic units, a free via and
a smoothed zone, each written by a DSL call and built again."""

from __future__ import annotations

from pathlib import Path

from _importcode import build, imported, itemized

from fenolite.backends.kicad.sexpr import dumps, parse


def test_board_items_are_written(tmp_path: Path) -> None:
    reply = imported(tmp_path, itemized(tmp_path / "src"), "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    for said in (
        'design.user_layers(2, names={"User.2": "notes"})',
        'layer="F.Cu",',
        "net=gnd",
        "width=None",
        'layer="User.2"',
        'units="auto"',
        'text_at=(mm("12"), mm("56"))',
        'smoothing="fillet"',
        'smoothing_radius=mm("0.5")',
    ):
        assert said in code, said
    assert "free=True" in (tmp_path / "out" / "copper.py").read_text(encoding="utf-8")
    assert build(tmp_path / "out").exit_code == 0
    root = parse((tmp_path / "out" / "built" / "itemized.kicad_pcb").read_text(encoding="utf-8"))
    (rect,) = [node for node in root.nodes("gr_rect") if node.find("layer") == parse('(layer "F.Cu")')]
    assert rect.find("net") == parse('(net "GND")')
    (poly,) = root.nodes("gr_poly")
    assert dumps(poly.find("stroke"), style="compact") == "(stroke (width -0.000001) (type solid))"  # type: ignore[arg-type]
    (dimension,) = root.nodes("dimension")
    assert dimension.find("format").find("units") == parse("(units 3)")  # type: ignore[union-attr]
    free = [via for via in root.nodes("via") if via.find("free") is not None]
    assert len(free) == 1 and free[0].find("at") == parse("(at 110 133)")
    rows = [dumps(row, style="compact") for row in root.find("layers").nodes()]  # type: ignore[union-attr]
    assert rows[-2:] == ['(39 "User.1" user)', '(41 "User.2" user "notes")']
