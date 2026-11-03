# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Repeated authored sheets preserve complete partitions and canonical names (c0276/6.6)."""

import shutil
from collections import Counter
from dataclasses import replace
from pathlib import Path

import _drawn
import pytest
from _buildhelp import LIBS, project

from fenolite.api import run
from fenolite.backends.altium import drawn
from fenolite.backends.altium.read import sch
from fenolite.model.circuit import PinRef


@pytest.fixture
def source(tmp_path: Path):
    original = _drawn.folder("repeat")
    before = {p.relative_to(original): p.read_bytes() for p in original.rglob("*") if p.is_file()}
    copied = tmp_path / "source"
    shutil.copytree(original, copied, ignore=shutil.ignore_patterns("design.lock", "__pycache__"))
    project(copied, {"Mini": str(LIBS / "Mini_v9.pretty")}, {"Mini": str(LIBS / "Mini_v9.kicad_sym")})
    yield copied / "design.py"
    assert {p.relative_to(original): p.read_bytes() for p in original.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("form", ("binary", "ascii"))
def test_repeat_keeps_all_pins_and_exact_canonical_local_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    form: str,
    source: Path,
) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    out = tmp_path / "out"
    result = run(
        "build",
        str(source),
        "--target",
        "altium",
        "--altium-format",
        form,
        "--out",
        str(out),
        "--confirm",
        seed=1,
        timestamp="2026-11-03T00:00:00Z",
    )
    assert result.exit_code == 0, (result.error, result.envelope)
    files = {p.name: p.read_bytes() for p in out.glob("*.SchDoc")}
    native, coverage = drawn._read_native(files)
    refs = {value: native.refs[key] for key, value in native.component_ids.items()}
    groups = {frozenset((refs[p.component], p.designator) for p in net.pins) for net in native.netlist.nets}
    # The native reader lists connected nets; unconnected covered pins remain singleton groups.
    all_pins = {(ref, p) for ref, _, pins in coverage.units for p in pins}
    connected = set().union(*groups)
    groups.update(frozenset({pin}) for pin in all_pins - connected)
    assert groups == {
        frozenset({("R1", "1"), ("R3", "1")}),
        frozenset({("R1", "2"), ("R2", "1")}),
        frozenset({("R3", "2"), ("R4", "1")}),
        frozenset({("R2", "2")}),
        frozenset({("R4", "2")}),
    }
    assert {(ref, p) for ref, _, pins in coverage.units for p in pins} == {
        (ref, pin) for ref in ("R1", "R2", "R3", "R4") for pin in ("1", "2")
    }
    labels = Counter(
        label.text for data in files.values() for label in sch.read_schematic(data).of_type(sch.NetLabel)
    )
    assert labels == Counter({"FB0": 2, "FB1": 2})


@pytest.fixture
def binding_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: Path):
    """Capture only authored, unqualified plans and their exact final circuit."""
    captured = {}
    original_global = drawn._global_local_names
    original_lower = drawn.lower_drawn

    def remember_lower(value, design, planned, **kwargs):
        captured["design"] = design
        return original_lower(value, design, planned, **kwargs)

    def remember_global(sheets, issues, **kwargs):
        captured["sheets"] = sheets
        return original_global(sheets, issues, **kwargs)

    monkeypatch.setattr(drawn, "lower_drawn", remember_lower)
    monkeypatch.setattr(drawn, "_global_local_names", remember_global)
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    result = run(
        "build",
        str(source),
        "--target",
        "altium",
        "--out",
        str(tmp_path / "out"),
        "--confirm",
        seed=1,
        timestamp="2026-11-03T00:00:00Z",
    )
    assert result.exit_code == 0
    return captured["sheets"], captured["design"]


def test_complete_carrier_binds_only_repeated_files(binding_inputs):
    sheets, design = binding_inputs
    repeated = frozenset(sheet.file for sheet in sheets[1:])
    assert drawn._canonical_local_bindings(sheets, design, repeated) == {
        (sheets[1].file, "FB"): "FB0",
        (sheets[2].file, "FB"): "FB1",
    }
    assert drawn._canonical_local_bindings(sheets, design, frozenset()) == {}


