# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Channels of a ``Repeat`` statement, their nets, and the pin-to-pad map (capability altium-import,
"Repeated sheets as channels", "Channel designators", "Channel nets", "Pin-to-pad map of a footprint
model"; change c0083). The sheets are authored record by record (``_altium_channels``)."""

from __future__ import annotations

import dataclasses

import _altium_channels as two
import _altium_records as rec
import pytest

from fenolite.backends.altium.adapter import (
    BoardInput,
    NetOptions,
    ProjectInput,
    import_circuit,
    import_project,
)
from fenolite.backends.altium.adapter.channels import channel_alpha, channel_designator, room_name
from fenolite.backends.altium.adapter.circuit import pin_pad_map
from fenolite.backends.altium.adapter.netlist import (
    MAX_CHANNELS,
    Repeat,
    parse_repeat,
    repeat_entry,
    resolve,
)
from fenolite.backends.altium.adapter.parts import part_groups
from fenolite.backends.altium.read.project import read_project
from fenolite.checks.assignment_compare import model_netlist
from fenolite.checks.equivalence.levels import level_netlist
from fenolite.core.errors import Issue
from fenolite.model.circuit import Circuit

OPTIONS = NetOptions(channel_format=two.FORMAT, room_style=0)


def codes(issues: list[Issue]) -> list[str]:
    return sorted({i.code.removeprefix("altium.import.") for i in issues})


def read(statement: str = two.STATEMENT, options: NetOptions = OPTIONS, **changes: str) -> tuple[
    Circuit, list[Issue]
]:  # fmt: skip
    issues: list[Issue] = []
    top, child = two.sheets(statement, **changes)
    return import_circuit((top.input(), child.input()), options=options, issues=issues), issues


def nets(circuit: Circuit) -> dict[str, list[tuple[str, str]]]:
    refs = {component.id: component.ref for component in circuit.components}
    return {net.name: sorted((refs[m.component_id], m.pin) for m in net.members) for net in circuit.nets}


# --- the statement ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Repeat(CH,1,2)", Repeat("CH", 1, 2)),
        ("repeat( PD , 0 , 15 )", Repeat("PD", 0, 15)),
        ("REPEAT(CH,2,1)", Repeat("CH", 2, 1)),
        ("Repeat(CH,1)", None),
        ("Repeat(CH,-1,2)", None),
        ("Repeat(,1,2)", None),
        ("Repeat(CH,1,2) x", None),
        ("Repeat(CH,a,2)", None),
        ("CH1", None),
        ("", None),
    ],
)
def test_parse_repeat(text: str, expected: Repeat | None) -> None:
    assert parse_repeat(text) == expected


def test_repeat_count_and_entry() -> None:
    assert Repeat("CH", 3, 6).count == 4 and Repeat("CH", 2, 1).count == 0
    assert repeat_entry("Repeat(OUT)") == "OUT" and repeat_entry(" repeat( OUT ) ") == "OUT"
    assert repeat_entry("OUT") is None and repeat_entry("Repeat()") is None
    assert repeat_entry("Repeat(CH,1,2)") is None
    assert MAX_CHANNELS == 256


# --- instances --------------------------------------------------------------------------------------------


def test_instances_of_two_channels() -> None:
    """Scenario "Two channels": four components in the modules ``CH[1]`` and ``CH[2]``."""
    circuit, issues = read()
    channel = sorted((c.ref, c.path) for c in circuit.components if "/" in c.path)
    assert channel == [
        ("C12_CH1", "CH[1]/C12_CH1"),
        ("C12_CH2", "CH[2]/C12_CH2"),
        ("R1_CH1", "CH[1]/R1_CH1"),
        ("R1_CH2", "CH[2]/R1_CH2"),
    ]
    assert [(m.path, m.ext["altium"].payload) for m in circuit.modules] == [
        ("CH[1]", (("sheet_symbol", "SYMBOL01"), ("channel_index", "1"))),
        ("CH[2]", (("sheet_symbol", "SYMBOL01"), ("channel_index", "2"))),
    ]
    assert all(len(m.component_ids) == 2 for m in circuit.modules)
    said = [i for i in issues if i.code == "altium.import.channels"]
    assert len(said) == 1 and "CH" in said[0].message and "2 times" in said[0].message
    assert said[0].severity == "info" and said[0].where.startswith(two.TOP)
    assert "repeated-sheet" not in codes(issues) and "channel-naming" not in codes(issues)


