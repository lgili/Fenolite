# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing sheet of a build (capability design-dsl, "Drawing sheets in a build"; kicad-file-backend,
"Projects carry the drawing sheet and text variables"; change c0074). The sheet texts are authored here."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from _project import Project, codes

from fenolite.backends.kicad import pro, wks
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.templates import example_path

LEGACY = """(page_layout
\t(setup
\t\t(textsize 1.5 1.5)
\t\t(linewidth 0.15)
\t\t(textlinewidth 0.15)
\t\t(left_margin 10)
\t\t(right_margin 10)
\t\t(top_margin 10)
\t\t(bottom_margin 10)
\t)
\t(rect
\t\t(name "")
\t\t(start 0 0 ltcorner)
\t\t(end 0 0)
\t)
\t(tbtext "FENOLITE FRAME ${PROJECT_CODE}"
\t\t(name "")
\t\t(pos 20 20 ltcorner)
\t)
)
"""
"""A drawing sheet with the legacy root name, authored for these tests."""
ADD = "design.add(u1, r1, d1)"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def with_sheet(p: Project, call: str, text: str | None = LEGACY, name: str = "frame.kicad_wks") -> Path:
    p.edit_script(ADD, f"{ADD}\n{call}")
    path = p.script.parent / name
    if text is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize("target", [9, 10])
def test_user_sheet_in_a_built_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int) -> None:
    p = Project(tmp_path, monkeypatch, target)
    with_sheet(p, 'design.sheet(drawing_sheet="frame.kicad_wks")')
    fresh = tmp_path / "fresh"
    code, env, err = p.run("build", "--confirm", out=fresh)
    assert code == 0, err
    written = [Path(w["path"]).name for w in env["receipt"]["written"]]  # type: ignore[index]
    assert "blink.kicad_wks" in written
    text = (fresh / "blink.kicad_wks").read_text(encoding="utf-8")
    root = parse(text)
    assert root.name == "kicad_wks" and "(version 20231118)" in text and "FENOLITE FRAME" in text
    project = json.loads((fresh / "blink.kicad_pro").read_text(encoding="utf-8"))
    assert project["pcbnew"]["page_layout_descr_file"] == "blink.kicad_wks"
    template = json.loads(pro.write_project_text(pro.template(target)))
    assert project["schematic"] == template["schematic"]  # no schematic is written: the key is untouched
    assert "kicad.wks.legacy-root" in codes(env)
    assert env["result"]["drawing_sheet"] == {  # type: ignore[index]
        "source": "frame.kicad_wks",
        "file": "blink.kicad_wks",
        "items": 2,
    }
    record = json.loads((fresh / ".fenolite" / "build.json").read_text(encoding="utf-8"))
    assert "blink.kicad_wks" in record["files"]
    # the written sheet reads back with the same items, and the user's file is untouched
    again = wks.read_drawing_sheet(text, file="blink.kicad_wks")
    source = (p.script.parent / "frame.kicad_wks").read_text(encoding="utf-8")
    assert len(again.items) == 2 and source == LEGACY
    board = read_board((fresh / "blink.kicad_pcb").read_text(encoding="utf-8")).board
    assert board is not None and board.sheet is not None and board.sheet.paper == "A4"


def test_missing_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    with_sheet(p, 'design.sheet(drawing_sheet="frame.kicad_wks")', text=None)
    fresh = tmp_path / "fresh"
    code, env, err = p.run("build", "--dry-run", out=fresh)
    error = json.loads(err)
    assert code == 3 and error["code"] == "FEN-3001" and "frame.kicad_wks" in error["message"]
    assert not fresh.exists() and env.get("result", {}).get("plan") is None  # type: ignore[union-attr]


def test_broken_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    with_sheet(p, 'design.sheet(drawing_sheet="frame.kicad_wks")', text="(kicad_wks (version")
    code, _, err = p.run("build", "--dry-run", out=tmp_path / "fresh")
    assert code == 3 and json.loads(err)["code"] == "FEN-3004"


def test_no_sheet_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    code, env, _ = p.build("--dry-run")
    assert code == 0 and env["result"]["drawing_sheet"] is None  # type: ignore[index]
    assert not (p.out / "blink.kicad_wks").exists()


