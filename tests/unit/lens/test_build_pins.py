# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pins and pads in a build (capability design-dsl, "Pins and pads in a build"; change c0011)."""

from __future__ import annotations

from pathlib import Path

from _buildhelp import authored, blink, build, codes

from fenolite.dsl import Design, Net, Part, connect, mm
from fenolite.dsl.convert import key_id


def one_part(tmp: Path, pins: list[tuple[str, str]], pads: list[str]) -> tuple[Design, Part, Path]:
    folder = authored(tmp, {"S": pins}, {"F": pads})
    d = Design("t")
    d.board(mm(20), mm(20))
    u1 = Part("U1", "T:S", footprint="T:F")
    d.add(u1)
    u1.place(mm(5), mm(5))
    return d, u1, folder


def test_a_name_joins_every_pin(tmp_path: Path) -> None:
    pins = [(str(n), "GND" if n in (4, 12) else f"P{n}") for n in range(1, 13)]
    d, u1, folder = one_part(tmp_path, pins, [str(n) for n in range(1, 13)])
    gnd = connect(Net("GND"), u1["GND"])
    d.add(gnd)
    out = build(d, project_dir=folder)
    net = next(n for n in out.design.circuit.nets if n.name == "GND")
    uid = key_id("component", "U1")
    assert [(m.component_id, m.pin) for m in net.members] == [(uid, "12"), (uid, "4")]
    pads = {p.number: p.net_id for p in out.design.board.footprints[0].pads}  # type: ignore[union-attr]
    assert pads["4"] == pads["12"] == net.id


def test_unknown_pin() -> None:
    d = blink()
    connect(Net("X_NET"), d.parts["R1"]["X"])
    out = build(d)
    assert "build.unknown-pin" in codes(out) and out.files == {}
    (found,) = [i for i in out.issues if i.code == "build.unknown-pin"]
    assert "R1" in found.message and "X" in found.message


def test_one_pin_on_two_nets_by_name(tmp_path: Path) -> None:
    d, u1, folder = one_part(tmp_path, [("10", "GND"), ("11", "X")], ["10", "11"])
    connect(Net("GND"), u1["GND"])
    connect(Net("SENSE"), u1["10"])
    out = build(d, project_dir=folder)
    assert "build.pin-on-two-nets" in codes(out) and out.files == {}
    assert any("U1 pin 10" in i.message for i in out.issues)


def test_pin_without_pad(tmp_path: Path) -> None:
    d, u1, folder = one_part(tmp_path, [("1", "A"), ("2", "B"), ("3", "C")], ["1", "2"])
    connect(Net("N"), u1["3"])
    assert "build.pin-without-pad" in codes(build(d, project_dir=folder))
    d2, _, folder2 = one_part(tmp_path / "b", [("1", "A"), ("2", "B"), ("3", "C")], ["1", "2"])
    found = codes(build(d2, project_dir=folder2))
    assert "build.unused-pin-without-pad" in found and "build.pin-without-pad" not in found


def test_explicit_pin_pad_map_applies_net_to_physical_pad(tmp_path: Path) -> None:
    d, u1, folder = one_part(tmp_path, [("1", "A"), ("2", "B")], ["1", "2"])
    u1.pad_map = {"1": "2", "2": "1"}
    connect(Net("N"), u1["1"])
    out = build(d, project_dir=folder)
    net = next(n for n in out.design.circuit.nets if n.name == "N")
    pads = {pad.number: pad.net_id for pad in out.design.board.footprints[0].pads}  # type: ignore[union-attr]
    assert pads == {"1": None, "2": net.id}
    component = next(c for c in out.design.circuit.components if c.ref == "U1")
    assert component.pin_pad_map == (("1", "2"), ("2", "1"))


def test_pin_pad_map_source_must_exist(tmp_path: Path) -> None:
    d, u1, folder = one_part(tmp_path, [("1", "A")], ["1"])
    u1.pad_map = {"9": "1"}
    out = build(d, project_dir=folder)
    assert "build.pin-pad-map-invalid" in codes(out) and out.files == {}


def test_a_number_wins_over_a_name(tmp_path: Path) -> None:
    d, u1, folder = one_part(tmp_path, [("1", "2"), ("2", "A")], ["1", "2"])
    connect(Net("SIG"), u1["2"])
    out = build(d, project_dir=folder)
    net = next(n for n in out.design.circuit.nets if n.name == "SIG")
    assert [m.pin for m in net.members] == ["2"]
    assert codes(out).count("build.pin-ambiguous") == 1


def test_pad_without_pin(tmp_path: Path) -> None:
    d, _, folder = one_part(tmp_path, [("1", "A"), ("2", "B")], ["1", "2", "3", ""])
    out = build(d, project_dir=folder)
    found = [i for i in out.issues if i.code == "build.pad-without-pin"]
    assert len(found) == 1 and "pad 3" in found[0].message and out.files


def test_names_that_differ_only_in_case() -> None:
    d = blink()
    d.add(Net("gnd"))
    out = build(d)
    assert "build.name-case-collision" in codes(out) and out.files == {}


def test_members_hold_pin_numbers() -> None:
    out = build(blink())
    gnd = next(n for n in out.design.circuit.nets if n.name == "GND")
    assert sorted(m.pin for m in gnd.members) == ["1", "10"]
    u1 = next(c for c in out.design.circuit.components if c.ref == "U1")
    assert len(u1.pins) == 32 and u1.pins[0].id == key_id("pin", "U1", u1.pins[0].number)


def test_several_pads_for_one_pin(tmp_path: Path) -> None:
    """Scenario "Two pads for one pin" (change c0123)."""
    d, u1, folder = one_part(tmp_path, [("1", "A"), ("2", "B"), ("3", "GND")], ["1", "2", "3", "EP"])
    u1.pad_map = {"3": ("3", "EP")}
    connect(Net("GND"), u1["3"])
    out = build(d, project_dir=folder)
    assert "build.pad-without-pin" not in codes(out) and "build.pin-pad-map-invalid" not in codes(out)
    net = next(n for n in out.design.circuit.nets if n.name == "GND")
    assert [m.pin for m in net.members] == ["3"]
    pads = {pad.number: pad.net_id for pad in out.design.board.footprints[0].pads}  # type: ignore[union-attr]
    assert pads == {"1": None, "2": None, "3": net.id, "EP": net.id}
    component = next(c for c in out.design.circuit.components if c.ref == "U1")
    assert component.pin_pad_map == (("3", "3"), ("3", "EP"))
    assert out.files and not [i for i in out.issues if i.severity == "error"]


def test_missing_pad_among_several(tmp_path: Path) -> None:
    """Scenario "Missing pad among several"."""
    d, u1, folder = one_part(tmp_path, [("1", "A"), ("3", "GND")], ["1", "3"])
    u1.pad_map = {"3": ("3", "TAB")}
    connect(Net("GND"), u1["3"])
    out = build(d, project_dir=folder)
    found = [i for i in out.issues if i.code == "build.pin-pad-map-invalid"]
    assert [i.severity for i in found] == ["error"] and "TAB" in found[0].message and out.files == {}


def test_a_pad_of_two_pins_among_several(tmp_path: Path) -> None:
    d, u1, folder = one_part(tmp_path, [("1", "A"), ("3", "GND")], ["1", "3", "EP"])
    u1.pad_map = {"3": ("3", "1")}  # the pad 1 is the pad of the pin 1, which the map does not move
    out = build(d, project_dir=folder)
    assert "build.pin-pad-map-invalid" in codes(out) and out.files == {}
