# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored native scalar/power alias controls, with complete pin partitions (c0336)."""

from __future__ import annotations

import _drawn
import _drawn_corpus
import _erc
import _probes
import pytest

from fenolite.backends.kicad import drawn, sch
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.ids import derived_id
from fenolite.model.schematic import NetLabel, SchematicSheet

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize(
    ("kind", "equal", "present"),
    [("local", True, True), ("local", False, True), ("local", True, False), ("global", True, True)],
)
def test_native_power_alias_preserves_complete_partition(kind, equal: bool, present: bool) -> None:
    output = _drawn.build("flat", _probes.major())
    assert output.files and output.design.circuit
    file = _drawn.root_name(output)
    value = _drawn.drawn("flat")
    index = next(i for i, symbol in enumerate(value.sheets[0].symbols) if symbol.part == "U1")
    anchor = next(
        pin.at for pin in _drawn.pins(value, "flat")[("root", "symbol", index)] if pin.number == "17"
    )
    label = NetLabel(
        id=derived_id("lbl", "authored-power", "label"),
        kind=kind,
        name="SUPPLY_A" if equal else "SUPPLY_B",
        position=anchor,
        shape="input" if kind == "global" else "",
    )
    shell = SchematicSheet(
        id=derived_id("sch", "authored-power", "shell"), name="power-alias", labels=(label,)
    )
    fragments = parse(sch.write_schematic(shell, target=_probes.major()).text)
    original = parse(output.files[file].decode())
    children = []
    for child in original.children:
        if isinstance(child, Node) and child.name in {
            "wire",
            "junction",
            "no_connect",
            "label",
            "global_label",
            "hierarchical_label",
        }:
            continue
        if isinstance(child, Node) and child.name == "symbol":
            properties = {prop.atoms()[0].value: prop for prop in child.nodes("property")}
            if properties["Reference"].atoms()[1].value.startswith("#"):
                if not present:
                    continue
                old = properties["Value"]
                new = old.with_children((old.children[0], Atom.string("SUPPLY_A"), *old.children[2:]))
                child = child.with_children(tuple(new if prop is old else prop for prop in child.children))
        children.append(child)
    children.extend(
        node
        for node in fragments.children
        if isinstance(node, Node) and node.name in {"label", "global_label"}
    )
    files = dict(output.files)
    files[file] = dumps(original.with_children(tuple(children))).encode()
    root = sch.read_schematic(files[file].decode(), file=file)
    _, own, issues = drawn.resolve_sheets(
        root, {}, circuit=output.design.circuit, name="flat", root_file=file
    )
    assert not issues
    refs = {
        component.properties["fenolite.path"]: component.ref for component in output.design.circuit.components
    }
    native = _erc.netlist(_probes.runner(), file, files)
    report = _drawn_corpus.partition_report(own, refs, native)
    assert any({("U1", "17"), ("R1", "2")} <= group for group in native.values()) is (equal and present)
    print(f"{_probes.runner().version()} {kind}/{equal}/{present}: {report}")
    assert report["equal"], report


def test_native_power_alias_does_not_reach_a_local_name_in_another_sheet() -> None:
    output = _drawn.build("hier", _probes.major())
    assert output.files and output.design.circuit
    file = _drawn.root_name(output)
    value = _drawn.drawn("hier")
    positions = _drawn.pins(value, "hier")
    files = dict(output.files)
    for path, data in tuple(files.items()):
        if not path.endswith(".kicad_sch"):
            continue
        key = "root" if path == file else "child"
        part, number = ("U1", "17") if key == "root" else ("R2", "1")
        sheet = next(sheet for sheet in value.sheets if sheet.key == key)
        index = next(i for i, symbol in enumerate(sheet.symbols) if symbol.part == part)
        anchor = next(pin.at for pin in positions[(key, "symbol", index)] if pin.number == number)
        label = NetLabel(id=derived_id("lbl", "power-scope", key), kind="local", name="GND", position=anchor)
        shell = SchematicSheet(id=derived_id("sch", "power-scope", key), name=key, labels=(label,))
        fragments = parse(sch.write_schematic(shell, target=_probes.major()).text)
        original = parse(data.decode())
        # Root retains its authored GND power; child has no power declaration.
        children = [
            child
            for child in original.children
            if not isinstance(child, Node)
            or child.name
            not in {"wire", "junction", "no_connect", "label", "global_label", "hierarchical_label"}
        ]
        children.extend(
            node for node in fragments.children if isinstance(node, Node) and node.name == "label"
        )
        files[path] = dumps(original.with_children(tuple(children))).encode()
    root = sch.read_schematic(files[file].decode(), file=file)
    children = {
        path: sch.read_schematic(data.decode(), file=path)
        for path, data in files.items()
        if path.endswith(".kicad_sch") and path != file
    }
    _, own, _issues = drawn.resolve_sheets(
        root, children, circuit=output.design.circuit, name="hier", root_file=file
    )
    refs = {
        component.properties["fenolite.path"]: component.ref for component in output.design.circuit.components
    }
    native = _erc.netlist(_probes.runner(), file, files)
    assert not any({("U1", "17"), ("R2", "1")} <= group for group in native.values())
    report = _drawn_corpus.partition_report(own, refs, native)
    print(f"{_probes.runner().version()} other-sheet: {report}")
    assert report["equal"], report