def test_instances_have_ids_of_their_own_and_are_stable() -> None:
    top, child = two.sheets()
    resolved = resolve((top.input(), child.input()), OPTIONS)
    assert [(i.names, i.uids, i.prefixes, i.indexes, i.position) for i in resolved.instances] == [
        ((), (), (), (), None),
        (("CH[1]",), ("SYMBOL01[1]",), ("CH",), (1,), 0),
        (("CH[2]",), ("SYMBOL01[2]",), ("CH",), (2,), 1),
    ]
    assert resolved.instances[1].labels == ("CH1",) and resolved.instances[1].repeated
    assert sorted(v for v in resolved.component_ids.values() if "SYMBOL01" in v) == [
        "cmp:\\SYMBOL01[1]\\CUID0001",
        "cmp:\\SYMBOL01[1]\\RUID0001",
        "cmp:\\SYMBOL01[2]\\CUID0001",
        "cmp:\\SYMBOL01[2]\\RUID0001",
    ]
    first, _ = read()
    second, _ = read()
    assert [c.id for c in first.components] == [c.id for c in second.components]
    assert len({c.id for c in first.components}) == 6
    assert len({pin.id for c in first.components for pin in c.pins}) == 11


def test_repeat_with_another_first_index() -> None:
    circuit, _ = read("Repeat(CH,3,5)", bus="OUT[3..5]")
    assert sorted(m.path for m in circuit.modules) == ["CH[3]", "CH[4]", "CH[5]"]
    assert sorted(c.ref for c in circuit.components if c.ref.startswith("R1")) == [
        "R1_CH3", "R1_CH4", "R1_CH5",
    ]  # fmt: skip


@pytest.mark.parametrize(
    ("statement", "reason"),
    [
        ("Repeat(CH,2,1)", "above its last index"),
        ("Repeat(CH,1)", "has not the form"),
        ("Repeat(CH,1,300)", "above 256 instances"),
    ],
)
def test_repeat_that_is_not_instantiated(statement: str, reason: str) -> None:
    """Scenario "Unparsable repeat": one instance is read and the issue names the sheet symbol."""
    circuit, issues = read(statement)
    assert len(circuit.modules) == 1 and len(circuit.components) == 4
    (said,) = [i for i in issues if i.code == "altium.import.repeated-sheet"]
    assert said.severity == "warning" and "CH" in said.message and reason in said.message
    assert "channels" not in codes(issues)
    assert sorted(c.ref for c in circuit.components) == ["C12", "J1", "R1", "U1"]


def test_repeat_inside_a_repeat() -> None:
    top = rec.Sheet("top.SchDoc")
    top.symbol("Repeat(BANK,1,2)", "bank.SchDoc", (100, 200), uid="BANKSYM1")
    bank = rec.Sheet("bank.SchDoc")
    bank.symbol("Repeat(CH,1,3)", "ch.SchDoc", (100, 200), uid="CHANSYM1")
    channel = rec.Sheet("ch.SchDoc")
    channel.component("R1", [("1", 10, 10)], uid="RUID0001")
    issues: list[Issue] = []
    options = NetOptions(channel_format="$Component_$RoomName", room_style=2)
    circuit = import_circuit((top.input(), bank.input(), channel.input()), options=options, issues=issues)
    assert sorted(c.ref for c in circuit.components) == [
        f"R1_BANK{b}_CH{c}" for b in (1, 2) for c in (1, 2, 3)
    ]
    assert sorted(c.path for c in circuit.components)[0] == "BANK[1]/CH[1]/R1_BANK1_CH1"
    assert len([i for i in issues if i.code == "altium.import.channels"]) == 2
    flat = import_circuit(
        (top.input(), bank.input(), channel.input()),
        options=NetOptions(channel_format=two.FORMAT, room_style=0),
    )
    assert sorted(c.ref for c in flat.components)[0] == "R1@BANK1/CH1"  # a flat room would name two alike


