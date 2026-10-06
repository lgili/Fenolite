# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The reader of KiCad's netlist export and the comparison of two netlists (capability kicad-schematic,
"Netlist export reading"; change c0063). Hermetic: the two exports are authored for these tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from fenolite.backends.kicad import netlist
from fenolite.backends.kicad.netlist import (
    KicadNetlist,
    NetComponent,
    NetlistNet,
    NetNode,
    build_netlist,
    differences,
    read_netlist,
)
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.errors import FormatError

DATA = Path(__file__).resolve().parents[3] / "data" / "kicad" / "netlist"


def text(major: int) -> str:
    return (DATA / f"export_{major}.net").read_text(encoding="utf-8")


def read(major: int) -> KicadNetlist:
    return read_netlist(text(major), file=f"export_{major}.net")


def net(found: KicadNetlist, name: str) -> NetlistNet:
    return next(n for n in found.nets if n.name == name)


def moved(found: KicadNetlist, element: tuple[str, str], source: str, target: str) -> KicadNetlist:
    """``found`` with the node ``element`` taken from the net ``source`` and put on ``target``."""
    node = next(n for n in net(found, source).nodes if (n.ref, n.pin) == element)
    nets = []
    for item in found.nets:
        nodes = tuple(n for n in item.nodes if n is not node)
        nets.append(replace(item, nodes=(*nodes, node) if item.name == target else nodes))
    return build_netlist(found.components, nets)


def test_export_of_each_major() -> None:
    nine, ten = read(9), read(10)
    assert nine == ten
    assert [c.ref for c in ten.components] == ["D1", "R1", "U1"]
    assert net(ten, "GND").nodes == (NetNode("D1", "1", "passive"), NetNode("U1", "10", "power_in"))
    assert len(ten.nets) == 5
    assert net(ten, "unconnected-(U1-PA1-Pad2)").nodes == (NetNode("U1", "2", "bidirectional+no_connect"),)
    assert net(ten, "GND").netclass == "PWR"


def test_components_and_fields() -> None:
    led = read(10).components[0]
    assert (led.ref, led.value, led.footprint) == ("D1", "LED", "Mini:Mini_LED_THT_3mm")
    assert dict(led.properties) == {
        "fenolite.path": "D1",
        "Footprint": "Mini:Mini_LED_THT_3mm",
        "Datasheet": "",
    }


@pytest.mark.parametrize("major", [9, 10])
def test_no_date_and_no_path(major: int) -> None:
    source = text(major)
    assert "2026-01-01" in source and "/authored/blink" in source, "the fixture holds a date and a path"
    dumped = repr(read(major))
    for part in ("2026-01-01", "/authored", "Eeschema", "KIPRJMOD", "0c0063d1", "PA0_1", "Sheetfile"):
        assert part not in dumped, part


def swapped(node: Node, head: str) -> Node:
    """``node`` with its ``head`` children in the reverse order, after its other children."""
    kept = [c for c in node.children if not (isinstance(c, Node) and c.name == head)]
    return node.with_children([*kept, *reversed(node.nodes(head))])


def test_order_of_the_export_does_not_matter() -> None:
    root = parse(text(10))
    children: list[Node | Atom] = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "components":
            child = swapped(child, "comp")
        elif isinstance(child, Node) and child.name == "nets":
            nets = [swapped(n, "node") for n in child.nodes("net")]
            child = child.with_children(list(reversed(nets)))
        children.append(child)
    shuffled = dumps(root.with_children(children))
    assert shuffled.index('"U1"') < shuffled.index('"D1"')
    assert read_netlist(shuffled) == read(10)


def test_natural_order() -> None:
    found = build_netlist(
        [NetComponent("R10"), NetComponent("R2"), NetComponent("C1")],
        [NetlistNet("B", "", (NetNode("U1", "10"), NetNode("U1", "9"), NetNode("R2", "1")))],
    )
    assert [c.ref for c in found.components] == ["C1", "R2", "R10"]
    assert [n.element for n in found.nets[0].nodes] == ["R2-1", "U1-9", "U1-10"]


def test_nets_of_one_name_are_joined_and_empty_nets_dropped() -> None:
    nets = [
        NetlistNet("A", "", (NetNode("R1", "1"),)),
        NetlistNet("A", "X", (NetNode("R2", "1"),)),
        NetlistNet("E"),
    ]
    found = build_netlist([], nets)
    assert found.nets == (NetlistNet("A", "X", (NetNode("R1", "1"), NetNode("R2", "1"))),)


def test_not_a_netlist() -> None:
    with pytest.raises(FormatError, match="kicad_sch") as caught:
        read_netlist("(kicad_sch (version 20260306))")
    assert getattr(type(caught.value), "cli_code", "FEN-3004") == "FEN-3004"


@pytest.mark.parametrize("head", ["components", "nets"])
def test_missing_section(head: str) -> None:
    root = parse(text(9))
    without = root.with_children([c for c in root.children if getattr(c, "name", "") != head])
    with pytest.raises(FormatError, match=head):
        read_netlist(dumps(without), file="x.net")


def test_not_an_expression() -> None:
    with pytest.raises(FormatError):
        read_netlist("this is no netlist")


def test_differences_are_located() -> None:
    first = read(10)
    second = moved(first, ("R1", "2"), "LED_A", "GND")
    found = differences(first, second)
    assert len(found) == 2
    assert any("LED_A" in line and "R1-2" in line for line in found)
    assert any("GND" in line and "R1-2" in line for line in found)
    assert list(found) == sorted(found)


def test_equal_netlists_have_no_difference() -> None:
    assert differences(read(9), read(10)) == ()


def test_component_differences() -> None:
    first = read(10)
    changed = tuple(
        replace(c, value="470") if c.ref == "R1" else replace(c, footprint="Other:FP") if c.ref == "D1" else c
        for c in first.components
        if c.ref != "U1"
    )
    found = differences(first, KicadNetlist((*changed, NetComponent("U9")), first.nets))
    assert found == (
        "component D1: footprint 'Mini:Mini_LED_THT_3mm' in the first and 'Other:FP' in the second",
        "component R1: value '330' in the first and '470' in the second",
        "component U1: only in the first",
        "component U9: only in the second",
    )


def test_net_on_one_side_only() -> None:
    first = read(10)
    second = KicadNetlist(first.components, tuple(n for n in first.nets if n.name != "VIN"))
    assert differences(first, second) == ("net VIN: only in the first",)
    assert differences(second, first) == ("net VIN: only in the second",)


def test_pintypes_and_netclasses_are_options() -> None:
    first = read(10)
    nets = tuple(
        replace(n, netclass="Other", nodes=tuple(replace(x, pintype="input") for x in n.nodes))
        if n.name == "VIN"
        else n
        for n in first.nets
    )
    second = KicadNetlist(first.components, nets)
    assert differences(first, second) == (
        "net VIN: U1-9 is 'power_in' in the first and 'input' in the second",
    )
    assert differences(first, second, pintypes=False) == ()
    assert len(differences(first, second, netclasses=True)) == 2


def test_fields_are_not_compared() -> None:
    first = read(10)
    second = KicadNetlist(tuple(replace(c, properties={}) for c in first.components), first.nets)
    assert differences(first, second) == ()


def test_evidence_names_its_hypothesis() -> None:
    assert netlist.EVIDENCE.hypotheses == ("H-K-NETLIST-SHAPE",)
