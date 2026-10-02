# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``model.validate`` stage (capability verification-loop, "Model validation stage"; change c0013)."""

from __future__ import annotations

import dataclasses

from fenolite.checks.validate import BUILT_EVIDENCE, validate_stage
from fenolite.core.coords import Point
from fenolite.core.evidence import Level
from fenolite.model.board import Board, FootprintInstance
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design


def _design(*components: Component, placed: tuple[str, ...] = ()) -> Design:
    footprints = tuple(
        FootprintInstance(id=f"fpi_{c.id}", component_id=c.id, lib_ref="L:F", position=Point(0, 0))
        for c in components
        if c.id in placed
    )
    base = Design.new("t", seed=0)
    board = Board(id="brd_1", footprints=footprints)
    return dataclasses.replace(base, circuit=Circuit(components=components), board=board)


def test_unresolved_footprint_and_symbol() -> None:
    bare = Component(id="cmp_1", ref="U1", properties={"fenolite.path": "U1"})
    dnp = Component(id="cmp_2", ref="U2", dnp=True, lib_symbol_ref="L:S")
    result = validate_stage(_design(bare, dnp), built=True, evidence=BUILT_EVIDENCE)
    found = [(i.code, i.where) for i in result.issues if i.code.startswith("check.")]
    assert found == [("check.footprint-unresolved", "U1"), ("check.symbol-unresolved", "U1")]
    assert result.status == "errors"


def test_clean_built_model() -> None:
    part = Component(id="cmp_1", ref="R1", lib_symbol_ref="L:R", lib_footprint_ref="L:F")
    result = validate_stage(_design(part, placed=("cmp_1",)), built=True, evidence=BUILT_EVIDENCE)
    assert result.status == "ok" and result.issues == ()
    assert result.evidence.level == Level.INFERRED


def test_board_only_component_not_asked_for_a_symbol() -> None:
    hole = Component(id="cmp_1", ref="H1", lib_footprint_ref="L:F")
    result = validate_stage(_design(hole, placed=("cmp_1",)), built=True, evidence=BUILT_EVIDENCE)
    assert [(i.code, i.where) for i in result.issues if i.code.startswith("check.")] == []


def test_path_key_is_the_embed_property() -> None:
    from fenolite.backends.kicad.embed import PATH_PROPERTY
    from fenolite.checks.validate import PATH_KEY

    assert PATH_KEY == PATH_PROPERTY


def test_native_input_needs_no_symbol() -> None:
    part = Component(id="cmp_1", ref="R1", lib_footprint_ref="L:F")
    result = validate_stage(_design(part, placed=("cmp_1",)), built=False, evidence=BUILT_EVIDENCE)
    assert result.status == "ok"


def test_footprint_reference_without_instance() -> None:
    part = Component(id="cmp_1", ref="R1", lib_symbol_ref="L:R", lib_footprint_ref="L:F")
    result = validate_stage(_design(part), built=True, evidence=BUILT_EVIDENCE)
    assert [i.code for i in result.issues] == ["check.footprint-unresolved"]


def test_model_findings_pass_through() -> None:
    a = Component(id="cmp_1", ref="R1", lib_footprint_ref="L:F")
    b = Component(id="cmp_2", ref="R1", lib_footprint_ref="L:F")
    result = validate_stage(_design(a, b, placed=("cmp_1", "cmp_2")), built=False, evidence=BUILT_EVIDENCE)
    assert any(i.code.startswith("model.") for i in result.issues)
