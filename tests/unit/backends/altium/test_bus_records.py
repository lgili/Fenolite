# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bus records (capability altium-schematic-writer, "Bus records"; change c0086): the bus identifier, the
buses that are drawn, the records of a bus block, and the bus port and bus sheet entry of a crossing."""

from __future__ import annotations

from pathlib import Path

import pytest
from _altium import sample
from _altium_tree import documents, nets_of, read_back, tree_build, tree_model, with_bus

from fenolite.backends.altium.layout import BUS_ENTRY, BUS_RUN, ENTRY_PITCH, LABEL_OFFSET, bus_block
from fenolite.backends.altium.project import bus_identifier, lowered_buses
from fenolite.backends.altium.read.sch import BusEntry, SheetEntry
from fenolite.dsl import to_model
from fenolite.lens.altium import build_altium

MEMBERS = ("D0", "D1", "D2", "D3")


@pytest.mark.parametrize(
    ("names", "label"),
    [
        (MEMBERS, "D[0..3]"),
        (("A7", "A6", "A5"), "A[7..5]"),
        (("BUS_9", "BUS_10"), "BUS_[9..10]"),
        (("D0", "D2"), None),  # not consecutive
        (("D0", "E1"), None),  # two stems
        (("D00", "D01"), None),  # leading zeros would not give these names back
        (("D0",), None),
        (("CLK", "DATA"), None),
        (("0", "1"), None),  # no stem
    ],
)
def test_bus_identifier(names: tuple[str, ...], label: str | None) -> None:
    assert bus_identifier(names) == label


def test_lowered_and_flattened_buses() -> None:
    model = tree_model()
    drawn, flattened = lowered_buses(model)
    assert [(b.name, b.label, b.members) for b in drawn] == [("D", "D[0..3]", MEMBERS)] and not flattened
    twice = with_bus(model, "E", ("D1", "D2"))
    drawn, flattened = lowered_buses(twice)
    assert [b.name for b in drawn] == ["D"] and flattened == [("E", "its net D1 is drawn in the bus D")]
    odd = with_bus(to_model(sample()), "CTRL", ("EN", "LED_DRV"))
    assert lowered_buses(odd) == (
        [],
        [("CTRL", "its member nets are not one stem followed by consecutive integers")],
    )
    power = with_bus(to_model(sample()), "P", ("VIN", "GND"))
    assert "not one stem" in lowered_buses(power)[1][0][1]


def test_bus_block_geometry() -> None:
    block = bus_block("D[0..3]", MEMBERS, (1000, 2000))
    bx = 1000 + BUS_RUN
    assert block.line == ((1000, 2000), (bx, 2000), (bx, 2000 + 4 * ENTRY_PITCH))
    for k, ((start, end), stub) in enumerate(zip(block.entries, block.stubs, strict=True), start=1):
        assert start == (bx, 2000 + ENTRY_PITCH * (k - 1)) and end == (bx + BUS_ENTRY, 2000 + ENTRY_PITCH * k)
        assert stub.start == end and stub.net.net == MEMBERS[k - 1] and stub.net.kind == "label"
    with pytest.raises(ValueError, match="no member"):
        bus_block("D[0..3]", (), (0, 0))


def test_bus_label_lies_beside_the_connection_point() -> None:
    """Scenario "Bus label beside the connection point" (change c0151): the net label of a bus block lies
    ``LABEL_OFFSET`` along the first run of the line, as a wire's label does, and not on the point where
    the bus meets its port or sheet entry."""
    block = bus_block("D[0..3]", MEMBERS, (1000, 2000))
    assert block.label_point == (1000 + LABEL_OFFSET, 2000) and LABEL_OFFSET < BUS_RUN
    for form in ("binary", "ascii"):
        for sheet in documents(tree_build(form=form)).values():
            labels = {label.location for label in sheet.net_labels()}
            for bus in sheet.buses():
                assert bus.points[0] not in labels, sheet.file


def test_four_bit_bus(tmp_path: Path) -> None:
    """Scenario "Four-bit bus": the single sheet holds one bus labelled ``D[0..3]`` with four bus
    entries, and the netlist read back holds ``D0`` to ``D3`` with their pins, in both forms."""
    for form in ("binary", "ascii"):
        output = tree_build(form=form, sheets="flat")
        (sheet,) = documents(output).values()
        (bus,) = sheet.buses()
        assert len(bus.points) == 3 and len(sheet.of_type(BusEntry)) == 4
        labels = [label for label in sheet.net_labels() if label.text == "D[0..3]"]
        # the label lies on the first run of the bus line, past its start (change c0151)
        (sx, sy), (cx, _cy) = bus.points[0], bus.points[1]
        (lx, ly) = labels[0].location
        assert len(labels) == 1 and ly == sy and sx.value < lx.value < cx.value
        ends = {entry.corner for entry in sheet.of_type(BusEntry)}
        starts = {wire.points[0] for wire in sheet.wires()}
        assert ends <= starts  # each bus entry ends where its member's wire starts
        design = read_back(tmp_path / form, output)
        nets = nets_of(design)
        assert {name: nets[name] for name in MEMBERS} == {
            f"D{k}": {("J2", str(k + 1)), (f"D{k + 1}", "1")} for k in range(4)
        }
        assert [(b.name, len(b.members)) for b in design.circuit.buses] == [("D", 4)]


def test_bus_port_and_bus_sheet_entry(tmp_path: Path) -> None:
    """Where the bus crosses a sheet it is one port and one sheet entry named by the bus identifier, and
    no member has a port of its own; the nets keep the names of the model."""
    output = tree_build()
    sheets = documents(output)
    for file in ("tree_io.SchDoc", "tree_io.leds.SchDoc"):
        names = [p.name for p in sheets[file].ports()]
        assert "D[0..3]" in names and not set(names) & set(MEMBERS)
    for file in ("tree.SchDoc", "tree_io.SchDoc"):
        names = [e.name for e in sheets[file].of_type(SheetEntry)]
        assert "D[0..3]" in names and not set(names) & set(MEMBERS)
    # the top sheet draws the bus at the sheet entry; the sheet between at its port and at its entry
    assert [len(sheets[f].buses()) for f in ("tree.SchDoc", "tree_io.SchDoc", "tree_io.leds.SchDoc")] == [
        1,
        2,
        1,
    ]
    design = read_back(tmp_path, output)
    names = {net.id: net.name for net in design.circuit.nets}
    assert {tuple(names[m.net_id] for m in bus.members) for bus in design.circuit.buses} == {MEMBERS}


def test_flattened_bus_is_drawn_as_its_nets() -> None:
    model = with_bus(to_model(sample()), "CTRL", ("EN", "LED_DRV"))
    output = build_altium(model, name="altium_sample")
    (sheet,) = documents(output).values()
    assert sheet.buses() == () and sheet.of_type(BusEntry) == ()
    (found,) = [i for i in output.issues if i.code == "altium.bus-flattened"]
    assert found.where == "CTRL" and found.severity == "info"
    plain = build_altium(to_model(sample()), name="altium_sample")
    assert output.files["altium_sample.SchDoc"] == plain.files["altium_sample.SchDoc"]
