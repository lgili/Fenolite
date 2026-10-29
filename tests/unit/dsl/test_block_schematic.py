# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block-local schematic groups and the sheet names of ports (capability design-dsl, "Block schematic groups
in the DSL", "Block schematic groups are not composition intent", "Block-local groups in Altium
composition" and "Sheet names of block ports"; change c0269)."""

from __future__ import annotations

from typing import Any

import pytest

from fenolite.dsl import (
    I2C,
    Design,
    DslError,
    Net,
    block,
    block_schematics,
    connect,
    schematic_composition,
    schematic_group,
    to_model,
)
from fenolite.schematic.block_sheets import SheetGroup, port_pins, sheet_name

R = "Fenolite:Resistor"
C = "Fenolite:Capacitor"
FP = "Fenolite:Chip_0603"


def body_of_filter(b: Any, grouped: bool) -> None:
    inp = b.port("IN", direction="in")
    out = b.port("OUT", direction="out")
    gnd = b.port("GND", direction="in")
    r1 = b.part("R", R, footprint=FP, value="10k")
    c1 = b.part("C", C, footprint=FP, value="100n")
    connect(inp, r1[1])
    connect(out, r1[2], c1[1])
    connect(gnd, c1[2])
    if grouped:
        b.schematic(schematic_group("chain", r1, c1, flow="left-to-right", title="Filter", anchor=r1))


@block
def rc_filter(b: Any) -> None:
    body_of_filter(b, True)


@block(name="rc_filter")
def rc_filter_plain(b: Any) -> None:
    body_of_filter(b, False)


def filters(grouped: bool = True) -> Design:
    design = Design("filters")
    src, dst, gnd = Net("SRC"), Net("DST"), Net("GND")
    for name in ("f1", "f2"):
        made = design.use(rc_filter if grouped else rc_filter_plain, name)
        connect(src, made.IN)
        connect(dst if name == "f1" else Net("DST2"), made.OUT)
        connect(gnd, made.GND)
    return design


def run(body: Any) -> None:
    @block
    def probe(b: Any) -> None:
        body(b)

    Design("probe").use(probe, "p")


def test_groups_reach_every_instance() -> None:
    design = filters()
    found = block_schematics(design)
    assert [(b.path, b.block) for b in found] == [("f1", "rc_filter"), ("f2", "rc_filter")]
    for item in found:
        assert item.groups == (
            SheetGroup("chain", (f"{item.path}/R", f"{item.path}/C"), "Filter", f"{item.path}/R", None),
        )
    assert to_model(filters()) == to_model(filters(grouped=False))


def test_anchor_first_and_local_names() -> None:
    def body(b: Any) -> None:
        r = b.part("R", R, footprint=FP)
        b.part("C", C, footprint=FP)
        b.schematic(schematic_group("g", "C", r, anchor=r, flow="top-to-bottom"))
        assert b.schematic_groups[0].members == ("R", "C")
        assert b.schematic_groups[0].flow == "top-to-bottom"
        assert b.schematic_groups[0].title == "g"

    run(body)


def test_part_of_a_nested_block_refused() -> None:
    @block
    def inner(b: Any) -> None:
        b.part("R", R, footprint=FP)

    def body(b: Any) -> None:
        b.use(inner, "inner")
        b.schematic(schematic_group("g", "inner/R"))

    with pytest.raises(DslError, match=r"inner/R.*a group holds the block's own parts"):
        run(body)

    def handle(b: Any) -> None:
        nested = b.use(inner, "inner")
        b.schematic(schematic_group("g", nested.part("R")))

    with pytest.raises(DslError, match=r"p/inner/R.*own parts"):
        run(handle)


def test_cycle_refused() -> None:
    def body(b: Any) -> None:
        r1 = b.part("R", R, footprint=FP)
        c1 = b.part("C", C, footprint=FP)
        b.schematic(schematic_group("a", r1, after="b"), schematic_group("b", c1, after="a"))

    with pytest.raises(DslError, match=r"block p \(probe\).*a and b"):
        run(body)


def test_after_moves_a_group() -> None:
    def body(b: Any) -> None:
        r1 = b.part("R", R, footprint=FP)
        c1 = b.part("C", C, footprint=FP)
        b.schematic(schematic_group("a", r1, after="b"), schematic_group("b", c1))
        assert [g.key for g in b.schematic_groups] == ["b", "a"]

    run(body)


