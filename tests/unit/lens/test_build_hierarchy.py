# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Module sheets in a build (capability design-dsl, "Hierarchical sheets in a build"; change c0070): the
child files, the layout option, a stale and an edited child sheet, the first readable build over a board
of the flat form, and the stand-in for KiCad's update on a hierarchy. Hermetic: no tool runs."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from _layout_edit import MM, footprint_node, move_footprint, update_from_schematic
from _lensfix import FOLDER, NAME
from _project import ROOT, Project, codes
from _schbuild import NESTED, built_nested, nested_design, root_name

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.lens.build import BUILD_ISSUE_CODES, RECORD_FILE, stale_sheets

IO, POWER = "sheets/io.kicad_sch", "sheets/power.kicad_sch"
SHEETS = (f"{NAME}.kicad_sch", IO, POWER)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


class Unbuilt(Project):
    """The acceptance design copied like ``Project``, without the first build."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int = 10) -> None:
        self.monkeypatch = monkeypatch
        self.target = target
        self.name = NAME
        root = tmp_path / "repo"
        shutil.copytree(ROOT / FOLDER, root / FOLDER)
        shutil.copytree(ROOT / "tests" / "data" / "libs", root / "tests" / "data" / "libs")
        self.script = root / FOLDER / "design.py"
        self.out = tmp_path / "B"


def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    return Project(tmp_path, monkeypatch, 10, folder=FOLDER, name=NAME)


def snapshot(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in folder.rglob("*")
        if p.is_file() and p.suffix != ".bak"
    }


def written(env: dict[str, object], out: Path) -> list[str]:
    return sorted(Path(w["path"]).relative_to(out).as_posix() for w in env["receipt"]["written"])  # type: ignore[index]


def path_of(text: str, ref: str) -> str:
    found = footprint_node(text, ref).find("path")
    assert found is not None
    return found.atoms()[0].value


def test_module_sheets_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Unbuilt(tmp_path, monkeypatch)
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert set(SHEETS) <= set(written(env, p.out))
    summary = env["result"]["schematic"]  # type: ignore[index]
    assert (summary["sheets"], summary["files"]) == (3, [IO, POWER])
    assert summary["symbols"] == 8 + summary["power_flags"], "counted over every sheet"
    record = json.loads((p.out / RECORD_FILE).read_text(encoding="utf-8"))["files"]
    for name in SHEETS:
        assert record[name] == hashlib.sha256((p.out / name).read_bytes()).hexdigest()
    first = snapshot(p.out)
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert snapshot(p.out) == first, "a second build writes every file with the same bytes"
    assert "build.schematic-replaced" not in codes(env) and "build.sheet-stale" not in codes(env)
    root = (p.out / f"{NAME}.kicad_sch").read_text(encoding="utf-8")
    assert [box.find("uuid") is not None for box in parse(root).nodes("sheet")] == [True, True]


def test_grid_layout_on_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Unbuilt(tmp_path, monkeypatch)
    code, env, err = p.build("--schematic-layout", "grid", "--confirm")
    assert code == 0, err
    assert not [name for name in written(env, p.out) if name.startswith("sheets/")]
    summary = env["result"]["schematic"]  # type: ignore[index]
    assert (summary["sheets"], summary["files"], summary["wires"], summary["satellites"]) == (1, [], 0, 0)
    root = (p.out / f"{NAME}.kicad_sch").read_text(encoding="utf-8")
    assert "(wire" not in root and not parse(root).nodes("sheet")


def test_module_gone_later(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The module ``io`` gets another name without ``moved()``: its old sheet is no sheet any more."""
    p = project(tmp_path, monkeypatch)
    old = (p.out / IO).read_bytes()
    p.edit_script('io = Module("io")', 'io = Module("inout")')
    code, env, err = p.build("--discard-layout", "--confirm")
    assert code == 0, err
    stale = [i for i in env["issues"] if i["code"] == "build.sheet-stale"]  # type: ignore[union-attr,index]
    assert len(stale) == 1 and IO in stale[0]["message"] and stale[0]["severity"] == "warning"
    assert (p.out / IO).read_bytes() == old, "the build deletes nothing"
    root = (p.out / f"{NAME}.kicad_sch").read_text(encoding="utf-8")
    assert IO not in root and "sheets/inout.kicad_sch" in root
    code, env, err = p.build("--confirm")
    assert code == 0 and "build.sheet-stale" not in codes(env), "the warning is given once"


def test_edited_child_sheet_is_replaced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = project(tmp_path, monkeypatch)
    built = (p.out / IO).read_bytes()
    (p.out / IO).write_bytes(built + b"\n")
    code, env, err = p.build("--confirm")
    assert code == 0, err
    replaced = [i for i in env["issues"] if i["code"] == "build.schematic-replaced"]  # type: ignore[union-attr,index]
    assert len(replaced) == 1 and replaced[0]["where"].replace("\\", "/").endswith(IO)
    assert "build.layout-exists" not in codes(env)
    assert (p.out / IO).read_bytes() == built


