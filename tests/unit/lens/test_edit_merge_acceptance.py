# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The acceptance loop of the edit merge (capability edit-merge, "Edit merge acceptance fixture"; change
c0250): build the fixture ``tests/data/lens/edit_merge``, edit its board and schematic as KiCad would (a
value, a footprint, a reference, a user property and positions), build again, sync, and build twice more."""

from __future__ import annotations

from pathlib import Path

import pytest
from _edit_help import issues
from _layout_edit import edit_properties
from _project import Project, footprint

MM = 1_000_000
FOLDER = "tests/data/lens/edit_merge"
EDITED = [
    "J1#reference",
    "R1#value",
    "R1#property:Part number",
    "led/D1#position",
    "led/R2#position",
    "led/R2#footprint",
]


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _edit(p: Project) -> None:
    """The edits of the loop, by token edit: the root sheet holds J1 and R1, the sheet of ``led`` R2."""
    root, child = p.out / "edit_merge.kicad_sch", p.out / "sheets" / "led.kicad_sch"
    board, root_text = edit_properties(
        p.board.read_text(encoding="utf-8"),
        root.read_text(encoding="utf-8"),
        {
            "J1": {"reference": "J9"},
            "R1": {"value": "470", "properties": {"Part number": "FEN-R470"}},
        },
    )
    board, child_text = edit_properties(
        board,
        child.read_text(encoding="utf-8"),
        {"R2": {"footprint": "Fenolite:Chip_0805", "move": (0, 2 * MM)}},
    )
    board, _ = edit_properties(board, None, {"D1": {"move": (MM, 0)}})
    p.board.write_text(board or "", encoding="utf-8")
    root.write_text(root_text or "", encoding="utf-8")
    child.write_text(child_text or "", encoding="utf-8")


def _keys(env: dict[str, object], code: str) -> list[str]:
    return sorted(i["where"] for i in issues(env, code))


def test_acceptance_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch, folder=FOLDER, name="edit_merge")
    _edit(p)
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert _keys(env, "edit.unrecorded") == sorted(EDITED)
    assert not issues(env, "sync.conflict")
    design = p.read()
    _, j9 = footprint(design, "J9")
    _, r1 = footprint(design, "R1")
    r2, _ = footprint(design, "R2")
    assert j9.properties["fenolite.path"] == "J1"  # type: ignore[attr-defined]
    assert r1.value == "470" and r1.properties["Part number"] == "FEN-R470"  # type: ignore[attr-defined]
    assert r2.lib_ref == "Fenolite:Chip_0805"  # type: ignore[attr-defined]
    code, env, err = p.run("sync", "--to-source", "--confirm")
    assert code == 0, err
    edits = (p.script.parent / "edits.toml").read_text(encoding="utf-8")
    for line in (
        'reference = "J9"',
        'value = "470"',
        'properties = { "Part number" = "FEN-R470" }',
        'footprint = "Fenolite:Chip_0805"',
    ):
        assert line in edits
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert not issues(env, "edit.unrecorded") and not issues(env, "sync.conflict")
    before = p.files()
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert not issues(env, "edit.unrecorded") and not issues(env, "edit.code-wins")
    assert p.files() == before
