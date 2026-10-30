# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board texts of change c0277 (capability design-dsl, "Board drawings in the DSL"): copper layers,
``knockout``, a size of two values, several lines, an empty text, ``bold``, ``italic`` and ``face``, in the
model and written for KiCad 9 and 10."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.core.coords import Size
from fenolite.dsl import Design, DslError, mm, to_model

STAMP = "2026-10-30T00:00:00Z"


def _design() -> Design:
    design = Design("texts")
    design.board(mm(50), mm(30))
    return design


def test_texts_in_the_model() -> None:
    d = _design()
    d.text("cu/rev", "REV B", (mm(5), mm(5)), layer="F.Cu", knockout=True)
    d.text("silk/wide", "WIDE", (mm(5), mm(10)), size=(mm(2), mm("1.25")), bold=True)
    d.text("silk/lines", "A\nB", (mm(5), mm(15)), italic=True, face="KiCad Font")
    d.text("user/empty", "", (mm(5), mm(20)), layer="Dwgs.User")
    texts = {t.text: t for t in to_model(d).board.texts}  # type: ignore[union-attr]
    rev = texts["REV B"]
    assert (rev.layer, rev.knockout, rev.size) == ("F.Cu", True, Size(1_000_000, 1_000_000))
    wide = texts["WIDE"]
    assert (wide.size, wide.bold, wide.italic, wide.face) == (Size(2_000_000, 1_250_000), True, False, "")
    lines = texts["A\nB"]
    assert (lines.italic, lines.face, lines.knockout) == (True, "KiCad Font", False)
    assert texts[""].layer == "Dwgs.User"


def test_a_text_without_the_new_arguments_keeps_its_model() -> None:
    d = _design()
    d.text("rev", "REV A", (mm(2), mm(2)), size=(mm(1), mm(1)))
    (text,) = to_model(d).board.texts  # type: ignore[union-attr]
    assert (text.size, text.knockout, text.bold, text.italic, text.face) == (
        Size(1_000_000, 1_000_000), False, False, False, "",
    )  # fmt: skip


@pytest.mark.parametrize(
    ("arguments", "word"),
    [
        ({"layer": "In1.Cu"}, "In1.Cu"),
        ({"layer": "F.Fab", "knockout": True}, "knockout"),
        ({"knockout": "yes"}, "knockout"),
        ({"bold": 1}, "bold"),
        ({"italic": None}, "italic"),
        ({"face": ""}, "face"),
        ({"face": 3}, "face"),
        ({"size": (mm(1),)}, "size"),
        ({"size": (mm(1), mm(0))}, "height"),
    ],
)
def test_refused_text_arguments(arguments: dict[str, object], word: str) -> None:
    d = _design()
    with pytest.raises(DslError, match=word):
        d.text("t", "A", (mm(1), mm(1)), **arguments)  # type: ignore[arg-type]
    assert not d.drawings


@pytest.mark.parametrize("value", ["A\tB", "A\nB\x00", 3])
def test_refused_text_values(value: object) -> None:
    d = _design()
    with pytest.raises(DslError, match="text"):
        d.text("t", value, (mm(1), mm(1)))  # type: ignore[arg-type]


LINES = (
    'design.text("cu/rev", "REV B", (mm(5), mm(5)), layer="F.Cu", knockout=True)\n'
    'design.text("silk/style", "STYLE", (mm(5), mm(10)), size=(mm(2), mm("1.25")), bold=True, italic=True,'
    ' face="KiCad Font")\n'
    'design.text("silk/lines", "A\\nB", (mm(5), mm(15)), layer="B.SilkS")\n'
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _texts(text: str) -> dict[str, Node]:
    return {node.atoms()[0].value: node for node in parse(text).nodes("gr_text")}


@pytest.mark.parametrize("target", [9, 10])
def test_texts_written(tmp_path: Path, target: int) -> None:
    script = blink_variant(tmp_path / "src", append=LINES)
    out = tmp_path / "out"
    reply = run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm",
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    texts = _texts((out / "blink.kicad_pcb").read_text(encoding="utf-8"))
    assert dumps(texts["REV B"].find("layer"), style="compact") == '(layer "F.Cu" knockout)'  # type: ignore[arg-type]
    font = texts["STYLE"].find("effects").find("font")  # type: ignore[union-attr]
    assert dumps(font, style="compact") == (  # type: ignore[arg-type]
        '(font (face "KiCad Font") (size 1.25 2) (thickness 0.15) (bold yes) (italic yes))'
    )
    lines = texts["A\nB"]
    assert "mirror" in dumps(lines.find("effects"), style="compact")  # type: ignore[arg-type]
    codes = [issue["code"] for issue in reply.envelope["issues"]]  # type: ignore[index]
    assert codes.count("copper.text-unchecked") == 1


def test_altium_reports_the_new_styles(tmp_path: Path) -> None:
    """An Altium build reports a text whose style its text record does not hold, and writes no record."""
    script = blink_variant(tmp_path / "src", append=LINES)
    reply = run(
        "build", str(script), "--out", str(tmp_path / "out"), "--target", "altium", "--dry-run",
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    messages = [issue["message"] for issue in reply.envelope["issues"]]  # type: ignore[index]
    assert any("STYLE" in m and "knockout" not in m and "bold, italic" in m for m in messages), messages
    assert any("REV B" in m for m in messages)


def test_dimension_size_pair_and_extension_offset() -> None:
    d = _design()
    d.dimension("w", (mm(0), mm(0)), (mm(50), mm(0)), offset=mm(-5), size=(mm("1.524"), mm("2.032")),
                extension_offset=mm(0))  # fmt: skip
    d.dimension("h", (mm(0), mm(0)), (mm(0), mm(30)), offset=mm(4), size=mm(1))
    dims = {dim.id: dim for dim in to_model(d).board.dimensions}  # type: ignore[union-attr]
    wide, tall = sorted(dims.values(), key=lambda dim: dim.end.x, reverse=True)
    assert (wide.offset, wide.size, wide.extension_offset) == (-5_000_000, Size(1_524_000, 2_032_000), 0)
    assert (tall.offset, tall.size, tall.extension_offset) == (4_000_000, Size(1_000_000, 1_000_000), None)
    with pytest.raises(DslError, match="extension_offset"):
        d.dimension("bad", (mm(0), mm(0)), (mm(5), mm(0)), offset=mm(1), extension_offset=mm(-1))
