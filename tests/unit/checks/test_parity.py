# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The parity comparison (capability verification-loop, "Parity comparison" and "Parity issue codes";
change c0072). The project is the blink as ``build`` writes it, whose board and schematic agree; every
case changes one thing of the board by token edit, or one thing of the schematic side."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import _parityedit as edits
import pytest
from _board_only import add_h1
from _buildhelp import blink, build

from fenolite.backends.base import SchematicSide, SideComponent
from fenolite.backends.kicad import parity_inputs
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks import parity
from fenolite.checks.parity import ParityFinding, ParityReport, compare
from fenolite.core.errors import Issue
from fenolite.core.evidence import Level

CODE = re.compile(r'"(parity\.[a-z-]+)"')


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> tuple[SchematicSide, str]:
    """The schematic side and the board text of the built blink."""
    folder = tmp_path_factory.mktemp("parity")
    files = build(blink(), 10).files
    (folder / "blink.kicad_sch").write_bytes(files["blink.kicad_sch"])
    return parity_inputs.schematic_side(folder / "blink.kicad_sch"), files["blink.kicad_pcb"].decode("utf-8")


def run(side: SchematicSide, text: str) -> ParityReport:
    issues: list[Issue] = []
    report = compare(side, read_board(text, file="blink.kicad_pcb"), issues=issues)
    assert [(i.code, i.severity, i.where) for i in issues] == [
        (f.code, f.severity, f.key) for f in report.findings
    ]
    assert all(f.severity in parity.PARITY_ISSUE_CODES[f.code] for f in report.findings)
    assert list(report.findings) == sorted(report.findings, key=lambda f: (f.code, f.key, f.field))
    assert all(i.message for i in issues)
    return report


def keyed(report: ParityReport, code: str) -> list[str]:
    return [f.key for f in report.findings if f.code == code]


def with_component(side: SchematicSide, ref: str, **changes: object) -> SchematicSide:
    components = dict(side.components)
    components[ref] = dataclasses.replace(components[ref], **changes)  # type: ignore[arg-type]
    return dataclasses.replace(side, components=components)


def with_nodes(side: SchematicSide, changes: dict[tuple[str, str], str | None]) -> SchematicSide:
    nodes = dict(side.nodes)
    for key, net in changes.items():
        if net is None:
            nodes.pop(key)
        else:
            nodes[key] = net
    return dataclasses.replace(side, nodes=nodes)


def test_agreeing_project(project: tuple[SchematicSide, str]) -> None:
    side, text = project
    report = run(side, text)
    assert report.findings == ()
    assert set(report.summary) == set(parity.SUMMARY_KEYS) and not any(report.summary.values())
    assert sorted(side.components) == ["D1", "R1", "U1"] and len(side.components["U1"].pins) == 32


def test_reference_on_one_side(project: tuple[SchematicSide, str]) -> None:
    side, text = project
    report = run(side, edits.rename(text, "R1", "R99"))
    assert keyed(report, "parity.missing-footprint") == ["R1"]
    assert keyed(report, "parity.extra-footprint") == ["R99"]
    assert report.summary["refs_one_side"] == 2 and len(report.findings) == 2


def test_pad_on_no_net(project: tuple[SchematicSide, str]) -> None:
    side, text = project
    report = run(side, edits.renet(text, "R1", "2", None))
    (found,) = report.findings
    assert found == ParityFinding("parity.net-conflict", "error", "R1-2", schematic="LED_A", board="")
    assert report.summary["connections_missing"] == 1 and report.summary["nets_split"] == 0


def test_pad_on_another_net_splits_the_net(project: tuple[SchematicSide, str]) -> None:
    side, text = project
    report = run(side, edits.renet(text, "R1", "2", "GND"))
    (found,) = report.findings
    assert (found.code, found.key, found.schematic, found.board) == (
        "parity.net-conflict",
        "R1-2",
        "LED_A",
        "GND",
    )
    assert report.summary["connections_missing"] == 0 and report.summary["nets_split"] == 1