def test_single_sheet_projects_have_no_channel_fields() -> None:
    """A project without a repeat keeps the model it had: no channel bag, the sheet's designators."""
    top = rec.Sheet("top.SchDoc")
    top.symbol("A", "a.SchDoc", (100, 200), uid="SYMBOL01")
    child = rec.Sheet("a.SchDoc")
    child.component("R1", [("1", 10, 10)], uid="RUID0001")
    circuit = import_circuit((top.input(), child.input()), options=OPTIONS)
    assert [(m.path, m.ext) for m in circuit.modules] == [("A", {})]
    assert [(c.ref, c.pin_pad_map, c.native_ids["altium"]) for c in circuit.components] == [
        ("R1", (), "cmp:\\SYMBOL01\\RUID0001")
    ]


# --- designators ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("form", "style", "expected"),
    [
        ("$Component_$RoomName", 0, "R12_CH2"),
        ("$Component_$RoomName", 1, "R12_CHB"),
        ("$RoomName_$Component", 2, "BANK_CH2_R12"),
        ("$Component_$RoomName", 3, "R12_BANK_CHB"),
        ("$Component$ChannelAlpha", 0, "R12B"),
        ("$Component_$ChannelPrefix$ChannelAlpha", 0, "R12_CHB"),
        ("$Component_$ChannelIndex", 0, "R12_2"),
        ("$Component_$ChannelPrefix$ChannelIndex", 0, "R12_CH2"),
        ("$ComponentPrefix_$ChannelIndex_$ComponentIndex", 0, "R_2_12"),
        ("$ComponentPrefix_$RoomName_$ComponentIndex", 0, "R_CH2_12"),
    ],
)
def test_designator_formats_of_a_repeat_channel(form: str, style: int, expected: str) -> None:
    """The eight predefined formats (S-0452) on channel 2 of ``Repeat(CH, 1, 2)`` under ``BANK``."""
    found = channel_designator(form, "R12", ["BANK", "CH"], style=style, separator="_", indexes=[None, 2])
    assert found == expected


def test_designator_keywords_that_a_repeat_channel_cannot_resolve() -> None:
    names, indexes = ["CH"], [27]
    assert channel_alpha(1) == "A" and channel_alpha(26) == "Z"
    assert channel_alpha(0) is None and channel_alpha(27) is None and channel_alpha(None) is None
    assert channel_designator("$Component$ChannelAlpha", "R1", names, indexes=indexes) is None
    assert channel_designator("$Component_$ChannelIndex", "R1", names, indexes=indexes) == "R1_27"
    assert channel_designator("$Component_$RoomName", "R1", names, style=1, indexes=indexes) is None
    assert channel_designator("$Component_$RoomName", "R1", names, style=4, indexes=[1]) is None
    assert room_name(["BANK", "CH"], 4, "_", [None, None]) == "BANK_CH"
    assert room_name(["CH"], 0, "_", [1, 2]) is None
    # nothing of the format tells the channels apart: never one designator for two components
    assert channel_designator("$Component_$ChannelPrefix", "R1", names, indexes=[1]) is None
    assert channel_designator("$Component", "R1", names, indexes=[1]) is None


def test_designator_from_the_format_is_counted_per_source() -> None:
    """Scenario "Designators from the naming format": four components for the source ``format``."""
    top, child = two.sheets()
    resolved = resolve((top.input(), child.input()), OPTIONS)
    assert resolved.channel_sources == {"format": 4}
    assert sorted(set(resolved.refs.values())) == ["C12_CH1", "C12_CH2", "J1", "R1_CH1", "R1_CH2", "U1"]


