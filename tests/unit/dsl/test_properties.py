# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""User properties of DSL parts (capability design-dsl, "User properties in the DSL"; change c0027)."""

from __future__ import annotations

import pytest

from fenolite.dsl import DslError, Part
from fenolite.dsl import part as dsl_part
from fenolite.lens import build as lens_build


def test_properties_recorded_in_name_order() -> None:
    r1 = Part("R1", "Mini:Mini_R", properties={"Supplier code": "S-1", "Part number": "PN-330"})
    assert dict(r1.properties) == {"Part number": "PN-330", "Supplier code": "S-1"}
    assert list(r1.properties) == ["Part number", "Supplier code"]
    with pytest.raises(TypeError):
        r1.properties["X"] = "y"  # type: ignore[index]


def test_no_properties() -> None:
    assert dict(Part("R1", "Mini:Mini_R").properties) == {}
    assert dict(Part("R1", "Mini:Mini_R", properties={}).properties) == {}


def test_reserved_names_in_any_letter_case() -> None:
    with pytest.raises(DslError, match="'datasheet'.*'Datasheet'"):
        Part("R1", "Mini:Mini_R", properties={"datasheet": "x"})
    with pytest.raises(DslError, match="'ki_'"):
        Part("R2", "Mini:Mini_R", properties={"KI_keywords": "x"})
    for name in ("Reference", "VALUE", "footprint", "Description"):
        with pytest.raises(DslError, match="reserved name"):
            Part("R3", "Mini:Mini_R", properties={name: "x"})


def test_path_property_is_not_the_scripts() -> None:
    with pytest.raises(DslError, match="'fenolite.'"):
        Part("R1", "Mini:Mini_R", properties={"fenolite.path": "R9"})


def test_values_are_printable_text() -> None:
    with pytest.raises(DslError, match="'Qty'"):
        Part("R1", "Mini:Mini_R", properties={"Qty": 2})  # type: ignore[dict-item]
    with pytest.raises(DslError, match="'Part number'"):
        Part("R2", "Mini:Mini_R", properties={"Part number": "A\nB"})
    assert Part("R3", "Mini:Mini_R", properties={"Note": ""}).properties["Note"] == ""
    assert Part("R4", "Mini:Mini_R", properties={"Code": 'S-1 "q" \\ µ'}).properties["Code"] == 'S-1 "q" \\ µ'


@pytest.mark.parametrize("name", ["", " MPN", "MPN ", "M\tPN"])
def test_bad_names(name: str) -> None:
    with pytest.raises(DslError, match="property name"):
        Part("R1", "Mini:Mini_R", properties={name: "x"})


def test_not_a_mapping() -> None:
    with pytest.raises(DslError, match="mapping"):
        Part("R1", "Mini:Mini_R", properties=[("MPN", "x")])  # type: ignore[arg-type]
    with pytest.raises(DslError, match="str name"):
        Part("R1", "Mini:Mini_R", properties={1: "x"})  # type: ignore[dict-item]


def test_names_that_differ_only_in_case() -> None:
    with pytest.raises(DslError, match="'MPN'.*'mpn'"):
        Part("R1", "Mini:Mini_R", properties={"MPN": "a", "mpn": "b"})


def test_reserved_sets_agree() -> None:
    assert dsl_part.RESERVED_PROPERTIES == lens_build.RESERVED_PROPERTIES
    assert dsl_part.RESERVED_PREFIXES == lens_build.RESERVED_PREFIXES


def test_not_re_exported() -> None:
    import fenolite.dsl as dsl

    assert not hasattr(dsl, "RESERVED_PROPERTIES") and not hasattr(dsl, "RESERVED_PREFIXES")
