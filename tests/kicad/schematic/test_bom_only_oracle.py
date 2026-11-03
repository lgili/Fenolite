# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original authored purchasing accessory: native BOM and every electrical pin survive (c0334)."""

from pathlib import Path

import _drawn
import _erc
import _probes
import pytest

from fenolite.api import run
from fenolite.api.sides import read_side
from fenolite.backends.kicad import bom, sch
from fenolite.backends.kicad.cli import BOM
from fenolite.backends.kicad.sexpr import dumps
from fenolite.exports.bom import parts_from_model

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("dnp", [False, True])
@pytest.mark.parametrize("fixture", ["flat", "repeat"])
def test_native_bom_only_roundtrip_keeps_bill_without_adding_electrical_pins(
    tmp_path: Path, dnp: bool, fixture: str
) -> None:
    output = _drawn.build(fixture, _probes.major())
    assert output.files
    name = _drawn.root_name(output)
    files = dict(output.files)
    original_pins = {pin for group in _erc.netlist(_probes.runner(), name, files).values() for pin in group}
    accessory_file = "sheets/channel.kicad_sch" if fixture == "repeat" else name
    root = sch.read_schematic(files[accessory_file].decode(), file=accessory_file)
    files[accessory_file] = dumps(_drawn.bom_only_instance(root, _probes.major(), dnp=dnp)).encode()
    source = tmp_path / "original"
    for relative, data in files.items():
        if relative.startswith(".fenolite/"):
            continue
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    project = source / Path(name).with_suffix(".kicad_pro")
    args = ["import", str(project), "--to", "python", "--out", "code"]
    planned = run(*args, "--dry-run", cwd=tmp_path)
    assert planned.exit_code == 0, (planned.error, planned.envelope)
    confirmed = run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=tmp_path)
    assert confirmed.exit_code == 0, confirmed.error
    rebuilt = run("build", "code/design.py", "--out", "rebuilt", "--confirm", cwd=tmp_path)
    assert rebuilt.exit_code == 0, (rebuilt.error, rebuilt.envelope)
    native_rows = []
    native_partitions = []
    for folder in (source, tmp_path / "rebuilt"):
        schematic = folder / name
        held = {
            p.relative_to(folder).as_posix(): p.read_bytes()
            for p in folder.rglob("*")
            if p.is_file() and not p.relative_to(folder).as_posix().startswith(".fenolite/")
        }
        native_partitions.append(_erc.netlist(_probes.runner(), name, held))
        exported = _probes.runner().export_bom(
            schematic, fields=bom.BASE_FIELDS, files={p.name: p for p in folder.iterdir()}
        )
        assert exported.returncode == 0, exported.stderr
        native_rows.append(bom.read_bom_csv(exported.outputs[BOM].decode(), fields=bom.BASE_FIELDS))
    assert native_rows[0] == native_rows[1]
    first = {frozenset(group) for group in native_partitions[0].values()}
    second = {frozenset(group) for group in native_partitions[1].values()}
    assert first == second
    assert {pin for group in first for pin in group} == original_pins
    assert not any(ref in {"M1", "M2"} for group in first for ref, _ in group)
    model = read_side(tmp_path / "rebuilt" / ".fenolite").design
    assert model.board is not None
    expected_refs = {"M1", "M2"} if fixture == "repeat" else {"M1"}
    assert {component.ref for component in model.circuit.components if component.bom_only} == expected_refs
    schematic_model = read_side(source / name).design
    assert {
        component.ref for component in schematic_model.circuit.components if component.bom_only
    } == expected_refs
    for ref in expected_refs:
        accessory = next(component for component in model.circuit.components if component.ref == ref)
        assert accessory.bom_only and accessory.dnp is dnp and accessory.pins == ()
        assert not any(footprint.component_id == accessory.id for footprint in model.board.footprints)
        part = next(part for part in parts_from_model(model) if part.ref == ref)
        native = next(part for part in native_rows[0] if part.ref == ref)
        assert (part.value, part.footprint, part.dnp) == (native.value, native.footprint, native.dnp)
    print(
        f"{_probes.runner().version()} {fixture} dnp={dnp}: BOM={len(native_rows[0])}, "
        f"pins={len(original_pins)}, groups={len(first)}"
    )


@pytest.mark.parametrize("defect", ["", "on_board", "no_bom", "dnp"])
def test_native_pinless_multiunit_flag_inputs_remain_electrically_complete(
    tmp_path: Path, defect: str
) -> None:
    output = _drawn.build("flat", _probes.major())
    assert output.files
    file = _drawn.root_name(output)
    before = _erc.netlist(_probes.runner(), file, output.files)
    files = dict(output.files)
    original = sch.read_schematic(files[file].decode(), file=file)
    files[file] = dumps(_drawn.bom_only_multiunit(original, _probes.major(), defect=defect)).encode()
    for relative, data in files.items():
        if relative.startswith(".fenolite/"):
            continue
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    source = tmp_path / file
    native = _probes.runner().export_bom(
        source, fields=bom.BASE_FIELDS, files={p.name: p for p in tmp_path.iterdir()}
    )
    assert native.returncode == 0, native.stderr
    rows = bom.read_bom_csv(native.outputs[BOM].decode(), fields=bom.BASE_FIELDS)
    assert [row.ref for row in rows].count("M1") == 1
    after = _erc.netlist(_probes.runner(), file, files)
    assert {frozenset(group) for group in before.values()} == {frozenset(group) for group in after.values()}
    assert len({pin for group in after.values() for pin in group}) == 34
    read = sch.read_schematic(source)
    assert (
        next(
            definition for definition in read.lib_symbols if definition.name == "AuthoredAccessory"
        ).unit_count
        == 2
    )
    flags = sorted(
        (symbol.unit, symbol.in_bom, symbol.on_board, symbol.dnp)
        for symbol in read.symbols
        if symbol.ref == "M1"
    )
    assert flags == [(1, True, False, False), (2, defect != "no_bom", defect == "on_board", defect == "dnp")]
    print(
        f"{_probes.runner().version()} multiunit {defect}: "
        f"native accepts original flags={flags}; 34 complete pins"
    )