def test_designator_of_an_unknown_format() -> None:
    """Scenario "Unknown format": one issue, and references no Altium format produces."""
    circuit, issues = read(options=NetOptions(channel_format="$Component_$Other", room_style=0))
    channel = sorted(c.ref for c in circuit.components if "@" in c.ref)
    assert channel == ["C12@CH1", "C12@CH2", "R1@CH1", "R1@CH2"]
    said = [i for i in issues if i.code == "altium.import.channel-naming"]
    assert len(said) == 1 and "4 component(s)" in said[0].message
    refs = [c.ref for c in circuit.components]
    assert len(refs) == len(set(refs))


def test_designator_options_come_from_the_project_file() -> None:
    project = read_project(two.project_text("$Component$ChannelAlpha").encode("utf-8"), file=two.PROJECT)
    circuit, _ = read(options=NetOptions.from_project(project))
    assert sorted(c.ref for c in circuit.components if c.ref[-1] in "AB") == ["C12A", "C12B", "R1A", "R1B"]


def board(*parts: object) -> BoardInput:
    return BoardInput("b.PcbDoc", rec.SHA, rec.document(components=parts))  # type: ignore[arg-type]


def test_designator_link_of_a_board_to_repeat_channels() -> None:
    """No unique-id path form of a Repeat channel is recorded: a board component links only when its own
    designator is the channel's and its source designator the sheet's; the rest is said."""
    top, child = two.sheets()
    parts = [
        rec.component("R1", unique_id="A", source_unique_id="\\ANY\\RUID0001"),
        rec.component("C12", unique_id="B", source_unique_id="\\ANY\\CUID0001"),
    ]
    texts = [
        rec.text("R1_CH1", designator=True, component=0),
        rec.text("C12_X", designator=True, component=1),
    ]
    document = rec.document(components=parts, texts=texts)
    issues: list[Issue] = []
    project = ProjectInput(
        "p",
        options=OPTIONS,
        sheets=(top.input(), child.input()),
        board=BoardInput("b.PcbDoc", rec.SHA, document),
    )
    design = import_project(project, issues=issues)
    assert design.board is not None
    by_id = {c.id: c for c in design.circuit.components}
    linked = [by_id[f.component_id] for f in design.board.footprints]
    assert [(c.ref, c.path) for c in linked] == [("R1_CH1", "CH[1]/R1_CH1"), ("C12_X", "C12_X")]
    (said,) = [i for i in issues if i.code == "altium.import.channel-naming"]
    assert "3 component(s) of Repeat channels" in said.message
    assert {"linked-by-designator", "pcb-only-component"} <= set(codes(issues))
    assert [i for i in design.validate() if i.code == "model.duplicate-ref"] == []


# --- nets -------------------------------------------------------------------------------------------------


def test_nets_shared_and_per_channel() -> None:
    """Scenario "Shared and per-channel nets"."""
    circuit, issues = read()
    assert nets(circuit) == {
        "MID_CH1": [("C12_CH1", "1"), ("R1_CH1", "2")],
        "MID_CH2": [("C12_CH2", "1"), ("R1_CH2", "2")],
        "OUT1": [("C12_CH1", "2"), ("U1", "1")],
        "OUT2": [("C12_CH2", "2"), ("U1", "2")],
        "VCC": [("J1", "1"), ("R1_CH1", "1"), ("R1_CH2", "1")],
    }
    assert "duplicate-net-name" not in codes(issues) and "channel-naming" not in codes(issues)
    (bus,) = circuit.buses
    names = {net.id: net.name for net in circuit.nets}
    assert [(m.index, names[m.net_id]) for m in bus.members] == [(1, "OUT1"), (2, "OUT2")]
    mid = next(net for net in circuit.nets if net.name == "MID_CH1")
    assert mid.ext["altium"].payload == (("alias", "MID"),)


