# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The resolver of drawn schematics against ``kicad-cli sch export netlist``, and the written drawn sheets
against KiCad's ERC (capability drawn-schematic, "Drawn schematic evidence"; capability kicad-schematic,
"Drawn sheets written"; hypotheses ``H-K-DRAWN-CONNECT``, ``H-K-DRAWN-NAMES``, ``H-K-DRAWN-BUS``,
``H-K-DRAWN-REPEAT`` and ``H-K-DRAWN-WRITE``; change c0276).

Each authored drawn fixture is built for the running major. Connectivity is compared as partitions of the
pins of drawn components; names are printed and compared apart, since a name difference is a warning."""

from __future__ import annotations

from collections import Counter

import _drawn
import _erc
import _probes
import pytest

from fenolite.model.drawn_connect import DrawnNetlist

pytestmark = pytest.mark.needs_kicad
CASES = (*_drawn.NAMES, "example")


def _refs(output: object) -> dict[str, str]:
    circuit = output.design.circuit  # type: ignore[attr-defined]
    return {c.properties["fenolite.path"]: c.ref for c in circuit.components}


def _partition(netlist: DrawnNetlist, refs: dict[str, str]) -> set[frozenset[tuple[str, str]]]:
    groups = {frozenset((refs[p], n) for p, n in net.members) for net in netlist.nets}
    return groups | {frozenset({(refs[p], n)}) for p, n in netlist.open}


def _kicad_partition(
    nets: dict[str, set[tuple[str, str]]], pins: set[tuple[str, str]]
) -> set[frozenset[tuple[str, str]]]:
    groups = {frozenset(nodes & pins) for nodes in nets.values()} - {frozenset()}
    seen = {pin for group in groups for pin in group}
    return groups | {frozenset({pin}) for pin in pins - seen}


@pytest.mark.parametrize("name", CASES)
def test_resolver_equals_the_export(name: str) -> None:
    """Scenario "Oracle on 9.0 and 10.0" (``H-K-DRAWN-CONNECT``, ``-BUS``, ``-REPEAT``)."""
    output = _drawn.build(name, _probes.major())
    files = dict(output.files)
    _drawn_value, netlist, _circuit = _drawn.resolved(output)
    refs = _refs(output)
    pins = {(refs[p], n) for p, n in netlist.pins}
    exported = _erc.netlist(_probes.runner(), _drawn.root_name(output), files)
    ours, theirs = _partition(netlist, refs), _kicad_partition(exported, pins)
    print(
        f"{name}: {len(ours)} groups; only ours {sorted(map(sorted, ours - theirs))}; only KiCad's "
        f"{sorted(map(sorted, theirs - ours))}"
    )
    names = {net.name: frozenset((refs[p], n) for p, n in net.members) for net in netlist.nets if net.name}
    kicad_names = {frozenset(nodes & pins): net for net, nodes in exported.items()}
    differing = {
        ours_name: kicad_names.get(group)
        for ours_name, group in names.items()
        if kicad_names.get(group) != ours_name
    }
    print(f"  names (H-K-DRAWN-NAMES): {'equal' if not differing else differing}")
    assert ours == theirs


@pytest.mark.parametrize("name", CASES)
def test_kicad_loads_the_drawn_sheets(name: str) -> None:
    """Scenario "KiCad loads the drawn sheets" (``H-K-DRAWN-WRITE``): ERC runs on every written fixture and
    reports no violation about a wire, a dangling label, a bus or a sheet pin."""
    output = _drawn.build(name, _probes.major())
    report = _erc.run_erc(_probes.runner(), _drawn.root_name(output), dict(output.files))
    found: Counter[str] = _erc.types(_erc.violations(report))
    print(f"{name}: ERC {dict(found)}")
    connectivity = {
        "label_dangling", "wire_dangling", "bus_entry_needed", "bus_to_net_conflict", "net_not_bus_member",
        "hier_label_mismatch", "multiple_net_names", "unconnected_wire_endpoint", "global_label_dangling",
        "bus_definition_conflict", "similar_labels",
    }  # fmt: skip
    # a label on a net of one pin (B0, B1 of the full fixture) is the drawing's own choice, not a defect;
    # 9.0.9 also calls those two labels dangling, while its netlist names their nets by them (measured on
    # 2026-10-29: the net of U1 pin 18 is /B0 on 9.0.9 and 10.0.6)
    if name == "full" and _probes.major() == 9:
        connectivity.discard("label_dangling")
    assert not set(found) & connectivity, found
