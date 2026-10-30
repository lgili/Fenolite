# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawn sheets written (capability kicad-schematic, "Drawn sheets written" and "Repeated sheets written";
change c0276)."""

from __future__ import annotations

import dataclasses

import _drawn
import pytest

from fenolite.backends.kicad import drawn as kdrawn
from fenolite.backends.kicad import sch
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.model.drawn import DrawnOpaque, DrawnSchematic

GROUP = (
    '(group "g" (uuid "7d2f6f90-63b4-4f4c-9b39-2f56b1f1e0aa") '
    '(members "0b6c1f2e-1d1a-4c6e-9d2b-1f0d2c3b4a51"))'
)


def _root_children(text: str, head: str) -> list[Node]:
    return [c for c in parse(text).children if isinstance(c, Node) and c.name == head]


@pytest.mark.parametrize("target", [9, 10])
def test_every_kind_written(target: int) -> None:
    """Scenario "Every kind written"."""
    value = _drawn.drawn("full")
    output = _drawn.build("full", target)
    assert not [i for i in output.issues if i.severity == "error"]
    text = output.files[_drawn.root_name(output)].decode("utf-8")
    root = value.sheets[0]
    assert len(_root_children(text, "junction")) == len(root.junctions) == 1
    # the bus is cut at the ends of its two entries, the form KiCad's editor keeps (kdrawn.split_at)
    entries = [e.at for e in root.bus_entries] + [e.end for e in root.bus_entries]
    cut = [piece for a, b in root.bus_segments() for piece in kdrawn.split_at(a, b, entries)]
    assert len(root.bus_segments()) == 1 and len(_root_children(text, "bus")) == len(cut) == 3
    assert len(_root_children(text, "bus_entry")) == len(root.bus_entries) == 2
    assert len(_root_children(text, "bus_alias")) == len(root.bus_aliases) == 1
    assert len(_root_children(text, "wire")) == len(root.segments())
    assert len(_root_children(text, "label")) == 4 and len(_root_children(text, "global_label")) == 2
    heads = [c.name for c in parse(text).children if isinstance(c, Node)]
    # opaque items follow the sheet references, in their drawn order, before sheet_instances
    assert heads[heads.index("sheet") + 1 : heads.index("sheet_instances")] == ["text", "rectangle"]
    extracted, netlist, _ = _drawn.resolved(output)
    again = extracted.sheets[0]
    assert set(again.segments()) == set(root.segments())
    assert again.junctions == root.junctions and again.bus_entries == root.bus_entries
    assert again.bus_aliases == root.bus_aliases and again.labels == root.labels
    assert again.opaques == root.opaques and again.title_block == root.title_block
    assert [s.part for s in again.symbols] == [s.part for s in root.symbols]
    assert again.symbols[0].fields == root.symbols[0].fields
    sub = extracted.sheet("sub")
    assert sub is not None and sub.labels == value.sheets[1].labels
    assert extracted.sheets[0].sheet_refs[0].pins == root.sheet_refs[0].pins
    assert netlist.nets


def _with_group(value: DrawnSchematic) -> DrawnSchematic:
    root = dataclasses.replace(value.sheets[0], opaques=(*value.sheets[0].opaques, DrawnOpaque(GROUP)))
    return DrawnSchematic(value.root, (root, *value.sheets[1:]))


def test_too_new_opaque_item() -> None:
    """Scenario "Too-new opaque item": a group (KiCad 10) on a sheet for target 9."""
    value = _with_group(_drawn.drawn("full"))
    with pytest.raises(LossyWriteError) as caught:
        _drawn.build("full", 9, value=value)
    assert "group" in str(caught.value)
    output = _drawn.build("full", 9, value=value, allow_lossy=True)
    dropped = [i for i in output.issues if i.code == sch.DROPPED_CODE]
    assert len(dropped) == 1 and "group" in dropped[0].message
    assert "(group" not in output.files[_drawn.root_name(output)].decode("utf-8")
    ten = _drawn.build("full", 10, value=value)
    assert "(group" in ten.files[_drawn.root_name(ten)].decode("utf-8")


def test_two_channels() -> None:
    """Scenario "Two channels": one file, one instance path per reference, footprint paths by instance."""
    output = _drawn.build("repeat", 10)
    sheets = sorted(p for p in output.files if p.endswith(".kicad_sch"))
    assert sheets == ["drawn_repeat.kicad_sch", "sheets/channel.kicad_sch"]
    channel = sch.read_schematic(
        output.files["sheets/channel.kicad_sch"].decode("utf-8"), file="channel.kicad_sch"
    )
    r1 = channel.symbols[0]
    model = {c.properties["fenolite.path"]: c for c in output.design.circuit.components}
    assert [u.ref for u in r1.uses] == [model["ch0/R1"].ref, model["ch1/R1"].ref] == ["R1", "R3"]
    assert len({u.path for u in r1.uses}) == 2
    paths = {c.properties["fenolite.path"]: c.path for c in output.design.circuit.components}
    assert output.schematic is not None
    by_id = output.schematic.paths
    first = by_id[model["ch0/R1"].id].split("/")
    second = by_id[model["ch1/R1"].id].split("/")
    assert first[-1] == second[-1] and first[:-1] != second[:-1] and len(first) == len(second) == 3
    del paths


def test_deterministic_and_generated_bytes_unchanged() -> None:
    first = _drawn.build("example", 10)
    second = _drawn.build("example", 10)
    assert {p: d for p, d in first.files.items() if p.endswith(".kicad_sch")} == {
        p: d for p, d in second.files.items() if p.endswith(".kicad_sch")
    }
