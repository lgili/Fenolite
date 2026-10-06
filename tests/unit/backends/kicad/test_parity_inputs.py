# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic side of a KiCad project for the parity comparison (capability verification-loop, "Parity
comparison"; change c0072): components and pins from the sheets, nodes from the own netlist or from a
netlist export. No tool runs."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _schbuild import built_nested, write_files

from fenolite.backends.base import ParityInputs, SchematicSide
from fenolite.backends.kicad import parity_inputs, sch_netlist
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.netlist import read_netlist
from fenolite.backends.kicad.projectset import project_set
from fenolite.cli._examples import EXAMPLE_PARITY
from fenolite.core.evidence import Level

DATA = Path(__file__).resolve().parents[3] / "data" / "kicad"
AGREE = Path(EXAMPLE_PARITY)
SHEET = AGREE / "blink.kicad_sch"
FLAT = DATA / "schematic" / "flat.kicad_sch"
HIER = DATA / "schematic" / "hier"
EXPORT = (DATA / "netlist" / "export_10.net").read_text(encoding="utf-8")


def test_generated_schematic() -> None:
    side = parity_inputs.schematic_side(SHEET)
    assert isinstance(side, SchematicSide)
    assert sorted(side.components) == ["D1", "R1", "U1"]
    r1, u1 = side.components["R1"], side.components["U1"]
    assert (r1.value, r1.footprint, r1.pins, r1.attributes) == (
        "330",
        "Mini:Mini_R_0603",
        {"1", "2"},
        frozenset(),
    )
    assert u1.pins == {str(n) for n in range(1, 33)}
    assert side.nodes[("R1", "2")] == side.nodes[("D1", "2")] == "LED_A"
    assert side.nodes[("U1", "5")].startswith("unconnected-(U1-")
    assert len(side.nodes) == 2 + 2 + 32 and not any(ref.startswith("#") for ref, _ in side.nodes)
    assert side.fold == (("{slash}", "/"),) and side.single_prefix == "unconnected-("


def test_sheets_and_grammar() -> None:
    sheets = parity_inputs.read_sheets(SHEET)
    assert list(sheets) == ["blink.kicad_sch"] and parity_inputs.grammar_issues(sheets) == ()
    assert list(parity_inputs.read_sheets(HIER / "top.kicad_sch")) == ["top.kicad_sch", "child.kicad_sch"]
    wired = parity_inputs.read_sheets(FLAT)
    reasons = [i.message.split(":", 1)[0] for i in parity_inputs.grammar_issues(wired)]
    assert "wire" in reasons
    with pytest.raises(sch_netlist.NetlistUnsupportedError):
        parity_inputs.schematic_side(FLAT)
    # a sheet that no reference of the root names is outside the grammar (c0070)
    with pytest.raises(sch_netlist.NetlistUnsupportedError):
        parity_inputs.own_netlist({**sheets, "other.kicad_sch": sheets["blink.kicad_sch"]}, project="blink")


def test_tree_of_generated_sheets(tmp_path: Path) -> None:
    """A design with modules, as ``build`` writes it: the own netlist covers the tree (c0070)."""
    root = write_files(built_nested(), tmp_path / "nested")
    sheets = parity_inputs.read_sheets(root / "nested.kicad_sch")
    assert list(sheets) == [
        "nested.kicad_sch",
        "sheets/io.kicad_sch",
        "sheets/power.kicad_sch",
        "sheets/power.ldo.kicad_sch",
    ]
    assert parity_inputs.grammar_issues(sheets) == ()
    side = parity_inputs.schematic_side(root / "nested.kicad_sch")
    assert sorted(side.components) == ["C1", "R1", "R2", "U1"], "the components of every sheet"
    # one net that crosses three sheets: the root, power and power/ldo
    assert side.nodes[("U1", "2")] == side.nodes[("R1", "2")] == side.nodes[("C1", "1")] == "power{slash}FB"
    assert side.nodes[("R2", "2")] == side.nodes[("U1", "10")] == "GND"
    (root / "sheets" / "io.kicad_sch").unlink()
    missing = parity_inputs.read_sheets(root / "nested.kicad_sch")
    reasons = [i.message.split(":", 1)[0] for i in parity_inputs.grammar_issues(missing)]
    assert reasons == ["sheet"], "a missing child file is no key, and the grammar reports its reference"


def test_nodes_from_an_export() -> None:
    netlist = read_netlist(EXPORT, file="export.net")
    side = parity_inputs.schematic_side(FLAT, netlist=netlist)
    nodes = parity_inputs.netlist_nodes(netlist)
    assert nodes and set(side.nodes) <= set(nodes)
    assert all(ref in side.components for ref, _ in side.nodes)
    for ref, component in side.components.items():
        assert {pin for r, pin in side.nodes if r == ref} <= component.pins
    assert not any(ref.startswith("#") for ref in side.components)


def test_symbol_flags(tmp_path: Path) -> None:
    text = SHEET.read_text(encoding="utf-8")
    assert "(dnp no)" in text and "(in_bom yes)" in text
    edited = tmp_path / "blink.kicad_sch"
    edited.write_text(text.replace("(dnp no)", "(dnp yes)").replace("(in_bom yes)", "(in_bom no)"), "utf-8")
    side = parity_inputs.schematic_side(edited)
    assert {c.attributes for c in side.components.values()} == {frozenset({"dnp", "exclude_from_bom"})}


def test_assignment_nodes() -> None:
    from fenolite.backends.base import PadAssignment, PadNetList

    listed = PadNetList(
        "schematic",
        (PadAssignment("R1-2", "A"), PadAssignment("J-1-A-3", "B"), PadAssignment("X9-1", "C")),
    )
    found = parity_inputs.assignment_nodes(listed, {"R1", "J-1", "J-1-A"})
    # the longest reference wins, and an unknown reference ends at the last hyphen
    assert found == {("R1", "2"): "A", ("J-1-A", "3"): "B", ("X9", "1"): "C"}


def test_backend_gives_the_side(tmp_path: Path) -> None:
    root = Path(shutil.copytree(AGREE, tmp_path / "agree"))
    backend = KicadBackend()
    assert isinstance(backend, ParityInputs)
    outcome = backend.schematic_side(project_set(root / "blink.kicad_pcb"))
    assert outcome.side == parity_inputs.schematic_side(root / "blink.kicad_sch")
    assert outcome.evidence.level is Level.KICAD_VERIFIED
    assert outcome.evidence.hypotheses == sch_netlist.EVIDENCE.hypotheses
    # a schematic outside the grammar: no side without an oracle's nodes, and a side with them
    shutil.copyfile(FLAT, root / "blink.kicad_sch")
    project = project_set(root / "blink.kicad_pcb")
    refused = backend.schematic_side(project)
    assert refused.side is None and "wire" in refused.message
    from fenolite.backends.base import PadAssignment, PadNetList

    nodes = PadNetList("schematic", (PadAssignment("R1-1", "N1"),))
    given = backend.schematic_side(project, nodes=nodes)
    assert given.side is not None and given.side.nodes.get(("R1", "1"), "N1") == "N1"
