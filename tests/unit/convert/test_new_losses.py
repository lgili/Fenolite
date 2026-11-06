# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The losses of a conversion of an Altium project to KiCad that change c0428 removes, on authored
inputs: duplicate designators in the generated schematic, and the parameters of the project that holds a
board document converted alone."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

from fenolite.api.conversion import verify_conversion
from fenolite.convert import convert_project
from fenolite.convert.altium_to_kicad import DUPLICATE_DESIGNATORS, DUPLICATE_PLACED
from fenolite.convert.sources import SourceProject, read_source
from fenolite.core.coords import Point

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "tests/data/altium/blink"


def _with_twin(placed: bool) -> tuple[SourceProject, str]:
    """The blink project with one more part that shares the designator of a placed part; on the board too
    when ``placed``."""
    source = read_source(BLINK / "blink.PrjPcb")
    design = source.design
    assert design.board is not None
    on_board = {fp.component_id for fp in design.board.footprints}
    first = next(c for c in design.circuit.components if c.id in on_board and c.ref)
    twin = dataclasses.replace(first, id=first.id.replace(first.id[4:12], "c0428dup", 1), path="")
    circuit = dataclasses.replace(design.circuit, components=(*design.circuit.components, twin))
    board = design.board
    if placed:
        fp = next(fp for fp in board.footprints if fp.component_id == first.id)
        copy = dataclasses.replace(
            fp, id=fp.id.replace(fp.id[4:12], "c0428dup", 1), component_id=twin.id, position=Point(0, 0)
        )
        board = dataclasses.replace(board, footprints=(*board.footprints, copy))
    return dataclasses.replace(
        source, design=dataclasses.replace(design, circuit=circuit, board=board)
    ), first.ref


def test_duplicate_designators_keep_the_schematic() -> None:
    """A part of the schematic alone that shares the designator of a part on the board: the schematic is
    written, the board's part keeps the designator and the other is written ``<ref>_2``; the read-back
    finds no difference that the report does not explain."""
    source, ref = _with_twin(placed=False)
    result = verify_conversion(convert_project(source, to="kicad", allow_lossy=True))
    conversion = result.conversion
    row = conversion.report.row("schematic")
    assert row is not None and row.lost == 0
    assert any(DUPLICATE_DESIGNATORS in r.reason.split("; ") for r in row.reasons)
    assert conversion.schematic is not None
    text = "".join(
        data.decode("utf-8") for key, data in conversion.files.items() if key.endswith(".kicad_sch")
    )
    assert f'"{ref}_2"' in text and f'"{ref}"' in text
    board = conversion.files[conversion.read_back].decode("utf-8")
    assert f'"{ref}_2"' not in board
    assert not [d for d in result.unexplained if ref in d.where], result.unexplained


def test_duplicate_designators_on_the_board_stay() -> None:
    """Two placed parts that share a designator both keep it, on the board as in the source; the
    schematic, which needs distinct designators, is a reported loss, not an internal failure."""
    source, ref = _with_twin(placed=True)
    conversion = convert_project(source, to="kicad", allow_lossy=True)
    row = conversion.report.row("schematic")
    assert row is not None and row.lost == 1
    assert [r.reason for r in row.reasons if r.outcome == "lost"] == [DUPLICATE_PLACED]
    board = conversion.files[conversion.read_back].decode("utf-8")
    assert f'"{ref}_2"' not in board


def test_a_board_alone_takes_its_projects_parameters(tmp_path: Path) -> None:
    """A board document converted alone, in a subfolder of the project that lists it, writes its special
    strings with the project's parameters, as the project's conversion does."""
    folder = tmp_path / "proj"
    (folder / "PCB").mkdir(parents=True)
    for name in ("blink.SchDoc", "blink.SchLib", "blink.PcbLib"):
        shutil.copyfile(BLINK / name, folder / name)
    shutil.copyfile(BLINK / "blink.PcbDoc", folder / "PCB" / "blink.PcbDoc")
    text = (BLINK / "blink.PrjPcb").read_text(encoding="latin-1")
    text = text.replace("DocumentPath=blink.PcbDoc", "DocumentPath=PCB\\blink.PcbDoc")
    assert "DocumentPath=PCB\\blink.PcbDoc" in text
    text += "\r\n[Parameter1]\r\nName=REV_CODE\r\nValue=B2\r\n"
    (folder / "blink.PrjPcb").write_text(text, encoding="latin-1")
    from fenolite.convert.altium_strings import project_parameters

    assert project_parameters(folder / "PCB" / "blink.PcbDoc") == {"REV_CODE": "B2"}
    board = read_source(folder / "PCB" / "blink.PcbDoc").design.board
    assert board is not None and board.title_block is not None
    assert board.title_block.params.get("REV_CODE") == "B2"


def test_a_board_without_its_project_keeps_no_parameters(tmp_path: Path) -> None:
    """No project lists the document: no parameter, nothing found."""
    shutil.copyfile(BLINK / "blink.PcbDoc", tmp_path / "blink.PcbDoc")
    from fenolite.convert.altium_strings import owning_project, project_parameters

    assert owning_project(tmp_path / "blink.PcbDoc") is None
    assert project_parameters(tmp_path / "blink.PcbDoc") == {}


def test_predefined_special_strings_take_kicad_variables() -> None:
    """``.Layer_Name``, ``.Pcb_File_Name``, ``.Pcb_File_Name_No_Path`` and ``.Print_Date`` in any letter
    case become ``${LAYER}``, ``${FILEPATH}``, ``${FILENAME}`` and ``${CURRENT_DATE}``; a project parameter of
    the same name wins; another name is a variable the project does not define (change c0451)."""
    from fenolite.convert.altium_strings import special_text

    assert special_text(".Layer_Name", {}) == ("${LAYER}", ())
    assert special_text(".LAYER_NAME", {}) == ("${LAYER}", ())
    assert special_text("'.Pcb_File_Name_No_Path' on '.print_date'", {}) == (
        "${FILENAME} on ${CURRENT_DATE}",
        (),
    )
    assert special_text(".Pcb_File_Name", {}) == ("${FILEPATH}", ())
    assert special_text(".Layer_Name", {"Layer_Name": "x"}) == ("${Layer_Name}", ())
    assert special_text(".Arc_Count", {}) == ("${Arc_Count}", (".Arc_Count",))  # change c0451