@pytest.mark.parametrize(
    "defect",
    (
        "missing-pin",
        "partial-cross-sheet-group",
        "unmatched-group",
        "ambiguous-group",
        "duplicate-casefold-name",
        "global-collision",
        "power-collision",
        "duplicate-reference",
        "ordinary-sheet",
    ),
)
def test_incomplete_or_ambiguous_carrier_never_picks_first(binding_inputs, defect):
    sheets, design = binding_inputs
    sheets = list(sheets)
    repeated = frozenset(sheet.file for sheet in sheets[1:])
    nets = list(design.circuit.nets)
    target = next(index for index, net in enumerate(nets) if net.name == "FB0")
    if defect == "missing-pin":
        nets[target] = replace(nets[target], members=nets[target].members[:-1])
    elif defect == "partial-cross-sheet-group":
        other = next(component for component in design.circuit.components if component.ref == "R4")
        nets[target] = replace(nets[target], members=(*nets[target].members, PinRef(other.id, "2")))
    elif defect == "unmatched-group":
        nets[target] = replace(nets[target], members=())
    elif defect == "ambiguous-group":
        nets.append(replace(nets[target], id="net_authored_ambiguous", name="Other"))
    elif defect == "duplicate-casefold-name":
        other = next(index for index, net in enumerate(nets) if net.name == "FB1")
        nets[other] = replace(nets[other], name="fb0")
    elif defect in {"global-collision", "power-collision"}:
        record = (
            ("RECORD", "25" if defect == "global-collision" else "17"),
            ("TEXT", "fB0"),
            ("NAME", "fB0"),
        )
        root = sheets[0]
        sheets[0] = replace(root, plan=replace(root.plan, drawn_records=(*root.plan.drawn_records, record)))
    elif defect == "duplicate-reference":
        components = list(design.circuit.components)
        components[1] = replace(components[1], ref=components[0].ref)
        design = replace(design, circuit=replace(design.circuit, components=tuple(components)))
    elif defect == "ordinary-sheet":
        repeated = frozenset()
    design = replace(design, circuit=replace(design.circuit, nets=tuple(nets)))
    bindings = drawn._canonical_local_bindings(sheets, design, repeated)
    assert (sheets[1].file, "FB") not in bindings


@pytest.mark.parametrize("defect", ("missing-pin", "ambiguous-group", "duplicate-casefold-name"))
def test_rejected_binding_retains_complete_native_partition(binding_inputs, defect):
    sheets, design = binding_inputs
    nets = list(design.circuit.nets)
    target = next(index for index, net in enumerate(nets) if net.name == "FB0")
    if defect == "missing-pin":
        nets[target] = replace(nets[target], members=nets[target].members[:-1])
    elif defect == "ambiguous-group":
        nets.append(replace(nets[target], id="net_authored_ambiguous", name="Other"))
    else:
        other = next(index for index, net in enumerate(nets) if net.name == "FB1")
        nets[other] = replace(nets[other], name="fb0")
    design = replace(design, circuit=replace(design.circuit, nets=tuple(nets)))
    bindings = drawn._canonical_local_bindings(sheets, design, frozenset(s.file for s in sheets[1:]))
    issues = []
    rewritten = drawn._global_local_names(sheets, issues, bindings=bindings)
    files = {sheet.file: drawn.schdoc.write_schdoc(sheet.plan) for sheet in rewritten}
    native, coverage = drawn._read_native(files)
    refs = {value: native.refs[key] for key, value in native.component_ids.items()}
    groups = {frozenset((refs[p.component], p.designator) for p in net.pins) for net in native.netlist.nets}
    all_pins = {(ref, pin) for ref, _, numbers in coverage.units for pin in numbers}
    groups.update(frozenset({pin}) for pin in all_pins - set().union(*groups))
    assert len(all_pins) == 8
    assert groups == {
        frozenset({("R1", "1"), ("R3", "1")}),
        frozenset({("R1", "2"), ("R2", "1")}),
        frozenset({("R3", "2"), ("R4", "1")}),
        frozenset({("R2", "2")}),
        frozenset({("R4", "2")}),
    }
    assert any(
        "__local_" in issue.message and "drawn label text is changed" in issue.message for issue in issues
    )


def test_ordinary_sheet_bytes_keep_existing_path(binding_inputs):
    sheets, design = binding_inputs
    bindings = drawn._canonical_local_bindings(sheets, design, frozenset())
    default = drawn._global_local_names(sheets, [])
    ordinary = drawn._global_local_names(sheets, [], bindings=bindings)
    assert {sheet.file: drawn.schdoc.write_schdoc(sheet.plan) for sheet in ordinary} == {
        sheet.file: drawn.schdoc.write_schdoc(sheet.plan) for sheet in default
    }
