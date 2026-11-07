# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fresh explicit tables and strict missing-reference controls, using authored Mini inputs only."""

from __future__ import annotations

import base64
import dataclasses
from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point
from fenolite.dsl import Design, mm, to_model
from fenolite.model.board import Image


def script(tmp: Path, omitted: tuple[str, ...] = ("Eco1.User", "Eco2.User")) -> Path:
    technical = tuple(
        layer.name for layer in created_layers(2) if layer.kind != "copper" and layer.name not in omitted
    )
    return blink_variant(
        tmp / "source",
        "design.board(mm(50), mm(30))",
        f"design.board(mm(50), mm(30), technical_layers={technical!r})",
    )


@pytest.mark.parametrize("target", [9, 10])
def test_fresh_table_and_independent_user_layers(tmp_path: Path, target: int) -> None:
    source = script(tmp_path)
    with source.open("a", encoding="utf-8") as stream:
        stream.write('\ndesign.user_layers(2, names={"User.2": "Authored notes"})\n')
    reply = run(
        "build", str(source), "--out", "built", "--confirm", "--kicad-version", str(target), cwd=tmp_path
    )
    assert reply.exit_code == 0, reply.error
    native = read_board(tmp_path / "built/blink.kicad_pcb").board
    assert native is not None
    assert tuple(layer.name for layer in native.layers) == tuple(
        layer.name for layer in created_layers(2, 2) if layer.name not in {"Eco1.User", "Eco2.User"}
    )
    assert dict(native.layers[-1].ext["kicad"].payload)["user_name"] == "Authored notes"
    before = (tmp_path / "built/blink.kicad_pcb").read_bytes()
    again = run(
        "build", str(source), "--out", "built", "--confirm", "--kicad-version", str(target), cwd=tmp_path
    )
    assert again.exit_code == 0, again.error
    assert (tmp_path / "built/blink.kicad_pcb").read_bytes() == before


@pytest.mark.parametrize("kind", ["drawing", "field", "pad"])
def test_omitted_referenced_layer_refuses_every_write(tmp_path: Path, kind: str) -> None:
    omitted = {"drawing": ("Eco1.User",), "field": ("F.SilkS",), "pad": ("F.Mask",)}[kind]
    source = script(tmp_path, omitted)
    if kind == "drawing":
        with source.open("a", encoding="utf-8") as stream:
            stream.write(
                '\ndesign.line("bad", (mm(1), mm(1)), (mm(2), mm(1)), layer="Eco1.User", width=mm("0.1"))\n'
            )
    reply = run("build", str(source), "--out", "built", "--confirm", cwd=tmp_path)
    assert reply.exit_code != 0, reply.result
    assert any(issue["code"] == "kicad.board.layer-undeclared" for issue in (reply.envelope or {})["issues"])
    assert not (tmp_path / "built").exists()


@pytest.mark.parametrize("allow_lossy", [False, True])
def test_modeled_image_is_also_an_undeclared_reference(allow_lossy: bool) -> None:
    design = Design("image")
    design.board(mm(20), mm(10), technical_layers=("Edge.Cuts",))
    model = to_model(design)
    assert model.board is not None
    image = Image(
        id="img-authored",
        position=Point(100_000_000, 100_000_000),
        layer="Eco1.User",
        data=base64.b64encode(b"authored unused image bytes").decode(),
    )
    model = dataclasses.replace(model, board=dataclasses.replace(model.board, images=(image,)))
    with pytest.raises(LossyWriteError) as caught:
        write_board(model, allow_lossy=allow_lossy)
    assert caught.value.droppable is False
    assert [(issue.code, issue.where) for issue in caught.value.issues] == [
        ("kicad.board.layer-undeclared", "Eco1.User")
    ]
