# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The netlist oracle on ``kicad-cli`` (capability kicad-oracle, "Netlist oracle from IPC-D-356";
``H-K-NET-IPC``): the export's partition equals the board's on the authored built project, and two nets
whose names share their last 14 characters become coverage, never a short.

Since change c0063 also the schematic's netlist ("Schematic netlist through the package runner"): the
pairs of ``fenolite check`` on projects that ``build`` wrote, and the difference a hidden power pin makes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import _gencases as gen
import _netlistcases as cases
import pytest
from _boards import FIXTURE
from _checkrun import check, cli_path, stage
from _netcases import COLLIDING, authored, board, collision, netlist
from _probes import run, runner
from _projects import tree_snapshot
from _schbuild import write_files

from fenolite.backends.base import PadAssignment, PadNetList
from fenolite.backends.kicad import schlayout
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.projectset import project_set
from fenolite.checks.assignment_compare import board_netlist, compare

pytestmark = pytest.mark.needs_kicad


def test_partition() -> None:
    assert run("netlist-partition") == "equal"
    outcome = netlist(authored())
    assert outcome.netlist is not None and outcome.netlist.uncovered == ()
    listed, unnumbered = board_netlist(board(authored()))
    result = compare(listed, outcome.netlist)
    assert result.differences == () and result.common == len({a.element for a in listed.assignments})
    assert unnumbered == 0 and outcome.evidence.oracle.startswith("kicad-cli ")


def test_collision() -> None:
    assert run("netlist-label-collision") in {"equal", "different"}
    outcome = netlist(collision())
    assert outcome.netlist is not None
    ambiguous = {u.element for u in outcome.netlist.uncovered if u.reason == "net-label-ambiguous"}
    assert ambiguous == set(COLLIDING)
    listed, _ = board_netlist(board(collision()))
    result = compare(listed, outcome.netlist)
    assert result.differences == ()
    assert {u.element for u in result.only_a if u.reason == "net-label-ambiguous"} == set(COLLIDING)


# -- the schematic's netlist (c0063)


def _pairs(env: dict[str, Any]) -> list[tuple[str, str, int]]:
    found = stage(env, "netlist.assignment_compare")["summary"]["pairs"]
    return [(p["a"], p["b"], p["differences"]) for p in found]


@pytest.mark.parametrize("name", ["blink", "units"])
def test_built_projects_agree_in_every_pair(name: str, tmp_path: Path) -> None:
    """Built input: the model is the hub, and KiCad's netlist of the generated sheet agrees with it."""
    folder = write_files(cases.output(name), tmp_path / name)
    before = tree_snapshot(folder)
    _, env, _, err = check(folder, "--stages", "netlist.assignment_compare")
    assert env, err
    assert _pairs(env) == [("model", "board", 0), ("model", "schematic", 0), ("board", "export", 0)]
    compared = stage(env, "netlist.assignment_compare")
    assert compared["status"] == "ok", env["issues"]
    assert all(p["common"] > 0 for p in compared["summary"]["pairs"])
    assert not [i for i in env["issues"] if i["severity"] == "error"]
    assert tree_snapshot(folder) == before


@pytest.mark.parametrize("name", ["blink", "units"])
def test_native_input_compares_the_schematic_with_the_board(name: str, tmp_path: Path) -> None:
    """The same files without ``.fenolite/``: the board is the hub."""
    folder = tmp_path / name
    for rel, data in cases.project_files(cases.output(name)).items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_bytes(data)
    _, env, _, err = check(folder, "--stages", "netlist.assignment_compare")
    assert env, err
    assert env["result"]["project"]["built"] is False
    assert _pairs(env) == [("schematic", "board", 0), ("board", "export", 0)]


