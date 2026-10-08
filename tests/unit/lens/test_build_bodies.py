# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A script height becomes a body of the placed footprint, kept in ``.fenolite/`` through a rebuild
(capability design-dsl, "Part heights in a build"; change c0140)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _buildhelp import blink, blink_variant, build

import fenolite.cli.main as cli_main
from fenolite.core.ids import derived_id
from fenolite.dsl import heights, mm
from fenolite.model import canonical
from fenolite.model.board import Board, FootprintInstance, outward_height

R1 = 'r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")'
TALL = 'r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330", height=mm(9))'
FLAGS = ["--seed", "1", "--timestamp", "2026-01-01T00:00:00Z"]


def _cli_build(script: Path, out: Path, target: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(out.parent / "kc"))
    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stderr", io.StringIO())
    argv = ["build", str(script), "--out", str(out), "--confirm", "--json", *FLAGS]
    assert cli_main.main([*argv, "--kicad-version", str(target)]) == 0


def _footprints(out: Path) -> dict[str, FootprintInstance]:
    board = canonical.loads((out / ".fenolite" / "board.json").read_text(encoding="utf-8"), Board)
    circuit = (out / ".fenolite" / "circuit.json").read_text(encoding="utf-8")
    refs = {component["id"]: component["ref"] for component in json.loads(circuit)["components"]}
    return {refs[fp.component_id]: fp for fp in board.footprints}


def _assert_body(out: Path) -> None:
    found = _footprints(out)
    (body,) = found["R1"].bodies
    assert body.id == derived_id("bdy", "dsl", "height:R1")
    assert (body.kind, body.height, body.standoff, body.outline, body.name) == (
        "extruded",
        9_000_000,
        0,
        (),
        "height",
    )
    assert outward_height(found["R1"]) == 9_000_000
    assert all(not fp.bodies for ref, fp in found.items() if ref != "R1")


@pytest.mark.parametrize("target", [9, 10])
def test_the_body_is_stored_and_survives_a_rebuild(
    target: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tall = blink_variant(tmp_path / "tall", R1, TALL)
    plain = blink_variant(tmp_path / "plain")
    out, ref = tmp_path / "B", tmp_path / "ref"
    _cli_build(tall, out, target, monkeypatch)
    _assert_body(out)
    _cli_build(plain, ref, target, monkeypatch)
    assert (out / "blink.kicad_pcb").read_bytes() == (ref / "blink.kicad_pcb").read_bytes()
    _cli_build(tall, out, target, monkeypatch)  # the rebuild over the existing board
    _assert_body(out)
    assert (out / "blink.kicad_pcb").read_bytes() == (ref / "blink.kicad_pcb").read_bytes()


@pytest.mark.parametrize("target", [9, 10])
def test_every_kicad_file_has_the_bytes_of_a_build_without_height(target: int) -> None:
    design = blink()
    assert dict(heights(design)) == {}
    plain = build(design, target)
    stated = build(blink(), target, heights={"R1": mm(9).nm, "NOPE": mm(1).nm})
    differ = {name for name in plain.files if plain.files[name] != stated.files.get(name)}
    assert set(stated.files) == set(plain.files)
    assert differ <= {".fenolite/board.json", ".fenolite/build.json"}
    assert all(not name.startswith(("blink.", "lib/")) for name in differ)
    assert stated.design.board is not None
    tall = [fp for fp in stated.design.board.footprints if fp.bodies]
    assert len(tall) == 1 and outward_height(tall[0]) == 9_000_000
