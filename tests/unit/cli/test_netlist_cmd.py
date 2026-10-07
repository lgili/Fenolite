# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite netlist`` (capability cli-contract, "Netlist command"; change c0063). Hermetic: the source
``kicad`` runs a fake ``kicad-cli`` that writes an authored export, and the source ``fenolite`` runs no
tool at all."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import _netexport
import pytest
from _buildhelp import blink, build
from _checkcli import hide_kicad, run, without_elapsed
from _fakecli import calls, fake_kicad_cli
from _projects import authored_project, tree_snapshot
from _schbuild import built_nested, write_files

from fenolite.backends.kicad import netlist as netlistmod
from fenolite.backends.kicad import oracle as oraclemod
from fenolite.backends.kicad import sch_netlist
from fenolite.cli._examples import EXAMPLE_SCHEMATIC
from fenolite.cli.cmd_netlist import COMMAND
from fenolite.core.evidence import Evidence

DATA = Path(__file__).resolve().parents[2] / "data" / "kicad"
EXPORT = (DATA / "netlist" / "export_10.net").read_text(encoding="utf-8")
FLAT = DATA / "schematic" / "flat.kicad_sch"
HIER = DATA / "schematic" / "hier"
TWO_LAYER = DATA / "board" / "two_layer.kicad_pcb"


@pytest.fixture(autouse=True)
def no_real_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)


def _project(tmp_path: Path) -> Path:
    """An authored project with a schematic beside its board; the fake does not read the sheet."""
    root = authored_project(tmp_path, major=10)
    shutil.copyfile(FLAT, root / "board.kicad_sch")
    return root


def _built(tmp_path: Path) -> Path:
    return write_files(build(blink()), tmp_path / "blink")


def _no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _net(result: dict[str, object], name: str) -> dict[str, object]:
    return next(net for net in result["nets"] if net["name"] == name)  # type: ignore[union-attr,index]


# -- the source kicad


