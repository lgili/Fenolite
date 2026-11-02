# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native footprint identity and optional physical definition lookup (change c0318)."""

from __future__ import annotations

import inspect

import pytest

from fenolite.core.errors import FormatError
from fenolite.dsl import Design, DslError, Part, ohm, resistor, to_model
from fenolite.model import Component, canonical


def test_override_is_keyword_only_and_survives_canonical_roundtrip() -> None:
    assert inspect.signature(Part).parameters["footprint_definition"].kind is inspect.Parameter.KEYWORD_ONLY
    design = Design("variant")
    design.add(Part("R1", "Mini:R", footprint="Original:R", footprint_definition="Local:R_2"))
    (component,) = to_model(design).circuit.components
    assert component.lib_footprint_ref == "Original:R"
    assert component.footprint_definition_ref == "Local:R_2"
    assert canonical.loads(canonical.dumps(component), Component) == component


def test_default_is_omitted_and_old_model_loads_unchanged() -> None:
    design = Design("ordinary")
    design.add(Part("R1", "Mini:R", footprint="Original:R"))
    (component,) = to_model(design).circuit.components
    text = canonical.dumps(component)
    assert "footprint_definition_ref" not in text
    assert canonical.loads(text, Component).footprint_definition_ref == ""
    assert canonical.dumps(canonical.loads(text, Component)) == text
    with pytest.raises(FormatError, match="/footprint_definition_ref"):
        canonical.loads(text.rstrip()[:-1] + ', "footprint_definition_ref": 42}', Component)


@pytest.mark.parametrize("bad", [None, False, 3, [], {}])
def test_override_requires_string(bad: object) -> None:
    with pytest.raises(DslError, match="footprint_definition must be a string"):
        Part("R1", "Mini:R", footprint="Original:R", footprint_definition=bad)  # type: ignore[arg-type]


def test_override_requires_explicit_symbol_and_native_identity() -> None:
    with pytest.raises(DslError, match="requires explicit lib_id and footprint"):
        Part("R1", "Mini:R", footprint_definition="Local:R_2")
    for device in ("Fenolite:R_0603", resistor(ohm("1k"))):
        with pytest.raises(DslError, match="do not give it with device="):
            Part("R1", device=device, footprint_definition="Local:R_2")


def test_explicit_override_preserves_even_an_empty_native_identity() -> None:
    part = Part("R1", "Mini:R", footprint="", footprint_definition="Local:R_2")
    assert part.footprint == "" and part.footprint_definition == "Local:R_2"
    with pytest.raises(DslError, match="footprint must be a non-empty string"):
        Part("R1", "Mini:R", footprint="")
