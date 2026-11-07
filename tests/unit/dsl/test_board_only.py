# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board-only parts (capability design-dsl, "Board-only parts in the DSL"; change c0277):
``Part(..., board_only=True)`` keeps its ref as written, may share it, has no symbol on the schematic and
marks its footprint with KiCad's ``board_only`` attribute."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.sexpr import parse
from fenolite.dsl import Design, DslError, Part, mm, to_model

STAMP = "2026-10-30T00:00:00Z"
LINES = (
    's1 = Part("STITCH1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", name="stitch_1", board_only=True)\n'
    's2 = Part("STITCH1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", name="stitch_2", board_only=True)\n'
    'logo = Part("REF**", "Mini:Mini_R", footprint="Mini:Mini_R_0603", name="logo", board_only=True)\n'
    "design.add(s1, s2, logo)\n"
    "s1.place(mm(5), mm(5))\n"
    "s2.place(mm(9), mm(5))\n"
    "logo.place(mm(14), mm(5))\n"
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_board_only_parts_in_the_model() -> None:
    design = Design("only")
    design.board(mm(20), mm(20))
    shared = [
        Part("STITCH1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", name=f"s{k}", board_only=True)
        for k in (1, 2)
    ]
    empty = Part("", "Mini:Mini_R", footprint="Mini:Mini_R_0603", name="art", board_only=True)
    design.add(*shared, empty)
    components = sorted(to_model(design).circuit.components, key=lambda c: c.properties["fenolite.path"])
    assert [(c.ref, c.board_only) for c in components] == [("", True), ("STITCH1", True), ("STITCH1", True)]


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"ref": "REF**", "board_only": True}, "needs name="),
        ({"ref": None, "name": "x", "board_only": True}, "give ref"),
        ({"ref": " A", "name": "x", "board_only": True}, "printable text"),
        ({"ref": "REF**", "name": "x"}, "must match"),
        ({"ref": "A1", "board_only": "yes"}, "board_only must be a bool"),
    ],
)
def test_refusals(kwargs: dict[str, object], match: str) -> None:
    ref = kwargs.pop("ref")
    with pytest.raises(DslError, match=match):
        Part(ref, "Mini:Mini_R", footprint="Mini:Mini_R_0603", **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("target", [9, 10])
def test_board_only_parts_built(tmp_path: Path, target: int) -> None:
    script = blink_variant(tmp_path / "src", append=LINES)
    out = tmp_path / "out"
    reply = run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm",
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    board = parse((out / "blink.kicad_pcb").read_text(encoding="utf-8"))
    attrs: list[tuple[str, list[str]]] = []
    for node in board.nodes("footprint"):
        ref = next(p.atoms()[1].value for p in node.nodes("property") if p.atoms()[0].value == "Reference")
        attr = node.find("attr")
        attrs.append((ref, [a.value for a in attr.atoms()] if attr is not None else []))
    shown = sorted(a for a in attrs if a[0] in ("STITCH1", "REF**"))
    assert shown == [("REF**", ["smd", "board_only"])] + [("STITCH1", ["smd", "board_only"])] * 2
    assert all("board_only" not in values for ref, values in attrs if ref in ("R1", "D1", "U1"))
    sheet = (out / "blink.kicad_sch").read_text(encoding="utf-8")
    assert "STITCH1" not in sheet and "REF**" not in sheet
    lock = script.parent / "design.lock"
    assert not lock.exists() or "stitch" not in lock.read_text(encoding="utf-8")