@pytest.mark.parametrize(
    ("groups", "message"),
    [
        (lambda r, c: (schematic_group("bad key", r),), "must match"),
        (lambda r, c: (schematic_group("g", r), schematic_group("g", c)), "used twice"),
        (lambda r, c: (schematic_group("g", r), schematic_group("h", r)), "in the schematic groups g and h"),
        (lambda r, c: (schematic_group("g", r, anchor=c),), "anchor C is not a member"),
        (lambda r, c: (schematic_group("g", r, after="x"),), "names no group"),
        (lambda r, c: (schematic_group("g", r, flow="diagonal"),), "flow 'diagonal'"),
        (lambda r, c: (schematic_group("g"),), "has no member"),
        (lambda r, c: (schematic_group("g", 3),), "a member is a part"),
    ],
)
def test_refusals_name_the_block(groups: Any, message: str) -> None:
    def body(b: Any) -> None:
        r1 = b.part("R", R, footprint=FP)
        c1 = b.part("C", C, footprint=FP)
        b.schematic(*groups(r1, c1))

    with pytest.raises(DslError, match=message) as caught:
        run(body)
    assert "block p (probe)" in str(caught.value)


def test_second_call_refused() -> None:
    def body(b: Any) -> None:
        r1 = b.part("R", R, footprint=FP)
        b.schematic(schematic_group("g", r1))
        b.schematic()

    with pytest.raises(DslError, match="second time"):
        run(body)


def test_clash_with_an_interface_member() -> None:
    def body(b: Any) -> None:
        b.port("I2C", I2C)
        b.port("I2C_sda")

    with pytest.raises(DslError, match=r"I2C_sda.*the port I2C\b"):
        run(body)


def test_sheet_names() -> None:
    assert sheet_name("VIN", "net", "net") == "VIN"
    assert sheet_name("I2C", "sda", "i2c") == "I2C_sda"

    @block
    def sensor(b: Any) -> None:
        bus = b.port("I2C", I2C)
        u = b.part("R1", R, footprint=FP)
        v = b.part("R2", R, footprint=FP)
        connect(bus.sda, u[1])
        connect(bus.scl, v[1])

    design = Design("s")
    design.use(sensor, "sen")
    pins = port_pins(to_model(design).circuit)["sen"]
    assert [p.name for p in pins] == ["I2C_scl", "I2C_sda"]


def test_library_block_composition_is_not_intent() -> None:
    assert schematic_composition(filters(), target=None) is None
    assert schematic_composition(filters(), target="kicad") is None


def test_local_groups_in_block_mode_altium() -> None:
    design = filters()
    design.schematic_layout(mode="blocks")
    intent = schematic_composition(design, target="altium")
    assert intent is not None
    keys = {b.key: b for b in intent.blocks}
    assert "f1" not in keys and "f2" not in keys
    assert keys["f1/chain"].members == ("f1/C", "f1/R")
    assert keys["f1/chain"].title == "Filter"
    assert keys["f1/chain"].anchor == "f1/R"


def test_design_level_block_takes_a_part_altium() -> None:
    design = filters()
    design.schematic_layout(mode="blocks")
    design.schematic_block("mine", members=[design.parts["f1/R"], design.parts["f1/C"]])
    intent = schematic_composition(design, target="altium")
    assert intent is not None
    keys = {b.key for b in intent.blocks}
    assert "f1/chain" not in keys and "mine" in keys and "f2/chain" in keys


LIBRARY_SCRIPT = """
from fenolite.dsl import Design, Net, block, connect, mm, schematic_group

design = Design("lib_block")
design.board(mm(40), mm(30))


@block
def rc_filter(b):
    inp = b.port("IN", direction="in")
    out = b.port("OUT", direction="out")
    r1 = b.part("R", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="10k")
    c1 = b.part("C", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="100n")
    connect(inp, r1[1])
    connect(out, r1[2], c1[1])
    b.schematic(schematic_group("chain", r1, c1, anchor=r1))


f1 = design.use(rc_filter, "f1")
j = design.part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54")
connect(Net("SRC"), j[1], f1.IN)
connect(Net("DST"), j[2], f1.OUT)
connect(Net("GND"), f1.part("C")[2])
"""


@pytest.mark.parametrize(
    "extra", [[], ["--target", "altium", "--altium-layout", "grid"]], ids=["kicad", "altium-grid"]
)
def test_library_block_in_every_mode(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, extra: list[str]
) -> None:
    import io
    import json

    import fenolite.cli.main as cli_main

    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    script = tmp_path / "design.py"
    script.write_text(LIBRARY_SCRIPT, encoding="utf-8")
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)
    code = cli_main.main(["build", str(script), "--out", str(tmp_path / "B"), "--dry-run", "--json", *extra])
    assert code == 0, stderr.getvalue()
    issues = json.loads(stdout.getvalue())["issues"]
    assert not [i for i in issues if i["severity"] == "error" or "composition" in i["message"]]
