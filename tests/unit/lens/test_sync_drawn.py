# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite sync --to-source`` with a drawn schematic (capability layout-lens, "Drawn schematic in the
source tree" and "Drawn schematic sync refuses changed nets"; change c0276)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _project import Project, codes

from fenolite.lens.drawn import read_drawn

SYNC = ("--to-source",)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _drawn_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    return Project(tmp_path, monkeypatch, folder="examples/drawn", name="drawn")


def _edit_sheet(p: Project, old: str, new: str) -> None:
    sheet = p.out / "drawn.kicad_sch"
    text = sheet.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    sheet.write_text(text.replace(old, new), encoding="utf-8")


def _plan(env: dict[str, object]) -> list[str]:
    return [Path(w["path"]).name for w in env["result"].get("plan", [])]  # type: ignore[union-attr,index]


def test_an_unchanged_drawing_plans_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The first sync writes the drawing in its extracted form (one wire per segment, field poses); after
    it, an unchanged project plans no drawn file, and never a schematic-placements.toml."""
    p = _drawn_project(tmp_path, monkeypatch)
    code, env, err = p.run("sync", *SYNC, "--confirm")
    assert code == 0, err and "schematic-placements.toml" not in _plan(env)
    code, _env, err = p.build("--confirm")
    assert code == 0, err
    code, env, err = p.run("sync", *SYNC, "--dry-run")
    assert code == 0, err
    assert "schematic.toml" not in _plan(env) and "schematic-placements.toml" not in _plan(env)
    assert env["result"]["drawn"]["planned"] is False  # type: ignore[index]


def test_wire_moved_in_kicad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Wire moved in KiCad": the stub of SDA lengthened past its label, nets unchanged."""
    p = _drawn_project(tmp_path, monkeypatch)
    _edit_sheet(p, "(xy 118.11 69.85) (xy 118.11 64.77)", "(xy 118.11 69.85) (xy 118.11 62.23)")
    code, env, err = p.run("sync", *SYNC, "--dry-run")
    assert code == 0, err and "schematic.toml" in _plan(env)
    plan_id = env["result"]["plan_id"]  # type: ignore[index]
    code, env, err = p.run("sync", *SYNC, "--confirm", "--plan", str(plan_id))
    assert code == 0, err
    drawn = read_drawn((p.script.parent / "schematic.toml").read_text(encoding="utf-8"))
    assert drawn.sheets[0].key == "root"
    code, _env, err = p.build("--confirm")
    assert code == 0, err
    assert "(xy 118.11 62.23)" in (p.out / "drawn.kicad_sch").read_text(encoding="utf-8")


def test_net_changed_in_kicad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Net changed in KiCad"."""
    p = _drawn_project(tmp_path, monkeypatch)
    _edit_sheet(p, "(xy 123.19 76.2)", "(xy 130.81 76.2)")
    code, env, _err = p.run("sync", *SYNC, "--dry-run")
    assert code == 5 and "schematic.toml" not in _plan(env)
    differs = [i for i in env["issues"] if i["code"] == "drawn.netlist-differs"]  # type: ignore[union-attr,index]
    assert len(differs) == 1 and differs[0]["where"] == "R1-1"  # type: ignore[index]


def test_freeze_the_blink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Freeze the blink"."""
    p = Project(tmp_path, monkeypatch)
    code, env, err = p.run("sync", *SYNC, "--freeze-schematic", "--dry-run")
    assert code == 0, err
    assert "schematic.toml" in _plan(env) and "drawn.frozen" in codes(env)
    frozen = [i for i in env["issues"] if i["code"] == "drawn.frozen"]  # type: ignore[union-attr,index]
    assert "load_schematic" in frozen[0]["hint"]  # type: ignore[index]
    code, env, err = p.run("sync", *SYNC, "--freeze-schematic", "--confirm")
    assert code == 0, err
    text = (p.script.parent / "schematic.toml").read_text(encoding="utf-8")
    assert read_drawn(text).sheets[0].symbols
    assert "load_schematic" not in p.script.read_text(encoding="utf-8")  # the script is never rewritten
    p.edit_script(
        'design = Design("blink")', 'design = Design("blink")\ndesign.load_schematic("schematic.toml")'
    )
    code, env, err = p.build("--dry-run")
    assert code == 0, err and env["result"]["schematic"]["source"] == "drawn"  # type: ignore[index]
