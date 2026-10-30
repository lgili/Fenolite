# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import dataclasses
import random

import pytest

from fenolite.core.coords import Point
from fenolite.core.ids import new_id
from fenolite.model import Bus, BusMember, Circuit, Component, ExtBag, Net, Pin, PinRef, Track
from fenolite.model.canonical import dumps, loads


def test_entities_are_immutable() -> None:
    component = Component(id=new_id("cmp", random.Random(1)), ref="R1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        component.ref = "R2"  # type: ignore[misc]


def test_header_defaults() -> None:
    pin = Pin(id=new_id("pin", random.Random(1)), number="1")
    assert (pin.native_ids, pin.provenance, pin.ext, pin.etype) == ({}, None, {}, "passive")


def test_extension_bag_survives_replace() -> None:
    bag = ExtBag(min_version="20241229", payload=(("locked", "yes"),))
    track = Track(
        id=new_id("trk", random.Random(2)),
        start=Point(0, 0),
        end=Point(1, 0),
        width=250_000,
        layer="F.Cu",
        ext={"kicad": bag},
    )
    wider = dataclasses.replace(track, width=300_000)
    assert wider.ext == {"kicad": bag} and wider.width == 300_000 and wider.id == track.id


def test_net_members_are_pin_refs() -> None:
    net = Net(
        id=new_id("net", random.Random(3)), name="GND", members=(PinRef("cmp_x", "2"), PinRef("cmp_y", "1"))
    )
    assert sorted(net.members)[0] == PinRef("cmp_x", "2")


def test_no_connect_marks_are_the_last_field_and_empty_by_default() -> None:
    assert [f.name for f in dataclasses.fields(Circuit)][-1] == "no_connects"
    assert Circuit().no_connects == ()


def test_no_connect_default_is_omitted_and_an_old_file_loads() -> None:
    component = Component(id=new_id("cmp", random.Random(1)), ref="U1")
    old = dumps(Circuit(components=(component,)))
    assert "no_connects" not in old
    loaded = loads(old, Circuit)
    assert loaded.no_connects == () and dumps(loaded) == old


def test_no_connect_marks_round_trip_as_text() -> None:
    component = Component(id=new_id("cmp", random.Random(1)), ref="U1")
    marks = (PinRef(component.id, "11"), PinRef(component.id, "12"))
    circuit = Circuit(components=(component,), no_connects=marks)
    text = dumps(circuit)
    assert '"no_connects"' in text
    assert loads(text, Circuit).no_connects == marks


# --- buses (change c0043, "Buses in the circuit model") -------------------------------------------------


def test_bus_default_is_omitted_and_an_old_file_loads() -> None:
    component = Component(id=new_id("cmp", random.Random(1)), ref="U1")
    old = dumps(Circuit(components=(component,)))
    assert "buses" not in old
    loaded = loads(old, Circuit)
    assert loaded.buses == () and dumps(loaded) == old


def test_bus_members_keep_their_order() -> None:
    rng = random.Random(4)
    d0 = Net(id=new_id("net", rng), name="D0")
    d1 = Net(id=new_id("net", rng), name="D1")
    bus = Bus(id=new_id("bus", rng), name="D", members=(BusMember(1, d1.id), BusMember(0, d0.id)))
    circuit = Circuit(nets=(d0, d1), buses=(bus,))
    loaded = loads(dumps(circuit), Circuit)
    assert loaded.buses == (bus,) and [m.index for m in loaded.buses[0].members] == [1, 0]


def test_bus_prefix() -> None:
    assert new_id("bus", random.Random(1)).startswith("bus_")
    with pytest.raises(ValueError, match="unknown id prefix"):
        new_id("busx", random.Random(1))


# --- blocks and ports (change c0251, "Block instances in the circuit model") ------------------------------


def _block_design() -> tuple[object, object]:
    from fenolite.model import BlockParam, Module, Port

    rng = random.Random(5)
    v33 = Net(id=new_id("net", rng), name="3V3")
    gnd = Net(id=new_id("net", rng), name="GND")
    module = Module(
        id=new_id("mod", rng),
        path="buck1",
        block="buck",
        params=(BlockParam("current", "quantity", "2A"), BlockParam("vout", "quantity", "3.3V")),
    )
    port = Port(
        id=new_id("prt", rng),
        name="VOUT",
        owner=module.id,
        kind="power",
        direction="out",
        members={"hv": v33.id, "lv": gnd.id},
    )
    return Circuit(nets=(v33, gnd), modules=(module,), ports=(port,)), (module, port)


def test_block_instance_round_trip(tmp_path: object) -> None:
    from pathlib import Path

    from fenolite.model import Design
    from fenolite.model.canonical import dump_dir, load_dir

    circuit, (module, port) = _block_design()
    assert isinstance(circuit, Circuit)
    design = dataclasses.replace(Design.new("b", seed=6), circuit=circuit)
    root = Path(str(tmp_path))
    dump_dir(design, root)
    loaded = load_dir(root)
    assert loaded.circuit.modules == (module,) and loaded.circuit.ports == (port,)
    text = (root / "circuit.json").read_text(encoding="utf-8")
    assert '"ports"' in text and '"block": "buck"' in text


def test_block_fields_are_omitted_and_an_old_file_loads() -> None:
    from fenolite.model import Module

    plain = Module(id=new_id("mod", random.Random(7)), path="power")
    old = dumps(Circuit(modules=(plain,)))
    assert "block" not in old and "params" not in old and "ports" not in old
    loaded = loads(old, Circuit)
    assert loaded.modules[0].block == "" and loaded.modules[0].params == () and loaded.ports == ()
    assert dumps(loaded) == old


def test_block_params_refused() -> None:
    from fenolite.model import BlockParam, Module

    with pytest.raises(ValueError, match="one name"):
        Module(
            id=new_id("mod", random.Random(8)),
            path="buck1",
            block="buck",
            params=(BlockParam("vout", "int", "1"), BlockParam("vout", "int", "2")),
        )
    with pytest.raises(ValueError, match="type"):
        BlockParam("vout", "float", "3.3")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="ordered"):
        Module(
            id=new_id("mod", random.Random(8)),
            path="buck1",
            block="buck",
            params=(BlockParam("b", "int", "1"), BlockParam("a", "int", "2")),
        )


def test_port_values_refused() -> None:
    from fenolite.model import Port

    with pytest.raises(ValueError, match="both"):
        Port(id=new_id("prt", random.Random(9)), name="EN", owner="mod_x", kind="net", direction="both")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="name and a kind"):
        Port(id=new_id("prt", random.Random(9)), name="", owner="mod_x", kind="net")
    assert new_id("prt", random.Random(1)).startswith("prt_")
