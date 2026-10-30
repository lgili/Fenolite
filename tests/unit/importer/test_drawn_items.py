# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board texts and dimensions through ``fenolite import --to python`` (change c0277): knockout, bold,
italic, face, sizes of two values, several lines, an empty text and a copper text become ``design.text()``
calls, an aligned dimension with its extension offset a ``design.dimension()`` call, and what the DSL cannot
say (a hidden text, automatic units) is reported."""

from __future__ import annotations

from pathlib import Path

from _importcode import build, drawn, imported

from fenolite.backends.kicad.sexpr import dumps, parse


def test_texts_and_dimensions_are_written(tmp_path: Path) -> None:
    reply = imported(tmp_path, drawn(tmp_path / "src"), "--allow-lossy", "--confirm")
    assert reply.exit_code == 0, reply.error
    kinds = {row["kind"]: row["count"] for row in reply.result["unexpressed"]}
    assert kinds == {"dimension-style": 1, "text": 1}
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    for call in (
        'design.text(\n    "F.SilkS/text/1",\n    "KNOCK",',
        'size=(mm("1.25"), mm("2"))',
        "knockout=True",
        "bold=True",
        '"TWO\\nLINES"',
        '"Dwgs.User/text/1",\n    "",\n',
        'layer="F.Cu"',
        'face="KiCad Font"',
        "italic=True",
        'extension_offset=mm("0")',
    ):
        assert call in code, call
    assert build(tmp_path / "out").exit_code == 0
    root = parse((tmp_path / "out" / "built" / "drawn.kicad_pcb").read_text(encoding="utf-8"))
    texts = {node.atoms()[0].value: node for node in root.nodes("gr_text")}
    assert dumps(texts["KNOCK"].find("layer"), style="compact") == '(layer "F.SilkS" knockout)'  # type: ignore[arg-type]
    font = texts["KNOCK"].find("effects").find("font")  # type: ignore[union-attr]
    assert dumps(font, style="compact") == "(font (size 2 1.25) (thickness 0.275) (bold yes))"  # type: ignore[arg-type]
    assert {"TWO\nLINES", "", "CU", "FACE"} <= set(texts) and "HIDDEN" not in texts
    (dimension,) = root.nodes("dimension")
    style = dimension.find("style")
    assert style is not None and style.find("extension_offset") == parse("(extension_offset 0)")
    assert dimension.find("height") == parse("(height -3)")