def test_nets_follow_the_order_of_the_bus() -> None:
    """Channel ``i`` takes member ``i`` of the bus, counted from the first channel."""
    circuit, _ = read(bus="OUT[2..1]")
    found = nets(circuit)
    assert found["OUT2"] == [("C12_CH1", "2"), ("U1", "2")]
    assert found["OUT1"] == [("C12_CH2", "2"), ("U1", "1")]


def test_nets_of_a_bus_that_is_too_short() -> None:
    circuit, issues = read("Repeat(CH,1,3)")
    (said,) = [i for i in issues if i.code == "altium.import.channel-naming"]
    assert "Repeat(OUT)" in said.message and "2 member(s)" in said.message and "1 channel(s)" in said.message
    assert said.where.startswith(f"{two.TOP}:")
    found = nets(circuit)
    assert found["OUT1"] == [("C12_CH1", "2"), ("U1", "1")]
    assert not any(("C12_CH3", "2") in members for members in found.values())


def test_nets_of_a_repeated_entry_without_a_bus() -> None:
    circuit, issues = read(bus="DATA[1..2]")
    (said,) = [i for i in issues if i.code == "altium.import.channel-naming"]
    assert "no bus named OUT" in said.message and "2 channel(s)" in said.message
    assert nets(circuit)["OUT1"] == [("U1", "1")]


def test_nets_of_a_plain_entry_join_every_channel() -> None:
    circuit, issues = read(entry="OUT")
    found = nets(circuit)
    assert [members for members in found.values() if ("C12_CH1", "2") in members] == [
        [("C12_CH1", "2"), ("C12_CH2", "2")]
    ]
    assert "channel-naming" not in codes(issues)
    assert "Repeat(OUT)" not in found


def test_nets_local_without_a_format_keep_their_name() -> None:
    circuit, issues = read(options=NetOptions())
    found = nets(circuit)
    assert found["MID"] == [("C12", "1"), ("R1", "2")] and found["MID#2"] == [("C12", "1"), ("R1", "2")]
    assert "duplicate-net-name" in codes(issues)


def test_nets_without_a_name_take_the_channel_designator() -> None:
    """A net without an identifier is named after a pin of its channel's component."""
    top = rec.Sheet("top.SchDoc")
    top.symbol("Repeat(CH,1,2)", "ch.SchDoc", (100, 200), uid="SYMBOL01")
    child = rec.Sheet("ch.SchDoc")
    child.component("R1", [("1", 10, 10)], uid="RUID0001")
    child.component("C1", [("1", 40, 10)], uid="CUID0001")
    child.wire((10, 10), (40, 10))
    circuit = import_circuit((top.input(), child.input()), options=OPTIONS)
    assert sorted(net.name for net in circuit.nets) == ["NetC1_CH1_1", "NetC1_CH2_1"]


# --- the pin-to-pad map -----------------------------------------------------------------------------------


def mapped_sheet(pin_map: dict[str, tuple[str, ...]]) -> rec.Sheet:
    sheet = rec.Sheet()
    sheet.component(
        "Q1",
        [("1", 10, 10), ("2", 10, 20), ("3", 10, 30)],
        uid="QUID0001",
        footprint="SOT23",
        pin_map=pin_map,
    )
    sheet.component("R1", [("1", 40, 10), ("2", 40, 20)], uid="RUID0001")
    sheet.wire((10, 10), (40, 10))
    sheet.wire((10, 20), (40, 20))
    return sheet


def test_pin_map_names_the_elements() -> None:
    """Scenario "Mapped pins": the elements of ``Q1`` are its pads."""
    issues: list[Issue] = []
    circuit = import_circuit((mapped_sheet({"1": ("G",), "2": ("D",), "3": ("S",)}).input(),), issues=issues)
    q1 = next(c for c in circuit.components if c.ref == "Q1")
    assert q1.pin_pad_map == (("1", "G"), ("2", "D"), ("3", "S")) and q1.ext == {}
    assert [pin.number for pin in q1.pins] == ["1", "2", "3"]
    design = type("D", (), {"circuit": circuit})()
    elements = sorted(a.element for a in model_netlist(design).assignments)  # type: ignore[arg-type]
    assert elements == ["Q1-D", "Q1-G", "Q1-S", "R1-1", "R1-2"]
    members = {(m.component_id == q1.id, m.pin) for net in circuit.nets for m in net.members}
    assert (True, "1") in members and (True, "G") not in members  # net members stay keyed by pin
    assert "pin-map" not in codes(issues)