def test_kicad_source_on_a_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _project(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin", netlist=EXPORT, writes=("x.kicad_prl",))
    before = tree_snapshot(root)
    code, env, _, out = run(monkeypatch, tmp_path, "netlist", str(root), "--kicad-cli", str(fake))
    assert code == 0, env
    result = env["result"]
    assert (result["schematic"], result["source"]) == ("board.kicad_sch", "kicad")
    assert result["counts"] == {"components": 3, "nets": 5, "pins": 8, "unconnected": 1, "below_min_pins": 0}
    assert [c["ref"] for c in result["components"]] == ["D1", "R1", "U1"]
    assert result["components"][0] == {
        "ref": "D1",
        "value": "LED",
        "footprint": "Mini:Mini_LED_THT_3mm",
        "properties": {"fenolite.path": "D1", "Footprint": "Mini:Mini_LED_THT_3mm", "Datasheet": ""},
    }
    assert _net(result, "GND") == {
        "name": "GND",
        "class": "PWR",
        "unconnected": False,
        "pins": [
            {"ref": "D1", "pin": "1", "type": "passive"},
            {"ref": "U1", "pin": "10", "type": "power_in"},
        ],
    }
    assert [n["name"] for n in result["nets"]] == sorted(n["name"] for n in result["nets"])
    assert _net(result, "unconnected-(U1-PA1-Pad2)")["unconnected"] is True
    assert _net(result, "VIN")["unconnected"] is False, "one pin, and a name the designer gave"
    assert "2026-01-01" in EXPORT and "/authored" in EXPORT, "the export holds a date and a path"
    for part in (str(tmp_path), "/authored", "KIPRJMOD", "Eeschema", "2026-01-01"):
        assert part not in out, part
    assert env["input"]["path"] == "board.kicad_sch" and env["input"]["kind"] == "kicad_sch"
    assert env["receipt"] is None and tree_snapshot(root) == before
    (call,) = [c for c in calls(fake) if c["args"][:3] == ["sch", "export", "netlist"]]
    assert call["args"][-1] == "board.kicad_sch" and "board.kicad_pro" in call["files"]


def test_kicad_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", netlist=EXPORT)
    _, env, _, _ = run(monkeypatch, tmp_path, "netlist", str(_project(tmp_path)), "--kicad-cli", str(fake))
    expected = Evidence.combine(netlistmod.EVIDENCE, oraclemod.EVIDENCE)
    assert env["evidence"]["level"] == expected.level.value
    assert env["evidence"]["oracle"] == "kicad-cli 10.0.6"
    assert env["evidence"]["hypotheses"] == sorted(expected.hypotheses)


@pytest.mark.parametrize("named", ["board.kicad_sch", "board.kicad_pcb", "board.kicad_pro"])
def test_kicad_source_by_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, named: str) -> None:
    root = _project(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin", netlist=EXPORT)
    code, env, _, _ = run(monkeypatch, root, "netlist", named, "--kicad-cli", str(fake))
    assert code == 0 and env["result"]["schematic"] == "board.kicad_sch"


def test_kicad_source_on_a_schematic_alone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A schematic without a board, with the sheets it names."""
    root = tmp_path / "alone"
    shutil.copytree(HIER, root)
    fake = fake_kicad_cli(tmp_path / "bin", netlist=EXPORT)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "netlist", str(root / "top.kicad_sch"), "--kicad-cli", str(fake)
    )
    assert code == 0 and env["result"]["schematic"] == "top.kicad_sch"


def test_two_runs_are_equal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _project(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin", netlist=EXPORT)
    args = ("netlist", str(root), "--kicad-cli", str(fake), "--timestamp", "2026-01-02T03:04:05Z")
    first = run(monkeypatch, tmp_path, *args)[3]
    second = run(monkeypatch, tmp_path, *args)[3]
    assert without_elapsed(first) == without_elapsed(second)


def test_unloadable_schematic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin")  # no netlist: "Failed to load schematic", exit 3
    code, _, err, _ = run(monkeypatch, tmp_path, "netlist", str(_project(tmp_path)), "--kicad-cli", str(fake))
    assert code == 3 and err["code"] == "FEN-3004"
    assert "Failed to load schematic" in err["message"] and str(tmp_path) not in err["message"]


def test_unreadable_export(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", netlist="(kicad_sch (version 20260306))")
    code, _, err, _ = run(monkeypatch, tmp_path, "netlist", str(_project(tmp_path)), "--kicad-cli", str(fake))
    assert code == 3 and err["code"] == "FEN-3004" and "unreadable netlist export" in err["message"]


def test_no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "netlist", str(_project(tmp_path)))
    assert code == 6 and err["code"] == "FEN-6001" and "--source fenolite" in err["hint"]


def test_unsupported_major(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", netlist=EXPORT, version="8.0.9")
    code, _, err, _ = run(monkeypatch, tmp_path, "netlist", str(_project(tmp_path)), "--kicad-cli", str(fake))
    assert code == 6 and err["code"] == "FEN-6002"


# -- the source fenolite


def test_own_reading_without_a_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _built(tmp_path)
    before = tree_snapshot(root)
    _no_subprocess(monkeypatch)
    code, env, _, out = run(monkeypatch, tmp_path, "netlist", str(root), "--source", "fenolite")
    assert code == 0, env
    result = env["result"]
    assert (result["schematic"], result["source"]) == ("blink.kicad_sch", "fenolite")
    assert result["counts"] == {
        "components": 3,
        "nets": 33,
        "pins": 36,
        "unconnected": 29,
        "below_min_pins": 0,
    }
    assert [p["ref"] + "-" + p["pin"] for p in _net(result, "GND")["pins"]] == ["D1-1", "U1-10"]  # type: ignore[union-attr,index]
    assert _net(result, "unconnected-(U1-PA1-Pad2)")["pins"] == [
        {"ref": "U1", "pin": "2", "type": "bidirectional+no_connect"}
    ]
    assert all(net["class"] == "" for net in result["nets"])
    assert env["evidence"]["level"] == sch_netlist.EVIDENCE.level.value
    assert env["evidence"]["oracle"] is None
    assert env["evidence"]["hypotheses"] == list(sch_netlist.EVIDENCE.hypotheses)
    assert str(tmp_path) not in out and tree_snapshot(root) == before


def test_own_reading_equals_the_export_of_its_own_netlist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Both sources give the same nets, apart from the class, when the tool writes what the sheet means."""
    root = _built(tmp_path)
    output = build(blink())
    assert output.schematic is not None
    export = _netexport.export_text(sch_netlist.own_netlist(output.schematic.sheet, project="blink"))
    fake = fake_kicad_cli(tmp_path / "bin", netlist=export)
    _, theirs, _, _ = run(monkeypatch, tmp_path, "netlist", str(root), "--kicad-cli", str(fake))
    _, ours, _, _ = run(monkeypatch, tmp_path, "netlist", str(root), "--source", "fenolite")

    def nets(env: dict[str, object]) -> list[dict[str, object]]:
        return [{k: v for k, v in net.items() if k != "class"} for net in env["result"]["nets"]]  # type: ignore[index]

    assert nets(ours) == nets(theirs) and ours["result"]["counts"] == theirs["result"]["counts"]  # type: ignore[index]
    assert ours["result"]["components"] == theirs["result"]["components"]  # type: ignore[index]


def test_small_nets_left_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _built(tmp_path)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "netlist", str(root), "--source", "fenolite", "--min-pins", "2"
    )
    assert code == 0
    assert [net["name"] for net in env["result"]["nets"]] == ["GND", "LED_A", "LED_DRV"]
    assert env["result"]["counts"]["below_min_pins"] == 30
    assert env["result"]["counts"]["nets"] == 33 and env["result"]["counts"]["unconnected"] == 29


