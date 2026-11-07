# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Radial dimensions, leaders and centre marks (capability design-dsl, "More dimension kinds in the DSL";
change c0277): the model, the refused values, and the KiCad build in the forms of the demo boards."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, DslError, mm, to_model

STAMP = "2026-10-30T00:00:00Z"
LINES = """
design.radial_dimension("hole/r", (mm(10), mm(10)), (mm(12), mm(12)), leader_length=mm(3))
design.leader("note", (mm(20), mm(10)), (mm(23), mm(7)), text="NOTE", frame="rect")
design.center_mark("hole/c", (mm(30), mm(10)), (mm(32), mm(10)))
"""


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def fresh() -> Design:
    design = Design("dims")
    design.board(mm(50), mm(30))
    return design


def test_three_new_kinds() -> None:
    """Scenario "Three new kinds"."""
    d = fresh()
    d.radial_dimension("r", (mm(10), mm(10)), (mm(12), mm(12)), leader_length=mm(3))
    d.leader("l", (mm(20), mm(10)), (mm(23), mm(7)), text="NOTE", frame="circle")
    d.center_mark("c", (mm(30), mm(10)), (mm(32), mm(10)))
    board = to_model(d).board
    assert board is not None
    found = {dim.kind: dim for dim in board.dimensions}
    assert sorted(found) == ["center", "leader", "radial"]
    assert found["radial"].leader_length == 3_000_000 and found["radial"].offset == 0
    assert (found["leader"].text, found["leader"].frame) == ("NOTE", "circle")
    assert found["center"].text is None and found["center"].leader_length is None
    for key, kind in (("r", "radial"), ("l", "leader"), ("c", "center")):
        assert found[kind].id == derived_id("dim", "dsl", f"dimension:{key}")
    with pytest.raises(DslError, match="frame"):
        d.leader("l2", (mm(20), mm(10)), (mm(23), mm(7)), text="X", frame="star")


@pytest.mark.parametrize(
    ("call", "match"),
    [
        (lambda d: d.radial_dimension("a", (mm(1), mm(1)), (mm(2), mm(2)), leader_length=0), "leader_length"),
        (
            lambda d: d.radial_dimension("b", (mm(1), mm(1)), (mm(1), mm(1)), leader_length=mm(1)),
            "same point",
        ),
        (lambda d: d.leader("c", (mm(1), mm(1)), (mm(2), mm(2)), text=""), "text"),
        (lambda d: d.leader("d", (mm(1), mm(1)), (mm(2), mm(2)), text="A\nB"), "text"),
        (lambda d: d.center_mark("e", (mm(1), mm(1)), (mm(2), mm(1)), layer="Nope"), "layer"),
        (lambda d: d.leader("f", (mm(1), mm(1)), (mm(2), mm(2)), text="X", units="cm"), "units"),
    ],
)
def test_refused_values(call, match: str) -> None:  # noqa: ANN001
    with pytest.raises(DslError, match=match):
        call(fresh())


@pytest.mark.parametrize("target", [9, 10])
def test_written_in_the_demo_forms(tmp_path: Path, target: int) -> None:
    """The radial dimension and the leader take the children of the demo boards' radial and leader
    dimensions (S-0058), the centre mark a ``style`` only; the board reads them back and a second build
    writes the same bytes."""
    script = blink_variant(tmp_path / "src", append=LINES)
    out = tmp_path / "out"
    args = ("build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm")
    reply = run(*args, cwd=script.parent, timestamp=STAMP)
    assert reply.exit_code == 0, reply.error
    first = (out / "blink.kicad_pcb").read_bytes()
    root = parse(first.decode("utf-8"))
    by_kind = {dumps(d.find("type"), style="compact"): d for d in root.nodes("dimension")}  # type: ignore[arg-type]
    radial, leader, center = by_kind["(type radial)"], by_kind["(type leader)"], by_kind["(type center)"]
    assert dumps(radial.find("leader_length"), style="compact") == "(leader_length 3)"  # type: ignore[arg-type]
    assert radial.find("height") is None and radial.find("format").find("prefix") == parse('(prefix "R ")')  # type: ignore[union-attr]
    assert dumps(leader.find("format"), style="compact") == (  # type: ignore[arg-type]
        '(format (prefix "") (suffix "") (units 2) (units_format 0) (precision 4) (override_value "NOTE"))'
    )
    assert leader.find("style").find("text_frame") == parse("(text_frame 1)")  # type: ignore[union-attr]
    assert [c.name for c in center.nodes()] == ["type", "layer", "uuid", "pts", "style"]
    back = read_board(out / "blink.kicad_pcb")
    assert back.board is not None
    assert sorted((d.kind, d.leader_length, d.text, d.frame) for d in back.board.dimensions) == [
        ("center", None, None, None),
        ("leader", None, "NOTE", "rect"),
        ("radial", 3_000_000, None, None),
    ]
    assert run(*args, cwd=script.parent, timestamp=STAMP).exit_code == 0
    assert (out / "blink.kicad_pcb").read_bytes() == first
