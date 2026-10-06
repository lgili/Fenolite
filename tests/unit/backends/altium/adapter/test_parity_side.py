# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic side of an Altium project for the parity comparison (``adapter.parity``; capability
altium-verification, "Parity on Altium projects"; change c0088). The committed samples must agree with
their own boards before any finding of the comparison is trusted; the spellings that differ between the
two documents of a project are tried on models authored here."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.backends.altium.adapter.parity import board_names, footprint_name, pads_of, side_of
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.checks import parity
from fenolite.core.coords import Point, Size
from fenolite.model.board import Board, FootprintInstance, Pad
from fenolite.model.circuit import Circuit, Component, Net, Pin, PinRef
from fenolite.model.design import Design

SAMPLES = Path(__file__).resolve().parents[4] / "data" / "altium"
NETS = {"R1": ("VIN", "LED_A"), "D1": ("LED_A", "GND"), "U1": ("VIN", "GND")}


def readings(name: str) -> tuple[Design, Design]:
    backend = AltiumBackend()
    read = backend.read_documents(backend.documents(SAMPLES / name))
    assert read.schematic is not None and read.pcb is not None and not read.errors
    return read.schematic.design, read.pcb.design  # type: ignore[return-value]


def schematic(
    nets: dict[str, tuple[str, ...]] = NETS, *, footprint: str = "parts:R_0603", **more: object
) -> Design:
    parts = [
        Component(
            id=f"cmp_s_{ref}",
            ref=ref,
            value="10k",
            lib_footprint_ref=footprint,
            pins=tuple(Pin(id=f"pin_{ref}_{n}", number=str(n)) for n in range(1, len(names) + 1)),
            **(more if ref == "R1" else {}),  # type: ignore[arg-type]
        )
        for ref, names in nets.items()
    ]
    members: dict[str, list[PinRef]] = {}
    for ref, names in nets.items():
        for number, name in enumerate(names, start=1):
            if name:
                members.setdefault(name, []).append(PinRef(f"cmp_s_{ref}", str(number)))
    listed = tuple(Net(id=f"net_s_{name}", name=name, members=tuple(m)) for name, m in members.items())
    return dataclasses.replace(
        Design.new("sch", seed=1), circuit=Circuit(components=tuple(parts), nets=listed)
    )


def board(nets: dict[str, tuple[str, ...]] = NETS, *, lib_ref: str = "Placed.PcbLib:R_0603") -> Design:
    names = sorted({name for held in nets.values() for name in held if name})
    listed = tuple(Net(id=f"net_p_{name}", name=name) for name in names)
    parts = tuple(Component(id=f"cmp_p_{ref}", ref=ref, value="10k") for ref in nets)
    footprints = tuple(
        FootprintInstance(
            id=f"fp_{ref}",
            component_id=f"cmp_p_{ref}",
            lib_ref=lib_ref,
            position=Point(0, 0),
            pads=tuple(
                Pad(
                    id=f"pad_{ref}_{n}",
                    number=str(n),
                    shape="rect",
                    size=Size(1, 1),
                    position=Point(0, 0),
                    layers=("F.Cu",),
                    net_id=f"net_p_{name}" if name else None,
                )
                for n, name in enumerate(held, start=1)
            ),
        )
        for ref, held in nets.items()
    )
    return dataclasses.replace(
        Design.new("pcb", seed=2),
        circuit=Circuit(components=parts, nets=listed),
        board=Board(id="brd_1", footprints=footprints),
    )


def codes(sch: Design, pcb: Design) -> list[tuple[str, str]]:
    return [(f.code, f.key) for f in parity.compare(side_of(sch, pcb), pcb).findings]


@pytest.mark.parametrize("name", ["blink", "routed", "board6"])
def test_committed_samples_agree(name: str) -> None:
    """Scenario "Agreeing project": an unedited project gives no finding, with and without the board's
    spelling (a build writes both documents with one spelling)."""
    sch, pcb = readings(name)
    for side in (side_of(sch, pcb), side_of(sch)):
        report = parity.compare(side, pcb)
        assert report.findings == () and not any(report.summary.values())
    side = side_of(sch, pcb)
    assert set(side.components) == {"D1", "R1", "U1"} and side.fold == () and side.single_prefix == ""
    assert side.components["R1"].value == "330" and side.components["R1"].footprint == f"{name}:Mini_R_0603"
    assert side.components["R1"].pins == frozenset({"1", "2"}) and len(side.components["U1"].pins) == 32
    assert side.components["R1"].attributes == frozenset()
    assert side.nodes[("R1", "1")] == "LED_DRV" and side.nodes[("D1", "1")] == "GND"
    assert ("U1", "11") not in side.nodes  # a pin on no net has no node


