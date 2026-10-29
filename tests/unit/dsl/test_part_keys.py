# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parts without a ref: keys and reference prefixes (capability design-dsl, "Parts without a ref",
"Reference prefixes" and MODIFIED "Design structure and names"; change c0249).

The device of c0248 is a third prefix source; until it is merged the scenarios use catalog symbols and
``prefix=``."""

from __future__ import annotations

import pytest

from fenolite.dsl import Design, DslError, Module, Part


def test_key_from_the_prefix() -> None:
    design = Design("t")
    buck = Module("buck")
    design.add(buck)
    u = buck.part(lib_id="Example:BUCK_6V_2A", prefix="U")
    assert u.path == "buck/U" and u.ref is None and u.explicit_ref is None and u.key == "U"
    assert design.parts["buck/U"] is u


def test_a_second_unnamed_part() -> None:
    design = Design("t")
    buck = Module("buck")
    design.add(buck)
    first = buck.part(lib_id="Fenolite:Capacitor", footprint="Fenolite:Chip_0805")
    with pytest.raises(DslError, match=r"buck/C.*name="):
        buck.part(lib_id="Fenolite:Capacitor", footprint="Fenolite:Chip_0805")
    assert first.path == "buck/C" and list(design.parts) == ["buck/C"]
    second = buck.part(name="c_out", lib_id="Fenolite:Capacitor", footprint="Fenolite:Chip_0805")
    assert second.path == "buck/c_out" and first.path == "buck/C"


def test_a_second_unnamed_part_at_the_top_and_beside_an_explicit_key() -> None:
    design = Design("t")
    design.part(lib_id="Fenolite:Resistor")
    with pytest.raises(DslError, match=r"design t: the path R is taken by an unnamed part; give this part"):
        design.part(lib_id="Fenolite:Resistor")
    with pytest.raises(DslError, match="name="):
        design.add(Part("R", "Fenolite:Resistor"))  # an explicit ref equal to an unnamed part's key


def test_a_second_unnamed_part_in_a_module_not_yet_added() -> None:
    sub = Module("sub")
    sub.part(lib_id="Fenolite:Inductor")
    with pytest.raises(DslError, match="module sub: the path sub/L"):
        sub.add(Part(lib_id="Fenolite:Inductor"))


def test_name_and_explicit_ref() -> None:
    design = Design("t")
    part = design.part("R5", name="pull_sda", lib_id="Fenolite:Resistor", footprint="Fenolite:Chip_0603")
    assert part.path == "pull_sda" and part.ref == "R5" and part.explicit_ref == "R5"


def test_path_from_a_name() -> None:
    design = Design("t")
    sensor = Module("sensor")
    design.add(sensor)
    part = sensor.part(name="R_pull_sda", lib_id="Fenolite:Resistor")
    assert part.path == "sensor/R_pull_sda" and part.ref is None


def test_prefix_from_the_catalog_symbol() -> None:
    design = Design("t")
    part = design.part(lib_id="Fenolite:Inductor", footprint="Fenolite:Chip_0805")
    assert part.path == "L" and part.prefix == "L"


def test_no_prefix_known() -> None:
    design = Design("t")
    with pytest.raises(DslError, match="give a ref, a prefix or a device"):
        design.part(lib_id="Device:Crystal", footprint="Crystal:HC49")
    assert not design.parts
    with pytest.raises(DslError, match="give a ref, a prefix or a device"):
        Part(lib_id="Fenolite:No_Such_Symbol")


def test_prefix_given() -> None:
    design = Design("t")
    part = design.part(lib_id="Device:Crystal", footprint="Crystal:HC49", prefix="Y")
    assert part.path == "Y" and part.prefix == "Y"
    tuned = Part(lib_id="Fenolite:Resistor", prefix="RV")
    assert tuned.prefix == "RV" and tuned.key == "RV"


@pytest.mark.parametrize("prefix", ["r", "1R", "R1", "", "R-"])
def test_invalid_prefix(prefix: str) -> None:
    with pytest.raises(DslError, match="prefix"):
        Part(lib_id="Fenolite:Resistor", prefix=prefix)


@pytest.mark.parametrize("name", ["a b", "", "x/y"])
def test_invalid_name(name: str) -> None:
    with pytest.raises(DslError, match="part name"):
        Part(lib_id="Fenolite:Resistor", name=name)


def test_lib_id_is_still_required() -> None:
    with pytest.raises(DslError, match="lib_id"):
        Part("R1")
    with pytest.raises(DslError, match="lib_id"):
        Part(prefix="R")


def test_explicit_refs_keep_their_paths() -> None:
    design = Design("t")
    power = Module("power")
    ldo = Module("ldo")
    power.add(ldo)
    design.add(power)
    c1 = Part("C1", "Mini:Mini_R")
    ldo.add(c1)
    assert c1.path == "power/ldo/C1" and c1.key == "C1" and c1.prefix is None
    with pytest.raises(DslError, match="two components have the path"):
        ldo.add(Part("C1", "Mini:Mini_R"))


def test_messages_name_the_path_before_the_build() -> None:
    design = Design("t")
    part = design.part(lib_id="Fenolite:Resistor")
    part.place("1mm", "1mm")
    with pytest.raises(DslError, match="part R is already placed"):
        part.place("1mm", "1mm")
