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


def test_replies_validate_against_the_schema(tmp_path: Path) -> None:
    """Capability design-equivalence, "Equivalent result schema", for the forms the example does not give:
    two models, differences, and a triangle whose converter gave no board."""
    import _schema

    schema = _schema.load("fenolite.equivalent.v0.json")
    design = _board()
    found = [equivalent(design, design, level=4), equivalent(TWO_LAYER, _moved(tmp_path))]
    failed = EquivalenceResult(None, found[0].a, None, None, (), found[0].evidence, "10.0.6")
    for result in (*found, failed):
        assert _schema.validate(result.to_json(), schema) == []
    assert failed.to_json()["level"] == 0 and failed.to_json()["sides"]["b"] is None


# --- schematic sides -------------------------------------------------------------------------------

NETLIST = """(export (version "E")
  (components
    (comp (ref "D1") (value "LED") (footprint "Mini:LED") {flag})
    (comp (ref "R1") (value "1k") (footprint "Mini:R")))
  (nets
    (net (code "1") (name "A") (class "Default")
      (node (ref "D1") (pin "1") (pintype "passive")) (node (ref "R1") (pin "1") (pintype "passive")))
    (net (code "2") (name "unconnected-(D1-Pad2)") (class "Default")
      (node (ref "D1") (pin "2") (pintype "passive")))
    (net (code "3") (name "unconnected-(R1-Pad2)") (class "Default")
      (node (ref "R1") (pin "2") (pintype "passive")))))
"""


def _refuse_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _built_blink(root: Path) -> Path:
    from _projects import built_blink_project

    return built_blink_project(root / "blink", target=10, cache=False)


def test_schematic_own(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Generated schematic, no tool"."""
    project = _built_blink(tmp_path)
    _refuse_tools(monkeypatch)
    found = equivalent(project / "blink.kicad_sch", project / "blink.kicad_pcb")
    assert found.report is not None and found.equivalent
    assert [level.level for level in found.report.levels] == [1, 2]
    assert (
        found.a.netlist_source == "schematic" and found.a.kind == "kicad_sch" and found.a.backend == "kicad"
    )
    assert found.a.components == 3 and found.a.footprints == 0 and found.a.sha256 is not None
    assert "H-K-NETLIST-OWN" in found.evidence.hypotheses
    import _schema

    assert _schema.validate(found.to_json(), _schema.load("fenolite.equivalent.v0.json")) == []


def test_schematic_power_symbols(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Power symbol left out"."""
    project = _built_blink(tmp_path)
    _refuse_tools(monkeypatch)
    side = api_sides.read_side(project / "blink.kicad_sch")
    from fenolite.backends.kicad.sch import read_schematic

    sheet = read_schematic((project / "blink.kicad_sch").read_text(encoding="utf-8"), file="blink.kicad_sch")
    refs = {symbol.ref for symbol in sheet.symbols if symbol.ref.startswith("#")}
    assert refs == {"#FLG01", "#FLG02"} and side.power_symbols == len(refs)
    assert not any(c.ref.startswith("#") for c in side.design.circuit.components)
    assert side.design.board is None


def test_schematic_dnp_from_the_export() -> None:
    """Scenario "Flag read", for a netlist that ``kicad-cli`` exported."""
    from fenolite.backends.kicad.netlist import read_netlist

    marked = read_netlist(NETLIST.format(flag='(property (name "dnp"))'))
    assert next(c for c in marked.components if c.ref == "D1").flags == frozenset({"dnp"})
    side_a = api_sides.netlist_design(
        marked, "a", dnp=frozenset(c.ref for c in marked.components if "dnp" in c.flags)
    )
    side_b = api_sides.netlist_design(read_netlist(NETLIST.format(flag="")), "b")
    found = equivalent(side_a, side_b)
    assert found.report is not None
    assert [(d.kind, d.where, d.a, d.b) for d in found.report.differences] == [("dnp", "D1", "true", "false")]


def test_schematic_dnp_from_the_own_netlist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Flag read", for the own netlist: the symbol's ``dnp`` attribute."""
    project = _built_blink(tmp_path)
    sheet = project / "blink.kicad_sch"
    text = sheet.read_text(encoding="utf-8")
    first = text.index("(dnp no)", text.index("(lib_id"))
    sheet.write_text(text[:first] + "(dnp yes)" + text[first + len("(dnp no)") :], encoding="utf-8")
    _refuse_tools(monkeypatch)
    side = api_sides.read_side(sheet)
    marked = [c.ref for c in side.design.circuit.components if c.dnp]
    assert len(marked) == 1
    found = equivalent(sheet, project / "blink.kicad_pcb")
    assert found.report is not None
    assert [(d.kind, d.where) for d in found.report.differences] == [("dnp", marked[0])]


def test_schematic_outside_the_grammar_needs_kicad_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A sheet outside the own netlist's grammar is read through ``kicad-cli``: without one,
    ``ToolMissingError`` (``FEN-6001``) naming the file."""
    from fenolite.backends.kicad import cli as kicad_cli

    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv("FENOLITE_KICAD_CLI", raising=False)
    monkeypatch.setattr(kicad_cli, "MACOS_KICAD_CLI", tmp_path / "missing" / "kicad-cli")
    with pytest.raises(api_sides.ToolMissingError) as raised:
        equivalent(DATA / "kicad" / "schematic" / "flat.kicad_sch", TWO_LAYER)
    assert raised.value.cli_code == "FEN-6001" and raised.value.where == "flat.kicad_sch"
