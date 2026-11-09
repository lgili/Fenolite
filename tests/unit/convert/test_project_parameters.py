# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project parameters and special strings of an Altium conversion (capability design-conversion, "Project
parameters and special strings"; change c0409, B10). The ``[Parameter<n>]`` sections of a ``.PrjPcb`` become
text variables of the board, and a board text that is the special string ``.NAME`` of one, or holds it as
``'.NAME'``, is written as ``${NAME}`` (``docs/formats/altium/project.md``; S-1681).

The source is a copy of the committed blink sample whose project gets authored parameters, and whose board
gets authored texts on the top silkscreen."""

from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path

import pytest
from _gensheets import generated
from _importcode import STAMP

import fenolite.convert as convert_module
from fenolite.api import run
from fenolite.backends.kicad.sexpr import parse
from fenolite.convert import convert_project
from fenolite.convert.altium_strings import altium_text, special_text
from fenolite.convert.sources import SourceProject, read_source
from fenolite.core.coords import Point, Size
from fenolite.model.base import Provenance
from fenolite.model.board import Text

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "tests" / "data" / "altium" / "blink"
PARAMETERS = "\n[Parameter1]\nName=REV_CODE\nValue=B2\n\n[Parameter2]\nName=Made By\nValue=bench\n"
TEXTS = (".REV_CODE", "Rev '.REV_CODE' on '.Print_Time'", ".Comment")


def _source(folder: Path) -> SourceProject:
    shutil.copytree(BLINK, folder)
    project = folder / "blink.PrjPcb"
    project.write_text(project.read_text(encoding="utf-8") + PARAMETERS, encoding="utf-8")
    source = read_source(project)
    board = source.design.board
    assert board is not None
    where = Provenance(backend="altium", file="blink.PcbDoc", file_sha256="", locator="Texts6/Data#c0409")
    added = tuple(
        Text(id=f"txt_0c409000-0000-4000-8000-00000000010{index}", provenance=where, text=value,
             position=Point(10_000_000, 10_000_000 + 3_000_000 * index), layer="F.SilkS",
             size=Size(1_000_000, 1_000_000), thickness=150_000)
        for index, value in enumerate(TEXTS)
    )  # fmt: skip
    board = dataclasses.replace(board, texts=(*board.texts, *added))
    return dataclasses.replace(source, design=dataclasses.replace(source.design, board=board))


def test_special_text() -> None:
    params = {"REV_CODE": "B2"}
    assert special_text(".REV_CODE", params) == ("${REV_CODE}", ())
    assert special_text("Rev '.REV_CODE' on '.Print_Time'", params) == ("Rev ${REV_CODE} on ${Print_Time}",
                                                                        (".Print_Time",))  # fmt: skip
    # change c0451: a special string of no parameter is a variable the project does not define
    assert special_text(".rev_code", params) == ("${rev_code}", (".rev_code",))
    assert special_text(".PCB Code", params) == (".PCB Code", (".PCB Code",))
    assert special_text("plain", params) == ("plain", ())


def test_altium_text() -> None:
    """The way back (change c0451): ``${NAME}`` alone is ``.NAME``, inside other text ``'.NAME'``, and a
    predefined board variable is its special string."""
    assert altium_text("${REV_CODE}") == (".REV_CODE", ("${REV_CODE}",))
    assert altium_text("Rev ${REV_CODE} on ${CURRENT_DATE}") == (
        "Rev '.REV_CODE' on '.Print_Date'",
        ("${REV_CODE}", "${CURRENT_DATE}"),
    )
    assert altium_text("${LAYER}") == (".Layer_Name", ("${LAYER}",))
    assert altium_text("plain $ {x}") == ("plain $ {x}", ())


def test_parameters_become_text_variables(tmp_path: Path) -> None:
    source = _source(tmp_path / "blink")
    board = source.design.board
    assert board is not None and board.title_block is not None
    assert board.title_block.params == {"REV_CODE": "B2"}
    assert any(
        issue.code == "altium.import.unmapped" and "'Made By'" in issue.message for issue in source.issues
    )
    conversion = convert_project(source, to="kicad", allow_lossy=True)
    pro = next(data for key, data in conversion.files.items() if key.endswith(".kicad_pro"))
    assert json.loads(pro)["text_variables"] == {"REV_CODE": "B2"}
    pcb = parse(conversion.files[conversion.read_back].decode())
    written = [node.atoms()[0].value for node in pcb.nodes("gr_text")]
    assert (
        "${REV_CODE}" in written and "Rev ${REV_CODE} on ${Print_Time}" in written and "${Comment}" in written
    )
    changed = [row for row in conversion.report.rows if row.kind == "text"]
    assert changed and all(row.lost == 0 for row in changed)


def test_parameters_come_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Parameters come back" (change c0451): the KiCad project of the conversion, converted to
    Altium, gives the source's special strings and the project parameter ``REV_CODE``. The first leg writes
    the generated schematic, whose netlist the pure way back reads without ``kicad-cli`` (change c0470)."""
    generated(monkeypatch)
    conversion = convert_project(_source(tmp_path / "blink"), to="kicad", allow_lossy=True)
    for name, data in conversion.files.items():
        (tmp_path / "k" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "k" / name).write_bytes(data)
    back = convert_project(next((tmp_path / "k").glob("*.kicad_pro")), to="altium", allow_lossy=True)
    for name, data in back.files.items():
        (tmp_path / "a" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "a" / name).write_bytes(data)
    project = next((tmp_path / "a").glob("*.PrjPcb"))
    assert "[Parameter1]\nName=REV_CODE\nValue=B2" in project.read_text(encoding="utf-8").replace(
        "\r\n", "\n"
    )
    board = read_source(project).design.board
    assert board is not None
    assert [t.text for t in board.texts if t.text.startswith((".", "Rev"))][-3:] == list(TEXTS)
    assert any(row.kind == "text" and row.changed for row in back.report.rows)


@pytest.fixture
def injected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source = _source(tmp_path / "blink")
    original = convert_module.read_source
    path = tmp_path / "blink" / "blink.PrjPcb"

    def read(given: Path) -> SourceProject:
        return source if Path(given) == path else original(given)

    monkeypatch.setattr(convert_module, "read_source", read)
    return path


def test_import_keeps_the_variables(injected: Path, tmp_path: Path) -> None:
    reply = run("import", str(injected), "--to", "python", "--out", "out", "--confirm", "--allow-lossy",
                cwd=tmp_path, timestamp=STAMP)  # fmt: skip
    assert reply.exit_code == 0, reply.error
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert '"REV_CODE": "B2"' in code and "${REV_CODE}" in code