def test_pin_map_identity_records_give_no_pair() -> None:
    circuit = import_circuit((mapped_sheet({"1": ("1",), "2": ("3",), "3": ("2",)}).input(),))
    q1 = next(c for c in circuit.components if c.ref == "Q1")
    assert q1.pin_pad_map == (("2", "3"), ("3", "2"))


def test_pin_map_several_pads_of_one_pin() -> None:
    """Scenario "Several pads of one pin" (change c0123): one pair per pad of a record, in its order; a
    record without a pad is what the model cannot hold, and is kept in the bag."""
    issues: list[Issue] = []
    sheet = mapped_sheet({"1": ("1", "4"), "2": ("5", "6"), "3": ()})
    (group,) = [g for g in part_groups(sheet.document()) if g.ref == "Q1"]
    pairs = (("1", "1"), ("1", "4"), ("2", "5"), ("2", "6"))
    assert pin_pad_map(group) == (pairs, (("3", ""),), 1)
    circuit = import_circuit((sheet.input(),), issues=issues)
    q1 = next(c for c in circuit.components if c.ref == "Q1")
    assert q1.pin_pad_map == pairs
    assert q1.pads_of("1") == ("1", "4") and q1.pads_of("2") == ("5", "6") and q1.pads_of("3") == ("3",)
    assert q1.ext["altium"].payload == (("pin_pads", "3="),)
    (said,) = [i for i in issues if i.code == "altium.import.pin-map"]
    assert said.severity == "info" and "1 pin map record(s)" in said.message
    design = type("D", (), {"circuit": circuit})()
    elements = sorted(a.element for a in model_netlist(design).assignments if a.element.startswith("Q1-"))  # type: ignore[arg-type]
    assert elements == ["Q1-1", "Q1-3", "Q1-4", "Q1-5", "Q1-6"]
    imported = import_project(ProjectInput("p", sheets=(sheet.input(),)))
    assert not [i for i in imported.validate() if i.code == "model.pin-pad-map"]


def test_pin_map_pad_that_another_pin_holds() -> None:
    """Scenario "Pad that another pin holds": the pad gives no pair, the other pads of the record do, and
    the record is kept in the bag and counted."""
    issues: list[Issue] = []
    sheet = mapped_sheet({"1": ("2", "7")})
    (group,) = [g for g in part_groups(sheet.document()) if g.ref == "Q1"]
    assert pin_pad_map(group) == ((("1", "7"),), (("1", "2,7"),), 1)
    circuit = import_circuit((sheet.input(),), issues=issues)
    q1 = next(c for c in circuit.components if c.ref == "Q1")
    assert q1.ext["altium"].payload == (("pin_pads", "1=2,7"),)
    assert [i.message[:1] for i in issues if i.code == "altium.import.pin-map"] == ["1"]
    # a record whose only pad another pin holds leaves the pin its own designator, as before
    taken = mapped_sheet({"2": ("1",)})
    (group,) = [g for g in part_groups(taken.document()) if g.ref == "Q1"]
    assert pin_pad_map(group) == ((), (("2", "1"),), 1)
    # a pad listed twice in one record gives one pair, and the pairs say the record in full
    twice = mapped_sheet({"3": ("S", "S", "T")})
    (group,) = [g for g in part_groups(twice.document()) if g.ref == "Q1"]
    assert pin_pad_map(group) == ((("3", "S"), ("3", "T")), (), 0)
    # two pins that list one pad: the first in the pin table takes it
    shared = mapped_sheet({"1": ("X", "Y"), "2": ("Y", "Z")})
    (group,) = [g for g in part_groups(shared.document()) if g.ref == "Q1"]
    assert pin_pad_map(group) == ((("1", "X"), ("1", "Y"), ("2", "Z")), (("2", "Y,Z"),), 1)