def test_sheet_specification_and_title_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    frames = p.script.parent / "frames"
    frames.mkdir()
    shutil.copy(example_path("iso5457_generic"), frames / "generic.sheet.toml")
    p.edit_script(
        ADD,
        f'{ADD}\ndesign.sheet("A3", drawing_sheet="frames/generic.sheet.toml")\n'
        'design.title_block(title="Blink", revision="B", variables={"PROJECT_CODE": "X1"})',
    )
    fresh = tmp_path / "fresh"
    code, env, err = p.run("build", "--confirm", out=fresh)
    assert code == 0, err
    result = env["result"]["drawing_sheet"]  # type: ignore[index]
    assert result["source"] == "frames/generic.sheet.toml" and result["file"] == "blink.kicad_wks"  # type: ignore[index]
    assert result["items"] > 5  # type: ignore[index,operator]
    assert parse((fresh / "blink.kicad_wks").read_text(encoding="utf-8")).name == "kicad_wks"
    project = json.loads((fresh / "blink.kicad_pro").read_text(encoding="utf-8"))
    assert project["text_variables"] == {"PROJECT_CODE": "X1"}
    assert project["pcbnew"]["page_layout_descr_file"] == "blink.kicad_wks"
    board = read_board((fresh / "blink.kicad_pcb").read_text(encoding="utf-8")).board
    assert board is not None and board.sheet is not None and board.title_block is not None
    assert board.sheet.paper == "A3" and (board.title_block.title, board.title_block.revision) == (
        "Blink",
        "B",
    )
    # a second build over its own output changes nothing
    p.out = fresh
    first = p.files()
    code, _, err = p.build("--confirm")
    assert code == 0 and p.files() == first, err


def test_edited_sheet_output_is_not_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    with_sheet(p, 'design.sheet(drawing_sheet="frame.kicad_wks")')
    fresh = tmp_path / "fresh"
    assert p.run("build", "--confirm", out=fresh)[0] == 0
    p.out = fresh
    out_sheet = fresh / "blink.kicad_wks"
    out_sheet.write_text(
        out_sheet.read_text(encoding="utf-8").replace("FENOLITE", "EDITED"), encoding="utf-8"
    )
    code, _, err = p.build("--confirm")
    assert code == 7 and "blink.kicad_wks" in err
    code, _, err = p.build("--discard-layout", "--confirm")
    assert code == 0 and "FENOLITE FRAME" in out_sheet.read_text(encoding="utf-8"), err


def test_wrong_file_type_is_a_script_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_script(ADD, f'{ADD}\ndesign.sheet(drawing_sheet="frame.pdf")')
    code, _, err = p.build("--dry-run")
    assert code == 3 and json.loads(err)["code"] == "FEN-3004" and "frame.pdf" in err


def test_declared_title_block_follows_the_script_on_a_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The board's own paper and title block are kept by a rebuild, unless the script declares them."""
    p = Project(tmp_path, monkeypatch)
    p.edit_script(ADD, f'{ADD}\ndesign.sheet("A3")\ndesign.title_block(title="Blink", revision="A")')
    code, _, err = p.build("--confirm")
    assert code == 0, err
    board = p.read().board
    assert board is not None and board.sheet is not None and board.title_block is not None
    assert (board.sheet.paper, board.title_block.revision) == ("A3", "A")
    p.edit_script('revision="A"', 'revision="B"')
    p.edit_script('design.sheet("A3")', 'design.sheet("A2")')
    code, _, err = p.build("--confirm")
    assert code == 0, err
    board = p.read().board
    assert board is not None and board.sheet is not None and board.title_block is not None
    assert (board.sheet.paper, board.title_block.title, board.title_block.revision) == ("A2", "Blink", "B")
    # without the calls the board keeps what it has
    p.edit_script('design.sheet("A2")\n', "")
    p.edit_script('design.title_block(title="Blink", revision="B")', "")
    first = p.files()
    code, _, err = p.build("--confirm")
    board = p.read().board
    assert code == 0 and board is not None and board.title_block is not None, err
    assert board.sheet is not None and (board.sheet.paper, board.title_block.revision) == ("A2", "B")
    assert p.files() == first
