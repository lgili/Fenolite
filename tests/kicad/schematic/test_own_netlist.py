# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite's own netlist of a generated schematic equals the netlist ``kicad-cli`` exports (capability
kicad-oracle, "Own netlists equal kicad-cli's"; hypothesis ``H-K-NETLIST-OWN``; change c0063).

The set: the blink, the units design, every example under ``examples/`` that builds for the KiCad target
with the libraries of the repository, and the 25 designs of ``tests/_gendesigns.py``. Each is built for
the running major; components, net names, nodes and pin types are compared, net classes are not."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import _gendesigns
import _netlistcases as cases
import _probes
import pytest
from _projects import tree_snapshot
from _schbuild import write_files

from fenolite.backends.kicad.cli import NETLIST
from fenolite.backends.kicad.netlist import differences, read_netlist
from fenolite.backends.kicad.sch_netlist import own_netlist

pytestmark = pytest.mark.needs_kicad
MUST_BUILD = ("blink_2layer", "blink_routed", "board_40parts")
"""Examples on the authored mini library: the set is never empty by accident."""


@pytest.mark.parametrize("name", ["blink", "units"])
def test_blink_and_units(name: str) -> None:
    found = cases.own_differences(cases.output(name))
    outcome = _probes.run(f"netlist-own-{name}")
    print(f"netlist-own-{name}: {outcome} (pin types compared: {cases.pintype_outcome() == 'equal'})")
    assert found == (), f"{name}: {found[0]}"
    assert outcome == "equal"


def test_examples() -> None:
    built = {name: cases.example(name) for name in cases.example_scripts()}
    compared = sorted(name for name, output in built.items() if output is not None)
    print(f"examples compared: {compared}; not built for KiCad here: {sorted(set(built) - set(compared))}")
    assert set(MUST_BUILD) <= set(compared)
    for name in compared:
        output = built[name]
        assert output is not None
        found = cases.own_differences(output)
        assert found == (), f"examples/{name}: {found[0]}"


@pytest.mark.parametrize("index", range(_gendesigns.COUNT))
def test_generated(index: int) -> None:
    output = cases.generated(index)
    found = cases.own_differences(output)
    assert found == (), f"gen{index:02d}: {found[0]}"


def test_generated_probe() -> None:
    outcome = _probes.run("netlist-own-generated")
    print(f"netlist-own-generated: {outcome} ({_gendesigns.COUNT} designs, seed {_gendesigns.SEED})")
    assert outcome == "equal"


def test_export_runs_on_a_copy(tmp_path: Path) -> None:
    """The comparison of a folder on disk: the export is made on a copy and the folder is unchanged."""
    output = cases.output("blink")
    folder = write_files(output, tmp_path / "blink")
    before = tree_snapshot(folder)
    others = {
        path.name: path for path in folder.iterdir() if path.name not in ("blink.kicad_sch", ".fenolite")
    }
    run = _probes.runner().export_netlist(folder / "blink.kicad_sch", files=others)
    assert run.ok and NETLIST in run.outputs, run.stderr
    theirs = read_netlist(run.outputs[NETLIST].decode("utf-8"), file=NETLIST)
    assert output.schematic is not None
    ours = own_netlist(output.schematic.sheet, project="blink")
    assert differences(ours, theirs, pintypes=cases.pintype_outcome() == "equal") == ()
    assert len(theirs.nets) == 33 and tree_snapshot(folder) == before


def test_a_difference_is_named() -> None:
    """The control: a sheet that says something else is reported, with the net and the pin."""
    output = cases.output("blink")
    assert output.schematic is not None
    sheet = output.schematic.sheet
    labels = tuple(label for label in sheet.labels if label.name != "LED_A")
    ours = own_netlist(dataclasses.replace(sheet, labels=labels), project="blink")
    found = differences(ours, read_netlist(cases.export("blink")))
    assert "net LED_A: only in the second" in found
    assert "net unconnected-(R1-Pad2): only in the first" in found
