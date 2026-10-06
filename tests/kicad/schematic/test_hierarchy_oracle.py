# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Projects built with module sheets and satellites, judged by the running ``kicad-cli`` (capability
kicad-oracle, "Hierarchical schematics pass the oracles"; hypothesis ``H-K-SCH-HIER-PATH``; change
c0070): no ERC violation, an empty parity list, Fenolite's own netlist equal to the export, and every
footprint path equal to the path the netlist gives its symbol."""

from __future__ import annotations

import _hiercases as hier
import _probes
import pytest
from _buildhelp import build
from _schbuild import built_nested, snap_design

from fenolite.backends.kicad import netlist as netlistmod

pytestmark = pytest.mark.needs_kicad
IO = "sheets/io.kicad_sch"


def test_acceptance() -> None:
    """The lens acceptance design: ``U1`` on the root, the modules ``power`` and ``io`` on their sheets."""
    output = hier.built_acceptance(hier.major())
    assert output.schematic is not None and list(output.schematic.children) == [IO, "sheets/power.kicad_sch"]
    flat = hier.built_acceptance(hier.major(), "grid")
    assert flat.schematic is not None and not flat.schematic.children
    assert hier.problems(output, flat) == [], "the sheets add no finding to those of the flat form"
    assert _probes.run("sch-hier-oracle-acceptance") == "equal"


def test_nested_design() -> None:
    """A module inside a module: the grandchild is named from its parent's folder, and is reached. The
    design marks every pin it leaves open, so ERC must report nothing at all."""
    output = built_nested(hier.major())
    assert hier.problems(output) == []
    _, export = hier.kicad_netlist(hier.project_files(output), hier.schematic_name(output))
    assert export.sheets["C1"][0] == "/power/ldo/" and export.sheets["R2"][0] == "/io/"


def test_paths() -> None:
    """``H-K-SCH-HIER-PATH``: the sheet path of the netlist joined with the symbol's uuid is the footprint
    path that the build wrote, for every component of the hierarchical builds."""
    checked = 0
    outputs = [hier.built_acceptance(hier.major()), built_nested(hier.major())]
    outputs += [hier.built_generated(index, hier.major()) for index in (1, 5, 12, 24)]
    for output in outputs:
        _, export = hier.kicad_netlist(hier.project_files(output), hier.schematic_name(output))
        ours, theirs = hier.footprint_paths(output), hier.netlist_paths(export)
        assert theirs and [ref for ref in theirs if ours[ref] not in theirs[ref]] == []
        checked += sum(1 for ref in theirs if ours[ref].count("/") > 1)
    print(f"footprint paths of {checked} components of child sheets equal the netlist's")
    assert checked >= 15


def test_satellite_design() -> None:
    """One resistor beside an IC pin, joined by a wire: the pair is one net under its one label."""
    output = build(snap_design(), hier.major())
    assert output.schematic is not None and output.schematic.satellites == 1
    # the snap design marks no pin, so ERC reports its open pins: the netlist is what is judged here
    theirs, export = hier.kicad_netlist(hier.project_files(output), hier.schematic_name(output))
    assert netlistmod.differences(hier.own(output), theirs) == ()
    assert export.nets["SIG"] == frozenset({("U1", "1"), ("R1", "1")})


def test_control_missing_child_file() -> None:
    """A ``Sheetfile`` that names no file: ERC has no finding about the sheet it dropped (at most about
    the labels that lost their other pin), and only the netlists tell that the parts are gone."""
    output = built_nested(hier.major())
    root = hier.schematic_name(output)
    files = hier.edited_file(output, root, f'"{IO}"', '"sheets/gone.kicad_sch"')
    kinds = hier.erc_kinds(files, root)
    print(f"ERC with the sheet io dropped: {kinds}")
    assert set(kinds) <= {"isolated_pin_label", "global_label_dangling", "pin_not_connected"}, kinds
    theirs, _ = hier.kicad_netlist(files, root)
    found = netlistmod.differences(hier.own(output), theirs)
    assert found and any("R2" in line for line in found), "the part of io is missing from the export"


def test_control_missing_wire() -> None:
    """A snap wire removed: the anchor pin is on no net, in ERC and in the netlist."""
    index = next(i for i in range(hier.COUNT) if hier.built_generated(i, hier.major()).schematic.satellites)  # type: ignore[union-attr]
    output = hier.built_generated(index, hier.major())
    assert output.schematic is not None
    sheets = {hier.schematic_name(output): output.schematic.sheet, **output.schematic.children}
    name = next(path for path, sheet in sheets.items() if sheet.wires)
    files = hier.without_first_wire(output, name)
    root = hier.schematic_name(output)
    kinds = hier.erc_kinds(files, root)
    theirs, _ = hier.kicad_netlist(files, root)
    assert kinds.get("pin_not_connected") or netlistmod.differences(hier.own(output), theirs), kinds


def test_generated() -> None:
    """The 25 generated designs with nested modules and resistors on IC pins."""
    for index in range(hier.COUNT):
        assert hier.generated_problems(index) == (), index
    sheets, satellites = hier.generated_stats()
    print(f"{hier.COUNT} designs: {sheets} child sheets, {satellites} satellites")
    assert sheets >= 10 and satellites >= 5
    assert _probes.run("sch-hier-oracle-generated") == "equal"