def test_pin_map_is_read_from_the_partial_and_from_the_full_form() -> None:
    """A footprint model may hold a record only for a pin with other pads than its own (the form Altium
    saves, and the one Fenolite writes) or a record for every pin, the others naming their own pad: both
    import to the same map."""
    partial = import_circuit((mapped_sheet({"3": ("3", "EP")}).input(),))
    full = import_circuit((mapped_sheet({"1": ("1",), "2": ("2",), "3": ("3", "EP")}).input(),))
    maps = [next(c for c in circuit.components if c.ref == "Q1").pin_pad_map for circuit in (partial, full)]
    assert maps[0] == maps[1] == (("3", "3"), ("3", "EP"))


def test_pin_map_several_pads_on_the_board_side() -> None:
    """Scenario "Board net through a pin of two pads": a net of the PCB document that the sheets lack
    lists the pin once, whichever of its pads the net is on."""
    sheet = mapped_sheet({"3": ("3", "EP")})
    parts = [rec.component("Q1", unique_id="A", source_unique_id="\\QUID0001")]
    document = rec.document(
        nets=["ONLYPCB"],
        components=parts,
        pads=[rec.pad("3", (0, 0), net=0, component=0), rec.pad("EP", (100, 0), net=0, component=0)],
    )
    project = ProjectInput("p", sheets=(sheet.input(),), board=BoardInput("b.PcbDoc", rec.SHA, document))
    design = import_project(project)
    q1 = next(c for c in design.circuit.components if c.ref == "Q1")
    assert q1.pin_pad_map == (("3", "3"), ("3", "EP"))
    only = next(net for net in design.circuit.nets if net.name == "ONLYPCB")
    assert [(m.component_id == q1.id, m.pin) for m in only.members] == [(True, "3")]


def test_pin_map_of_the_board_side_names_the_pin() -> None:
    """A net of the PCB document that the sheets lack lists the pin of its pad, not the pad."""
    sheet = mapped_sheet({"1": ("G",), "2": ("D",), "3": ("S",)})
    parts = [rec.component("Q1", unique_id="A", source_unique_id="\\QUID0001")]
    document = rec.document(
        nets=["ONLYPCB"], components=parts, pads=[rec.pad("S", (0, 0), net=0, component=0)]
    )
    project = ProjectInput("p", sheets=(sheet.input(),), board=BoardInput("b.PcbDoc", rec.SHA, document))
    design = import_project(project)
    q1 = next(c for c in design.circuit.components if c.ref == "Q1")
    only = next(net for net in design.circuit.nets if net.name == "ONLYPCB")
    assert [(m.component_id == q1.id, m.pin) for m in only.members] == [(True, "3")]


def test_pin_map_in_level_2_of_equivalent() -> None:
    """Level 2 names a mapped pin by its pad: a design equals itself, and differs from the same design
    without the map on the three pins of ``Q1``."""
    sheet = mapped_sheet({"1": ("G",), "2": ("D",), "3": ("S",)})
    design = import_project(ProjectInput("p", sheets=(sheet.input(),)))
    same = level_netlist(design, design, ["Q1", "R1"])
    assert same.compared == 5 and same.differences == ()
    plain = dataclasses.replace(
        design,
        circuit=dataclasses.replace(
            design.circuit,
            components=tuple(dataclasses.replace(c, pin_pad_map=()) for c in design.circuit.components),
        ),
    )
    other = level_netlist(design, plain, ["Q1", "R1"])
    assert other.compared == 2
    assert sorted((d.kind, d.where) for d in other.differences) == [
        ("pin-missing", "Q1-1"), ("pin-missing", "Q1-2"), ("pin-missing", "Q1-3"),
        ("pin-missing", "Q1-D"), ("pin-missing", "Q1-G"), ("pin-missing", "Q1-S"),
    ]  # fmt: skip
