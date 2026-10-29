# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Blocks: the decorator, instances, the builder, local names and board refs (capability design-dsl,
"Block decorator", "Block instances", "Block builder", "Board refs in blocks", "Block instance handles",
"Block names are unique" and "Design structure and names"; change c0251)."""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

import pytest

from fenolite.dsl import Design, DslError, Net, Part, block, connect, mm, to_model
from fenolite.dsl.block import Block, BlockDef, BlockInstance
from fenolite.dsl.lock import assign_refs, make_lock

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "blocks" / "design.py"
R = "Fenolite:Resistor"
FP = "Fenolite:Chip_0603"


def example() -> Design:
    return runpy.run_path(str(EXAMPLE))["design"]


@block
def channel(b: Any, *, r_en: object = "10k") -> None:
    vin = b.port("VIN", direction="in")
    fb = b.net("FB")
    r = b.part("R_EN", R, footprint=FP, value=str(r_en))
    connect(vin, r[1])
    connect(fb, r[2])


def test_bad_signature() -> None:
    def bad(b: object, vout: object) -> None: ...

    with pytest.raises(DslError, match=r"bad.*vout.*keyword-only"):
        block(bad)


def test_variadic_keywords_refused() -> None:
    def bad(b: object, **kw: object) -> None: ...

    with pytest.raises(DslError, match="bad"):
        block(bad)
    with pytest.raises(DslError, match="builder"):
        block(name="nob")(lambda: None)  # type: ignore[arg-type]


def test_named_block_and_definition() -> None:
    @block(name="buck")
    def anything(b: object) -> None: ...

    assert isinstance(anything, BlockDef) and anything.name == "buck"
    with pytest.raises(DslError, match="block name"):
        block(name="no good")(lambda b: None)


def test_direct_call_refused() -> None:
    design = Design("t")
    with pytest.raises(DslError, match=r"design\.use"):
        channel(design)


def test_instances_two_without_collision() -> None:
    model = to_model(example())
    paths = {c.properties["fenolite.path"]: c.ref for c in model.circuit.components}
    names = {net.name for net in model.circuit.nets}
    assert {"ch0/R_EN", "ch1/R_EN"} <= set(paths) and paths["ch0/R_EN"] != paths["ch1/R_EN"]
    assert {"ch0/FB", "ch1/FB"} <= names


def test_instance_is_a_module_and_handle() -> None:
    design = Design("t")
    inst = design.use(channel, "ch0")
    assert isinstance(inst, BlockInstance) and isinstance(inst.module, Block)
    assert inst.path == "ch0" and inst.block is channel and dict(inst.params) == {"r_en": "10k"}
    assert inst.part("R_EN").path == "ch0/R_EN" and inst.port("VIN") is inst.VIN
    assert design.modules["ch0"] is inst.module
    with pytest.raises(DslError, match="no part named X"):
        inst.part("X")
    with pytest.raises(DslError, match="no port GND"):
        inst.port("GND")
    with pytest.raises(AttributeError, match="no port GND"):
        _ = inst.GND
    with pytest.raises(TypeError):
        inst.params["r_en"] = "1k"  # type: ignore[index]


def test_duplicate_local_name() -> None:
    @block
    def twice(b: Any) -> None:
        b.part("R_EN", R)
        b.part("R_EN", R)

    with pytest.raises(DslError, match=r"R_EN.*twice.*u1/R_EN"):
        Design("t").use(twice, "u1")


def test_duplicate_port_and_net_names() -> None:
    @block
    def clash(b: Any) -> None:
        b.port("VIN")
        b.net("VIN")

    with pytest.raises(DslError, match="VIN is taken by a port"):
        Design("t").use(clash, "u1")


def test_return_value_refused() -> None:
    @block
    def returns(b: Any) -> None:
        return b  # type: ignore[no-any-return]

    with pytest.raises(DslError, match="returns None"):
        Design("t").use(returns, "u1")


def test_two_functions_named_buck() -> None:
    def first(b: object) -> None: ...

    def second(b: object) -> None: ...

    one, two = block(name="buck")(first), block(name="buck")(second)
    design = Design("t")
    design.use(one, "a")
    design.use(one, "b")  # two instances of one definition are allowed
    with pytest.raises(DslError, match="buck"):
        design.use(two, "c")


def test_local_net_of_a_nested_block() -> None:
    @block
    def buck(b: Any) -> None:
        fb = b.net("FB")
        r = b.part("R", R, footprint=FP)
        connect(fb, r[1])

    @block
    def power(b: Any) -> None:
        b.use(buck, "buck1")

    design = Design("t")
    design.use(power, "power")
    names = {net.name for net in to_model(design).circuit.nets}
    assert "power/buck1/FB" in names
    assert "power/buck1/R" in design.parts


def test_global_net_inside_a_block_keeps_its_name() -> None:
    gnd = Net("GND")

    @block
    def uses_gnd(b: Any) -> None:
        connect(gnd, b.part("R", R, footprint=FP)[1])

    design = Design("t")
    design.use(uses_gnd, "u1")
    assert {net.name for net in to_model(design).circuit.nets} == {"GND"}


def test_refs_allocated_and_explicit() -> None:
    @block
    def chan(b: Any, *, first: bool = False) -> None:
        b.part("R_EN", R, footprint=FP)
        if first:
            b.part("R_SET", R, footprint=FP, ref="R90")

    design = Design("t")
    design.use(chan, "ch0", first=True)
    design.use(chan, "ch1")
    model = to_model(design)
    refs = {c.properties["fenolite.path"]: c.ref for c in model.circuit.components}
    assert refs["ch0/R_SET"] == "R90"
    assert refs["ch0/R_EN"].startswith("R") and refs["ch1/R_EN"].startswith("R")
    assert refs["ch0/R_EN"] != refs["ch1/R_EN"]


def test_refs_from_the_lock() -> None:
    design = Design("t")
    design.use(channel, "ch0")
    design.use(channel, "ch1")
    lock = make_lock("t", {"refs": {"ch1/R_EN": "R17"}})
    found = assign_refs(design, lock, moves={})
    assert found.refs["ch1/R_EN"] == "R17" and found.refs["ch0/R_EN"] == "R1"


def test_part_added_by_ref_becomes_the_local_name() -> None:
    @block
    def adds(b: Any) -> None:
        b.add(Part("R7", "Mini:Mini_R"))

    design = Design("t")
    design.use(adds, "a")
    design.use(adds, "b")
    model = to_model(design)
    refs = {c.properties["fenolite.path"]: c.ref for c in model.circuit.components}
    assert set(refs) == {"a/R7", "b/R7"} and sorted(refs.values()) == ["R1", "R2"]


def test_failed_function_leaves_the_block_added() -> None:
    @block
    def fails(b: Any) -> None:
        b.part("R", R)
        raise DslError("boom")

    design = Design("t")
    with pytest.raises(DslError, match="boom"):
        design.use(fails, "u1")
    assert "u1" in design.modules and "u1/R" in design.parts


def test_plain_module_scripts_unchanged() -> None:
    from fenolite.model import canonical

    blink = runpy.run_path(str(ROOT / "examples" / "blink_2layer" / "design.py"))["design"]
    texts = canonical.dump_texts(to_model(blink))
    assert '"block"' not in texts["circuit.json"] and '"ports"' not in texts["circuit.json"]
    assert "prt_" not in texts["circuit.json"]


def test_placement_inside_a_block() -> None:
    design = example()
    assert design.parts["ch1/R_EN"].request is not None
    assert design.parts["ch1/R_EN"].request.x == mm(40).nm
