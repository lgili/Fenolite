# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.api.equivalent`` (capability design-equivalence, "Public equivalence API", "Public equivalence
API inputs" and "Public API errors and effects"; change c0158)."""

from __future__ import annotations

import dataclasses
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from _projects import tree_snapshot

from fenolite.api import EquivalenceResult, SideUsageError, equivalent
from fenolite.api import sides as api_sides
from fenolite.backends import registry
from fenolite.backends.kicad.pcb import read_board
from fenolite.cli import _kicadtool
from fenolite.cli import main as cli_main
from fenolite.core.coords import Point
from fenolite.core.evidence import Level
from fenolite.model.design import Design

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"


def _board() -> Design:
    return read_board(TWO_LAYER.read_text(encoding="utf-8"), file=TWO_LAYER.name)


def _moved(tmp_path: Path) -> Path:
    """A copy of the two-layer board with ``R1`` moved by 1 mm, written with the KiCad backend."""
    design = _board()
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    footprints = tuple(
        dataclasses.replace(f, position=Point(f.position.x + 1_000_000, f.position.y))
        if refs[f.component_id] == "R1"
        else f
        for f in design.board.footprints
    )
    changed = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=footprints))
    folder = tmp_path / "moved"
    folder.mkdir()
    target = folder / "moved.kicad_pcb"
    target.write_text(registry.get("kicad").write(changed).text, encoding="utf-8", newline="\n")
    return target


def _cli(monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(cwd)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


def test_same_as_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Same reply as the command"."""
    moved = _moved(tmp_path)
    found = equivalent(TWO_LAYER, moved)
    code, env = _cli(monkeypatch, tmp_path, "equivalent", str(TWO_LAYER), str(moved))
    assert code == 5 and found.equivalent is False
    assert found.to_json() == env["result"]
    issues = [(i.code, i.severity, i.where, i.message) for i in found.issues]
    assert issues == [(i["code"], i["severity"], i["where"], i["message"]) for i in env["issues"]]
    assert env["evidence"]["level"] == found.evidence.level.value


def test_same_as_cli_with_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    moved = _moved(tmp_path)
    found = equivalent(
        str(TWO_LAYER), str(moved), level=4, tolerances={"length_nm": 5}, frame="relative", ignore_refs=["D*"]
    )
    code, env = _cli(
        monkeypatch, tmp_path, "equivalent", str(TWO_LAYER), str(moved), "--level", "4", "--tolerance-nm",
        "5", "--frame", "relative", "--ignore-ref", "D*",
    )  # fmt: skip
    assert found.to_json() == env["result"] and code == (0 if found.equivalent else 5)


def test_two_models() -> None:
    """Scenario "Two models"."""
    design = _board()
    component = next(c for c in design.circuit.components if c.ref == "R1")
    changed = design.replace_entity(dataclasses.replace(component, value=component.value + "0"))
    found = equivalent(design, changed)
    assert isinstance(found, EquivalenceResult) and found.report is not None
    assert found.report.equivalent is False
    assert [(d.kind, d.where) for d in found.report.differences] == [("value", "R1")]
    assert found.b is not None and found.a.backend == found.b.backend == "model"
    assert found.a.sha256 is None and found.evidence.level is Level.INFERRED
    assert found.to_json()["sides"]["a"]["path"] == design.header.name


@pytest.mark.parametrize(
    ("b", "options", "named"),
    [
        (None, {}, "give b"),
        (TWO_LAYER, {"against": "kicad-import"}, "give b"),
        (TWO_LAYER, {"against": "other"}, "against is one of"),
        (TWO_LAYER, {"level": 6}, "level is one of"),
        (TWO_LAYER, {"frame": "turned"}, "frame is one of"),
        (TWO_LAYER, {"tolerances": {"length_nm": -1}}, "length_nm"),
        (TWO_LAYER, {"tolerances": {"width": 1}}, "no field 'width'"),
    ],
)
def test_usage_fault(b: Path | None, options: dict[str, Any], named: str) -> None:
    """Scenario "Usage fault": a ``ValueError`` that names what is wrong."""
    with pytest.raises(ValueError, match=named) as raised:
        equivalent(_board(), b, **options)
    assert isinstance(raised.value, SideUsageError)


def test_usage_fault_names_b() -> None:
    with pytest.raises(ValueError) as raised:
        equivalent(_board(), None)
    assert isinstance(raised.value, SideUsageError) and raised.value.where == "b"
    assert " b " in str(raised.value)


def test_missing_path_and_level_above_the_sides(tmp_path: Path) -> None:
    with pytest.raises(api_sides.SideMissingError) as missing:
        equivalent(TWO_LAYER, tmp_path / "none.kicad_pcb")
    assert missing.value.cli_code == "FEN-3001" and missing.value.where == "none.kicad_pcb"
    circuit = dataclasses.replace(_board(), board=None)
    with pytest.raises(SideUsageError, match="the highest level available is 2"):
        equivalent(circuit, TWO_LAYER, level=3)


def test_hermetic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Hermetic call"."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("equivalent started a subprocess")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    before = tree_snapshot(TWO_LAYER.parent)
    found = equivalent(TWO_LAYER, TWO_LAYER)
    assert found.equivalent and found.report is not None and found.report.levels[-1].level == 5
    assert tree_snapshot(TWO_LAYER.parent) == before


def test_bare_import_leaves_the_api_out() -> None:
    code = "import sys, fenolite; assert 'fenolite.api' not in sys.modules, sorted(sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_tool_hint_is_the_commands() -> None:
    assert api_sides.NO_TOOL_HINT == _kicadtool.NO_TOOL_HINT