def test_side_through_the_backend() -> None:
    sch, pcb = readings("blink")
    outcome = AltiumBackend().parity_side(sch, pcb)
    assert outcome.side is not None and outcome.side.nodes == side_of(sch, pcb).nodes
    assert outcome.evidence.level.value == "INFERRED" and "H-A-IMP-NETLIST" in outcome.evidence.hypotheses
    empty = dataclasses.replace(sch, circuit=Circuit())
    none = AltiumBackend().parity_side(empty, pcb)
    assert none.side is None and "no component" in none.message


def test_the_library_of_a_footprint_is_not_compared() -> None:
    """The schematic names the library by the model's file and the board by where the part came from."""
    assert footprint_name("parts:R_0603") == "R_0603" and footprint_name("R_0603") == "R_0603"
    assert footprint_name("a:b:R_0603") == "R_0603" and footprint_name("") == ""
    sch, pcb = schematic(), board()
    assert side_of(sch).components["R1"].footprint == "parts:R_0603"
    assert side_of(sch, pcb).components["R1"].footprint == "Placed.PcbLib:R_0603"
    assert codes(sch, pcb) == []
    # another footprint name is a difference, in the schematic's own spelling
    other = board(lib_ref="Placed.PcbLib:R_0805")
    assert side_of(sch, other).components["R1"].footprint == "parts:R_0603"
    assert {code for code, _ in codes(sch, other)} == {parity.MISMATCH}


def test_a_net_named_differently_is_one_net_when_its_pads_agree() -> None:
    """The import does not give a net the name Altium gave it on a hierarchical project: a net whose pads
    are the pads of one board net is that net."""
    renamed = {ref: tuple("NetD1_1" if n == "LED_A" else n for n in names) for ref, names in NETS.items()}
    sch, pcb = schematic(), board(renamed)
    side = side_of(sch, pcb)
    assert side.nodes[("R1", "2")] == "NetD1_1" and side.nodes[("D1", "1")] == "NetD1_1"
    assert side.nodes[("U1", "1")] == "VIN" and codes(sch, pcb) == []
    assert side_of(sch).nodes[("R1", "2")] == "LED_A"
    assert board_names({("R1", "2"): "LED_A"}, {("R1", "2"): {"NetD1_1"}}) == {"LED_A": "NetD1_1"}


def test_split_joined_and_open_nets_stay_differences() -> None:
    sch = schematic()
    # split: R1-2 of LED_A is on another net of the board
    split = board(NETS | {"R1": ("VIN", "OTHER")})
    assert codes(sch, split) == [(parity.NET_CONFLICT, "R1-2")]
    assert board_names(dict(side_of(sch).nodes), {("R1", "2"): {"OTHER"}, ("D1", "1"): {"LED_A"}}) == {}
    # joined: the board puts LED_A and GND on one net
    joined = board({"R1": ("VIN", "X"), "D1": ("X", "X"), "U1": ("VIN", "X")})
    assert {code for code, _ in codes(sch, joined)} == {parity.NET_CONFLICT}
    # open: a pad on no net is no name to take
    opened = board(NETS | {"R1": ("VIN", "")})
    assert codes(sch, opened) == [(parity.NET_CONFLICT, "R1-2")]
    # two pads of one number on two nets give no name either
    assert board_names({("R1", "2"): "LED_A"}, {("R1", "2"): {"A", "B"}}) == {}
    assert board_names({("R1", "2"): "LED_A"}, {}) == {}


def test_pins_name_pads_through_the_map_when_the_component_holds_one() -> None:
    """``Component.pin_pad_map`` decides which pads a pin names; without it a pin names its own number."""
    plain = schematic().circuit.components[0]
    assert pads_of(plain) == {"1": ("1",), "2": ("2",)}
    mapped = dataclasses.replace(plain, pin_pad_map=(("2", "A"), ("2", "K")))
    assert pads_of(mapped) == {"1": ("1",), "2": ("A", "K")}
    sch = schematic(pin_pad_map=(("2", "A"), ("2", "K")))
    side = side_of(sch)
    assert side.components["R1"].pins == frozenset({"1", "A", "K"})
    assert side.nodes[("R1", "A")] == "LED_A" and side.nodes[("R1", "K")] == "LED_A"
    assert ("R1", "2") not in side.nodes
    # a pin without a number names no pad, and a component without a designator is no key
    blank = dataclasses.replace(plain, pins=(*plain.pins, Pin(id="pin_x", number="")))
    assert pads_of(blank) == pads_of(plain)
    nameless = dataclasses.replace(
        schematic(), circuit=Circuit(components=(dataclasses.replace(plain, ref=""),))
    )
    assert side_of(nameless).components == {}


def test_the_first_component_of_a_designator_stands_for_it() -> None:
    sch = schematic()
    first = sch.circuit.components[0]
    twice = dataclasses.replace(first, id="cmp_s_again", value="other")
    doubled = dataclasses.replace(
        sch, circuit=dataclasses.replace(sch.circuit, components=(*sch.circuit.components, twice))
    )
    assert side_of(doubled).components["R1"].value == "10k"
