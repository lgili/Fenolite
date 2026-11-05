# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""3D models of an Altium import (capability import-python, "3D models of an Altium import"; change c0409,
B9): ``convert --to kicad`` and ``import --to python`` of one project write the same models. The board's
footprints hold them, so the library the import derives from the board holds them too, and the import writes
the model files at the paths its footprints name.

The source is the committed blink sample whose LED footprint gets an authored body naming an authored STEP
file in memory, with the Altium reader's embedded models replaced by that file, as in the c0223 tests; the
footprint is put on the top, where a model is placed."""

from __future__ import annotations

import dataclasses
from collections import Counter
from pathlib import Path

import pytest
from _importcode import STAMP

import fenolite.convert as convert_module
from fenolite.api import run
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.base import BodyModel
from fenolite.backends.kicad.sexpr import parse
from fenolite.convert import convert_project
from fenolite.convert.sources import SourceProject, read_source
from fenolite.core.coords import Point
from fenolite.model.base import Provenance
from fenolite.model.board import ComponentBody

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"
STEP = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
LOCATOR = "ComponentBodies6/Data#0"


def _source() -> tuple[SourceProject, BodyModel]:
    source = read_source(BLINK)
    board = source.design.board
    assert board is not None
    counts = Counter(fp.lib_ref for fp in board.footprints)
    index, chosen = next((i, fp) for i, fp in enumerate(board.footprints) if counts[fp.lib_ref] == 1)
    where = Provenance(backend="altium", file="blink.PcbDoc", file_sha256="", locator=LOCATOR)
    body = ComponentBody(id="bdy-c0409", provenance=where, kind="model", height=5_000_000, model="part.step")
    placed = dataclasses.replace(chosen, bodies=(body,), side="top")
    footprints = (*board.footprints[:index], placed, *board.footprints[index + 1 :])
    design = dataclasses.replace(source.design, board=dataclasses.replace(board, footprints=footprints))
    model = BodyModel(
        locator=LOCATOR, name="part.step", format="step", data=STEP,
        position=Point(chosen.position.x, chosen.position.y), z=0, rotation=(0, 0, chosen.rotation),
    )  # fmt: skip
    return dataclasses.replace(source, design=design), model


def _models(text: str) -> list[str]:
    root = parse(text)
    holders = root.nodes("footprint") if root.name == "kicad_pcb" else [root]
    return [model.atoms()[0].value for holder in holders for model in holder.nodes("model")]


@pytest.fixture
def injected(monkeypatch: pytest.MonkeyPatch) -> SourceProject:
    source, model = _source()
    original = convert_module.read_source

    def models(self: AltiumBackend, path: Path, **_: object) -> tuple[BodyModel, ...]:
        return (model,)

    def read(path: Path) -> SourceProject:
        return source if Path(path) == BLINK else original(path)

    monkeypatch.setattr(AltiumBackend, "body_models", models)
    monkeypatch.setattr(convert_module, "read_source", read)
    return source


def test_convert_places_the_model_on_the_board(injected: SourceProject) -> None:
    conversion = convert_project(injected, to="kicad", allow_lossy=True)
    board = _models(conversion.files[conversion.read_back].decode())
    assert len(board) == 1 and board[0].startswith("${KIPRJMOD}/blink.3dshapes/")
    library = [path for key, data in conversion.files.items() if key.endswith(".kicad_mod")
               for path in _models(data.decode())]  # fmt: skip
    assert library == board
    assert conversion.files[board[0].removeprefix("${KIPRJMOD}/")] == STEP


def test_import_keeps_the_model(injected: SourceProject, tmp_path: Path) -> None:
    reply = run("import", str(BLINK), "--to", "python", "--out", "out", "--confirm", "--allow-lossy",
                cwd=tmp_path, timestamp=STAMP)  # fmt: skip
    assert reply.exit_code == 0, reply.error
    out = tmp_path / "out"
    found = [
        path for mod in sorted(out.rglob("*.kicad_mod")) for path in _models(mod.read_text(encoding="utf-8"))
    ]
    assert len(found) == 1 and found[0].startswith("${KIPRJMOD}/blink.3dshapes/")
    assert (out / found[0].removeprefix("${KIPRJMOD}/")).read_bytes() == STEP