def test_pin_without_a_pad(project: tuple[SchematicSide, str]) -> None:
    side, text = project
    pins = side.components["U1"].pins
    more = with_component(side, "U1", pins=pins | {"33", "34"})
    more = with_nodes(more, {("U1", "33"): "VIN", ("U1", "34"): "unconnected-(U1-Pad34)"})
    report = run(more, text)
    assert [(f.code, f.severity, f.key, f.schematic) for f in report.findings] == [
        ("parity.pin-without-pad", "error", "U1-33", "VIN"),  # U1-9 is on VIN too: it can never be routed
        ("parity.pin-without-pad", "warning", "U1-34", "unconnected-(U1-Pad34)"),
    ]
    assert report.summary["parity.pin-without-pad"] == 2
    # a pin without a number names no pad at all
    assert run(with_component(side, "U1", pins=pins | {""}), text).findings == ()


def test_pad_without_a_pin(project: tuple[SchematicSide, str]) -> None:
    side, text = project
    less = with_component(side, "U1", pins=side.components["U1"].pins - {"5"})
    less = with_nodes(less, {("U1", "5"): None})
    # the pad still carries its net: the schematic gives it none
    (conflict,) = run(less, text).findings
    assert (conflict.code, conflict.key, conflict.schematic) == ("parity.net-conflict", "U1-5", "")
    # on no net, it is a pad that no pin names
    (alone,) = run(less, edits.renet(text, "U1", "5", None)).findings
    assert alone == ParityFinding("parity.pad-without-pin", "info", "U1-5")


def test_board_only_footprint(project: tuple[SchematicSide, str]) -> None:
    side, text = project
    with_hole = add_h1()(text)
    assert keyed(run(side, with_hole), "parity.extra-footprint") == ["H1"]
    report = run(side, edits.board_only(with_hole, "H1"))
    assert not [f for f in report.findings if f.key.startswith("H1")] and report.findings == ()
    # a footprint marked so still stands for the component of its reference
    assert run(side, edits.board_only(text, "R1")).findings == ()


def test_duplicated_reference(project: tuple[SchematicSide, str]) -> None:
    side, text = project
    report = run(side, edits.duplicate(text, "R1", "D1"))
    assert keyed(report, "parity.duplicate-footprints") == ["D1"]
    assert keyed(report, "parity.missing-footprint") == ["R1"]
    # D1 comes first on the board, so the component D1 is compared with its own footprint
    assert len(report.findings) == 2
    # the other way round, the first footprint of the reference is the one that took it
    other = run(side, edits.duplicate(text, "D1", "R1"))
    assert keyed(other, "parity.duplicate-footprints") == ["R1"] and keyed(
        other, "parity.missing-footprint"
    ) == ["D1"]
    assert sorted(f.field for f in other.findings if f.code == "parity.footprint-mismatch") == [
        "footprint",
        "value",
    ]
    assert keyed(other, "parity.net-conflict") == ["R1-1"]
    # one finding for each further footprint
    three = run(
        side, edits.copy(edits.copy(text, "R1", "R1", "f3a0c0de-0072-4000-8000-000000000001"), "R1", "R1")
    )
    assert keyed(three, "parity.duplicate-footprints") == ["R1", "R1"]


def test_value_footprint_and_attributes(project: tuple[SchematicSide, str]) -> None:
    side, text = project
    report = run(side, edits.relib(edits.revalue(text, "R1"), "R1"))
    assert [(f.code, f.severity, f.key, f.field) for f in report.findings] == [
        ("parity.footprint-mismatch", "warning", "R1", "footprint"),
        ("parity.footprint-mismatch", "warning", "R1", "value"),
    ]
    assert report.findings[0].board == edits.NEW_LIB_ID and report.findings[1].board == edits.NEW_VALUE
    flagged = run(with_component(side, "R1", attributes=frozenset({"dnp"})), text)
    (found,) = flagged.findings
    assert (found.code, found.field, found.schematic, found.board) == (
        "parity.footprint-mismatch",
        "attributes",
        "dnp",
        "",
    )


