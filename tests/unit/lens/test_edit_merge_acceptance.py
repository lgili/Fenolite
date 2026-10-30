# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The acceptance loop of the edit merge (capability edit-merge, "Edit merge acceptance fixture"; change
c0250): build the fixture ``tests/data/lens/edit_merge``, edit its board and schematic as KiCad would (a
value, a footprint, a reference, a user property and positions), build again, sync, and build twice more."""

from __future__ import annotations

from pathlib import Path

import pytest
from _edit_help import FIXTURE, FIXTURE_EDITS, FIXTURE_NAME, edit_fixture, issues
from _project import Project, footprint


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _keys(env: dict[str, object], code: str) -> list[str]:
    return sorted(i["where"] for i in issues(env, code))


def test_acceptance_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch, folder=FIXTURE, name=FIXTURE_NAME)
    edit_fixture(p)
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert _keys(env, "edit.unrecorded") == sorted(FIXTURE_EDITS)
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