def _sheet_netlist(tmp_path: Path, text: str) -> PadNetList:
    """KiCad's netlist of a hand-written sheet, through ``KicadOracle.schematic_netlist``."""
    root = tmp_path / "probe"
    root.mkdir(parents=True)
    shutil.copyfile(FIXTURE, root / "probe.kicad_pcb")
    (root / "probe.kicad_sch").write_text(text, encoding="utf-8", newline="\n")
    before = tree_snapshot(root)
    project = project_set(root / "probe.kicad_pcb")  # the copy set holds the schematic (c0062)
    outcome = KicadOracle(runner()).schematic_netlist(project)
    assert outcome.netlist is not None, outcome.message
    assert outcome.netlist.source == "schematic" and outcome.evidence.oracle.startswith("kicad-cli ")
    assert tree_snapshot(root) == before
    return outcome.netlist


def _supply_sheet(hidden: bool) -> str:
    """c0061's power probe: two power-input pins named ``VSS``, labelled ``GND`` and ``OTHER``."""
    pins = [("power_in", "1", "VSS"), ("power_in", "2", "VSS")]
    points = gen.probe_points(2)
    inst = gen.Inst("Probe:Supply", "X1", gen.POWER_AT, ("1", "2"))
    labels = [
        ("GND", schlayout.pin_point(gen.POWER_AT, points[0])),
        ("OTHER", schlayout.pin_point(gen.POWER_AT, points[1])),
    ]
    symbol = gen.probe_symbol("Supply", pins, hidden=hidden)
    return gen.hand_sheet(gen.major(), [symbol], [inst], labels)


def test_hidden_power_pins_differ_from_the_model(tmp_path: Path) -> None:
    """A symbol embedded with its power pins hidden joins what the circuit keeps apart: the pair
    (``model``, ``schematic``) names the pin. Embedded shown, as ``build`` embeds it, the pair agrees."""
    model = PadNetList("model", (PadAssignment("X1-1", "GND"), PadAssignment("X1-2", "OTHER")))
    shown = compare(model, _sheet_netlist(tmp_path / "shown", _supply_sheet(False)))
    assert shown.differences == () and shown.common == 2
    hidden = compare(model, _sheet_netlist(tmp_path / "hidden", _supply_sheet(True)))
    assert (hidden.a, hidden.b) == ("model", "schematic")
    assert {d.element for d in hidden.differences} & {"X1-1", "X1-2"}, hidden


def test_unloadable_schematic_is_an_outcome(tmp_path: Path) -> None:
    root = tmp_path / "broken"
    root.mkdir()
    shutil.copyfile(FIXTURE, root / "probe.kicad_pcb")
    (root / "probe.kicad_sch").write_text("(kicad_sch (version 1)", encoding="utf-8")
    project = project_set(root / "probe.kicad_pcb")  # the copy set holds the schematic (c0062)
    outcome = KicadOracle(runner()).schematic_netlist(project)
    assert outcome.netlist is None and outcome.message and str(tmp_path) not in outcome.message


# -- the netlist command (cli-contract, "Netlist command", scenario "Both sources agree")


def _netlist_command(folder: Path, *args: str) -> dict[str, Any]:
    command = [sys.executable, "-m", "fenolite", "netlist", str(folder), "--kicad-cli", cli_path(), *args]
    done = subprocess.run(
        [*command, "--json"], cwd=folder, capture_output=True, text=True, timeout=600, check=False
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@pytest.mark.parametrize("name", ["blink", "units"])
def test_command_sources_agree(name: str, tmp_path: Path) -> None:
    folder = write_files(cases.output(name), tmp_path / name)
    before = tree_snapshot(folder)
    theirs = _netlist_command(folder)
    ours = _netlist_command(folder, "--source", "fenolite")
    assert (theirs["result"]["source"], ours["result"]["source"]) == ("kicad", "fenolite")
    assert theirs["evidence"]["oracle"].startswith("kicad-cli ") and ours["evidence"]["oracle"] is None

    def nets(env: dict[str, Any]) -> list[dict[str, Any]]:
        return [{k: v for k, v in net.items() if k != "class"} for net in env["result"]["nets"]]

    assert nets(ours) == nets(theirs)
    assert ours["result"]["counts"] == theirs["result"]["counts"]
    assert ours["result"]["components"] == theirs["result"]["components"]
    assert str(tmp_path) not in json.dumps(theirs["result"]) and tree_snapshot(folder) == before