def test_spellings_read_as_one(project: tuple[SchematicSide, str]) -> None:
    side, text = project
    spelled = with_nodes(side, {("R1", "2"): "LED{slash}A", ("D1", "2"): "LED{slash}A"})
    assert keyed(run(dataclasses.replace(spelled, fold=()), text), "parity.net-conflict") == ["D1-2", "R1-2"]
    assert run(dataclasses.replace(spelled, fold=(("{slash}", "_"),)), text).findings == ()
    assert parity_inputs.FOLD == (("{slash}", "/"),)


def test_further_pads_of_a_pin_on_no_net(project: tuple[SchematicSide, str]) -> None:
    side, text = project
    name = side.nodes[("U1", "5")]
    assert name.startswith(side.single_prefix) and side.single_prefix == "unconnected-("
    suffixed = text.replace(f'"{name}"', f'"{name}_1"')
    assert suffixed != text
    assert run(side, suffixed).findings == ()
    assert keyed(run(dataclasses.replace(side, single_prefix=""), suffixed), "parity.net-conflict") == [
        "U1-5"
    ]
    # only a number is such a suffix, and only on the net of one pin
    assert keyed(run(side, text.replace(f'"{name}"', f'"{name}_x"')), "parity.net-conflict") == ["U1-5"]
    assert keyed(run(side, text.replace('"LED_A"', '"LED_A_1"')), "parity.net-conflict") == ["D1-2", "R1-2"]


def test_references_that_are_no_components(project: tuple[SchematicSide, str]) -> None:
    side, text = project
    components = {**side.components, "#PWR01": SideComponent("VIN"), "#FLG01": SideComponent("PWR_FLAG")}
    assert run(dataclasses.replace(side, components=components), text).findings == ()


def test_oracle_entries() -> None:
    assert dict(parity.KICAD_TYPES) == {
        "parity.missing-footprint": "missing_footprint",
        "parity.extra-footprint": "extra_footprint",
        "parity.duplicate-footprints": "duplicate_footprints",
        "parity.footprint-mismatch": "footprint_symbol_mismatch",
        "parity.net-conflict": "net_conflict",
        "parity.pin-without-pad": "net_conflict",
    }
    assert parity.oracle_entry(ParityFinding("parity.net-conflict", "error", "R1-2")) == (
        "net_conflict",
        "R1-2",
    )
    # KiCad names the footprint, not the pin
    assert parity.oracle_entry(ParityFinding("parity.pin-without-pad", "error", "U1-33")) == (
        "net_conflict",
        "U1",
    )
    assert parity.oracle_entry(ParityFinding("parity.pad-without-pin", "info", "U1-5")) is None
    assert parity.oracle_entry(ParityFinding("parity.missing-footprint", "error", "R1")) == (
        "missing_footprint",
        "R1",
    )


def test_evidence_and_purity() -> None:
    assert parity.EVIDENCE.level is Level.INFERRED and parity.EVIDENCE.hypotheses == ("H-K-PARITY-OWN",)
    source = Path(parity.__file__).read_text(encoding="utf-8")
    assert "backends.kicad" not in source and "import os" not in source and "open(" not in source
    with pytest.raises(ValueError, match="board"):
        compare(SchematicSide({}, {}), dataclasses.replace(read_board(MINIMAL), board=None))


MINIMAL = '(kicad_pcb (version 20241229) (generator "fenolite") (layers (0 "F.Cu" signal)))'


def test_closed_set() -> None:
    assert dict(parity.PARITY_ISSUE_CODES) == {
        "parity.missing-footprint": ("error",),
        "parity.extra-footprint": ("error",),
        "parity.duplicate-footprints": ("error",),
        "parity.net-conflict": ("error",),
        "parity.pin-without-pad": ("error", "warning"),
        "parity.footprint-mismatch": ("warning",),
        "parity.oracle-differs": ("warning",),
        "parity.pad-without-pin": ("info",),
    }
    produced: set[str] = set()
    here = Path(__file__)
    for path in (here, here.with_name("test_parity_stage.py")):
        produced |= set(CODE.findall(path.read_text(encoding="utf-8")))
    assert produced == set(parity.PARITY_ISSUE_CODES)