def test_sheet_outside_the_grammar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _no_subprocess(monkeypatch)
    code, env, err, _ = run(monkeypatch, tmp_path, "netlist", str(FLAT), "--source", "fenolite")
    assert code == 7 and err["code"] == "FEN-7001"
    assert "--source kicad" in err["hint"]
    codes = {issue["code"] for issue in env["issues"]}
    assert codes == {"kicad.sch.netlist-unsupported"}
    reasons = [issue["message"].split(":", 1)[0] for issue in env["issues"]]
    assert "wire" in reasons and "label-kind" in reasons
    assert all(issue["severity"] == "error" for issue in env["issues"])


# -- inputs and usage


def test_no_schematic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "netlist", str(TWO_LAYER))
    assert code == 3 and err["code"] == "FEN-3001" and "two_layer.kicad_sch" in err["message"]
    code, _, err, _ = run(monkeypatch, tmp_path, "netlist", str(tmp_path / "missing.kicad_sch"))
    assert code == 3 and err["code"] == "FEN-3001"
    code, _, err, _ = run(monkeypatch, tmp_path, "netlist", str(tmp_path / "missing"))
    assert code == 3 and err["code"] == "FEN-3001"


def test_ambiguous_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "two"
    root.mkdir()
    for name in ("a.kicad_pcb", "b.kicad_pcb"):
        shutil.copyfile(TWO_LAYER, root / name)
    code, _, err, _ = run(monkeypatch, tmp_path, "netlist", str(root))
    assert code == 2 and err["code"] == "FEN-2001"


@pytest.mark.parametrize("value", ["0", "-3"])
def test_min_pins_below_one(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "netlist", str(FLAT), "--min-pins", value)
    assert code == 2 and err["code"] == "FEN-2001"


def test_unknown_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "netlist", str(FLAT), "--source", "altium")
    assert code == 2 and err["code"] == "FEN-2001"


def test_command_registration() -> None:
    assert COMMAND.name == "netlist" and COMMAND.mutates is False
    assert COMMAND.example_args == (EXAMPLE_SCHEMATIC,) and COMMAND.example_tools == ("kicad-cli",)
    assert Path(EXAMPLE_SCHEMATIC) == FLAT and FLAT.is_file()


# -- module sheets (c0070)


def test_own_reading_of_module_sheets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = write_files(built_nested(), tmp_path / "nested")
    before = tree_snapshot(root)
    _no_subprocess(monkeypatch)
    code, env, _, _ = run(monkeypatch, tmp_path, "netlist", str(root), "--source", "fenolite")
    assert code == 0, env
    result = env["result"]
    assert [c["ref"] for c in result["components"]] == ["C1", "R1", "R2", "U1"]
    assert [(p["ref"], p["pin"]) for p in _net(result, "GND")["pins"]] == [  # type: ignore[union-attr]
        ("C1", "2"),
        ("R2", "2"),
        ("U1", "10"),
    ]
    assert tree_snapshot(root) == before


def test_own_reading_refuses_a_missing_child(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = write_files(built_nested(), tmp_path / "nested")
    (root / "sheets" / "io.kicad_sch").unlink()
    code, env, err, _ = run(monkeypatch, tmp_path, "netlist", str(root), "--source", "fenolite")
    assert code == 7 and err["code"] == "FEN-7001"
    assert any("sheets/io.kicad_sch" in issue["message"] for issue in env["issues"])


def test_evidence_names_the_stacked_rows_only_for_a_design_with_stacked_pins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Change c0123: ``netlist``, ``parity`` and ``build`` answer for a design with a pin bonded to several
    pads with the rows ``H-K-SCH-STACKED`` and ``H-K-SCH-STACKED-OPEN``; a design of one pad per pin answers
    with the evidence it had."""
    from _schbuild import built_stacked, built_units

    rows = {"H-K-SCH-STACKED", "H-K-SCH-STACKED-OPEN"}
    _no_subprocess(monkeypatch)
    for name, output, expected in (("stacked", built_stacked(), True), ("units", built_units(), False)):
        assert (
            rows <= set(output.evidence.hypotheses)
            if expected
            else not rows & set(output.evidence.hypotheses)
        )
        root = write_files(output, tmp_path / name)
        for command, extra in (("netlist", ("--source", "fenolite")), ("parity", ("--netlist", "own"))):
            code, env, _, _ = run(monkeypatch, tmp_path, command, str(root), *extra)
            assert code in (0, 5), env
            listed = set(env["evidence"]["hypotheses"])
            assert (rows <= listed) if expected else not (rows & listed), (name, command, sorted(listed))
            assert "H-K-NETLIST-OWN" in listed
