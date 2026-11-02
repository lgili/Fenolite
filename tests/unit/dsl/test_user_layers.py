# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""User layers (capability design-dsl, "User layers in the DSL"; change c0277): ``design.user_layers()``
adds ``User.1`` … ``User.<n>`` to the created layer table, as KiCad 9.0 and 10.0 write them, and drawings
may go on them."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.dsl import Design, DslError, mm, to_model

STAMP = "2026-10-30T00:00:00Z"
LINES = (
    'design.user_layers(9, names={"User.9": "plugins.config"})\n'
    'design.text("note", "NOTE", (mm(5), mm(5)), layer="User.2")\n'
    'design.circle("ring", (mm(10), mm(10)), (mm(11), mm(10)), layer="User.4", width=mm("0.1"))\n'
    'design.dimension("span", (mm(0), mm(0)), (mm(20), mm(0)), offset=mm(-3), layer="User.2")\n'
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_user_layers_in_the_model() -> None:
    design = Design("user")
    design.board(mm(20), mm(20))
    design.user_layers(3, names={"User.2": "notes"})
    design.text("t", "T", (mm(1), mm(1)), layer="User.3")
    board = to_model(design).board
    assert board is not None
    assert [(layer.name, layer.kind) for layer in board.layers] == [(f"User.{k}", "user") for k in (1, 2, 3)]
    assert dict(board.layers[1].ext["kicad"].payload) == {"user_name": "notes"}
    assert board.texts[0].layer == "User.3"


@pytest.mark.parametrize(
    ("count", "names", "match"),
    [
        (0, None, "count must be"),
        (46, None, "count must be"),
        (True, None, "count must be"),
        (2, {"User.3": "x"}, "not one of"),
        (2, {"User.2": " x"}, "printable"),
    ],
)
def test_refusals(count: object, names: object, match: str) -> None:
    design = Design("user")
    design.board(mm(20), mm(20))
    with pytest.raises(DslError, match=match):
        design.user_layers(count, names=names)  # type: ignore[arg-type]


def test_undeclared_user_layer_is_refused() -> None:
    design = Design("user")
    design.board(mm(20), mm(20))
    design.user_layers(1)
    with pytest.raises(DslError, match="takes no drawing"):
        design.text("t", "T", (mm(1), mm(1)), layer="User.2")
    with pytest.raises(DslError, match="already declared"):
        design.user_layers(2)


@pytest.mark.parametrize("target", [9, 10])
def test_user_layers_built(tmp_path: Path, target: int) -> None:
    script = blink_variant(tmp_path / "src", append=LINES)
    out = tmp_path / "out"
    reply = run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm",
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    root = parse((out / "blink.kicad_pcb").read_text(encoding="utf-8"))
    table = root.find("layers")
    assert table is not None
    rows = [dumps(row, style="compact") for row in table.nodes()]
    assert rows[-10] == '(33 "B.Fab" user)'
    assert rows[-9:] == [f'({37 + 2 * k} "User.{k}" user)' for k in range(1, 9)] + [
        '(55 "User.9" user "plugins.config")'
    ]
    layers = {
        node.find("layer").atoms()[0].value
        for node in root.nodes()
        if node.name in ("gr_text", "gr_circle", "dimension")
    }  # type: ignore[union-attr]
    assert layers == {"User.2", "User.4"}
    again = run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm",
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip
    assert again.exit_code == 0, again.error
    assert parse((out / "blink.kicad_pcb").read_text(encoding="utf-8")) == root