def test_board_survives_the_first_readable_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Unbuilt(tmp_path, monkeypatch)
    code, _, err = p.build("--schematic-layout", "grid", "--confirm")
    assert code == 0, err
    flat = p.board.read_text(encoding="utf-8")
    assert path_of(flat, "R1").count("/") == 1 and path_of(flat, "R4").count("/") == 1
    p.edit_board(lambda text: move_footprint(move_footprint(text, "R1", 3 * MM, MM), "R4", -2 * MM, 2 * MM))
    edited = read_board(p.board.read_text(encoding="utf-8"))
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert not {"layout.orphan", "layout.net-removed"} & set(codes(env))
    text = p.board.read_text(encoding="utf-8")
    rebuilt = read_board(text)
    assert edited.board is not None and rebuilt.board is not None
    was = {f.component_id: f.position for f in edited.board.footprints}
    refs = {c.id: c.ref for c in rebuilt.circuit.components}
    now = {refs[f.component_id or ""]: f.position for f in rebuilt.board.footprints}
    old_refs = {c.id: c.ref for c in edited.circuit.components}
    assert now == {old_refs[cid or ""]: at for cid, at in was.items()}, "every footprint is where it was"
    assert path_of(text, "U1").count("/") == 1
    for ref in ("R1", "R2", "R3", "D1", "R4", "D2", "R5"):
        assert path_of(text, ref).count("/") == 2, ref
    assert sorted(written(env, p.out) and [n for n in written(env, p.out) if n.startswith("sheets/")]) == [
        IO,
        POWER,
    ]


def test_layout_option_is_refused_for_altium(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Unbuilt(tmp_path, monkeypatch)
    code, _, err = p.build("--target", "altium", "--schematic-layout", "grid", "--dry-run")
    assert code == 2 and json.loads(err)["code"] == "FEN-2001" and "--schematic-layout" in err


def test_skip_ignores_the_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Unbuilt(tmp_path, monkeypatch)
    code, env, err = p.build("--schematic", "skip", "--schematic-layout", "grid", "--dry-run")
    assert code == 0, err
    assert env["result"]["schematic"] is None  # type: ignore[index]


# -- build_design


def test_stale_sheets_come_from_the_record() -> None:
    files = {"sheets/io.kicad_sch": b"", "x.kicad_sch": b""}
    record = {
        "sheets/io.kicad_sch": "0",
        "sheets/old.kicad_sch": "0",
        "sheets/notes.txt": "0",
        "old.kicad_sch": "0",
    }
    (issue,) = stale_sheets(record, files)
    assert (issue.code, issue.severity, issue.where) == (
        "build.sheet-stale",
        "warning",
        "sheets/old.kicad_sch",
    )
    assert stale_sheets(None, files) == [] and stale_sheets({}, files) == []
    assert BUILD_ISSUE_CODES["build.sheet-stale"] == "warning"
    assert BUILD_ISSUE_CODES["build.sheet-file-collision"] == "error"
    output = built_nested(record={"sheets/gone.kicad_sch": "0"})
    assert [i.where for i in output.issues if i.code == "build.sheet-stale"] == ["sheets/gone.kicad_sch"]
    assert output.files, "a warning: the build still returns its files"
    assert built_nested(schematic="skip", record={"sheets/gone.kicad_sch": "0"}).schematic is None


def test_summary_counts_every_sheet() -> None:
    output = built_nested()
    summary = output.summary["schematic"]
    assert isinstance(summary, dict)
    assert summary["sheets"] == 4 and len(summary["files"]) == 3
    assert summary["symbols"] == 4 + summary["power_flags"] and summary["no_connects"] == 28
    assert summary["file"] == f"{NESTED}.kicad_sch"


# -- the stand-in for "Update PCB from Schematic"


def texts(output: object) -> dict[str, str]:
    files: dict[str, bytes] = output.files  # type: ignore[attr-defined]
    root = root_name(output)  # type: ignore[arg-type]
    names = [root, *(n for n in files if n.endswith(".kicad_sch") and n.startswith("sheets/"))]
    return {name: files[name].decode("utf-8") for name in names}


def test_stand_in_names_the_sheet_of_each_symbol() -> None:
    output = built_nested()
    board = output.files[f"{NESTED}.kicad_pcb"].decode("utf-8")
    updated = update_from_schematic(board, texts(output))
    for ref in ("U1", "R1", "C1", "R2"):
        assert path_of(updated, ref) == path_of(board, ref), "the build already wrote the path of the update"

    def sheet(ref: str) -> list[str]:
        node = footprint_node(updated, ref)
        return [n.atoms()[0].value for name in ("sheetname", "sheetfile") for n in node.nodes(name)]

    assert sheet("U1") == ["/", f"{NESTED}.kicad_sch"]
    assert sheet("R1") == ["power", "sheets/power.kicad_sch"]
    assert sheet("C1") == ["ldo", "power.ldo.kicad_sch"], "the file as its own parent sheet names it"
    assert sheet("R2") == ["io", "sheets/io.kicad_sch"]
    assert update_from_schematic(updated, texts(output)) == updated
    assert path_of(board, "C1").count("/") == 3


def test_nested_design_is_authored_here() -> None:
    design = nested_design()
    assert sorted(design.parts) == ["U1", "io/R2", "power/R1", "power/ldo/C1"]
