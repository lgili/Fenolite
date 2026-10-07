# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stack-up of a design script (capability design-dsl, "Stack-up in the DSL"; change c0101)."""

from __future__ import annotations

import runpy
from fractions import Fraction
from pathlib import Path

import pytest

import fenolite.dsl as dsl
from fenolite.dsl import KEYS, Design, DslError, mm, stack, stackup_locked, to_model
from fenolite.dsl.convert import key_id
from fenolite.dsl.stack import StackEntry

ROOT = Path(__file__).resolve().parents[3]


def board(copper: int = 2) -> Design:
    design = Design("stack")
    design.board(mm(50), mm(30), copper=copper)
    return design


# -- entries


def test_entries_are_frozen_values() -> None:
    entry = stack.core("1.2mm", material="FR4", epsilon_r=4, loss_tangent="0.0200", color="FR4 natural")
    assert entry == StackEntry("core", 1_200_000, "FR4", "4", "0.02", "FR4 natural")
    with pytest.raises(AttributeError):
        entry.thickness = 1  # type: ignore[misc]
    assert stack.prepreg(mm("0.2")).kind == "prepreg"
    assert stack.copper("35um") == StackEntry("copper", 35_000)
    assert stack.mask("0mm", color="Green") == StackEntry("mask", 0, color="Green")
    assert stack.silkscreen(color="White") == StackEntry("silkscreen", color="White")


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ("4.50", "4.5"),
        (4, "4"),
        (Fraction(9, 2), "4.5"),
        ("0.0200", "0.02"),
        ("10", "10"),
        (Fraction(1, 8), "0.125"),
    ],
)
def test_decimals_are_stored_shortest(value: object, text: str) -> None:
    assert stack.core("1mm", epsilon_r=value).epsilon_r == text


@pytest.mark.parametrize("value", [4.5, True, "-4.5", "4.5e0", "+4", Fraction(1, 3), "4,5", 0, "0.0", ""])
def test_decimals_refused(value: object) -> None:
    with pytest.raises(DslError) as caught:
        stack.core("1.5mm", epsilon_r=value)
    assert repr(value) in str(caught.value)


def test_loss_tangent_may_be_zero_and_not_negative() -> None:
    """KiCad writes a loss tangent of 0 for a solder mask (design, "Found on 2026-10-07")."""
    assert stack.mask("10um", loss_tangent=0).loss_tangent == "0"
    with pytest.raises(DslError):
        stack.mask("10um", loss_tangent=0.02)


def test_thicknesses_and_texts_refused() -> None:
    for call in (
        lambda: stack.copper("0mm"),
        lambda: stack.core("0mm"),
        lambda: stack.prepreg("-0.1mm"),
        lambda: stack.mask("-1um"),
        lambda: stack.copper(35),
        lambda: stack.copper(0.035),
        lambda: stack.core("1mm", material=" FR4"),
        lambda: stack.mask("10um", color="Green "),
        lambda: stack.silkscreen(color=3),  # type: ignore[arg-type]
    ):
        with pytest.raises(DslError):
            call()


# -- the call


def four_layers(design: Design, **more: object) -> None:
    design.stackup(
        stack.mask("10um"),
        stack.copper("35um"),
        stack.prepreg("0.2mm", material="FR4", epsilon_r="4.50", loss_tangent="0.02"),
        stack.copper("17.5um"),
        stack.core("1.2mm", material="FR4", epsilon_r=4),
        stack.copper("17.5um"),
        stack.prepreg("0.2mm"),
        stack.copper("35um"),
        stack.mask("10um"),
        finish="ENIG",
        **more,  # type: ignore[arg-type]
    )


def test_four_layers_in_the_model() -> None:
    design = board(4)
    four_layers(design)
    model = to_model(design)
    assert model.board is not None and model.board.stackup is not None
    found = model.board.stackup
    assert [e.name for e in found.layers] == [
        "F.Mask", "F.Cu", "dielectric 1", "In1.Cu", "dielectric 2", "In2.Cu", "dielectric 3", "B.Cu", "B.Mask"
    ]  # fmt: skip
    assert found.layers[2].epsilon_r == "4.5" and found.layers[2].dielectric_kind == "prepreg"
    assert found.layers[4].epsilon_r == "4" and found.layers[4].dielectric_kind == "core"
    assert [e.kind for e in found.layers[:3]] == ["soldermask", "copper", "dielectric"]
    assert found.finish == "ENIG" and not found.impedance_controlled and found.thickness() == 1_725_000
    assert found.id == key_id("stackup")
    assert [e.id for e in found.layers] == [key_id("stack_layer", str(k)) for k in range(9)]
    assert not [i for i in model.validate() if i.code.startswith("model.stackup-")]
    assert to_model(design) == model


def test_sheets_silkscreens_and_flags() -> None:
    design = board()
    design.stackup(
        stack.silkscreen(color="White"),
        stack.mask("10um", color="Green"),
        stack.copper("35um"),
        stack.prepreg("0.1mm"),
        stack.prepreg("0.2mm"),
        stack.copper("35um"),
        stack.mask("10um"),
        stack.silkscreen(),
        impedance_controlled=True,
        locked=True,
    )
    found = to_model(design).board.stackup  # type: ignore[union-attr]
    assert found is not None and found.impedance_controlled and found.finish == ""
    assert [e.name for e in found.layers] == [
        "F.SilkS", "F.Mask", "F.Cu", "dielectric 1", "dielectric 1", "B.Cu", "B.Mask", "B.SilkS"
    ]  # fmt: skip
    assert found.layers[0].color == "White" and found.layers[0].kind == "silkscreen"
    assert stackup_locked(design) is True


CU = stack.copper("35um")
CORE = stack.core("1.5mm")
REFUSED = {
    "neighbouring copper": ((CU, CU), "entry 1 "),
    "two kinds in one gap": ((CU, CORE, stack.prepreg("0.1mm"), CU), "entry 2 "),
    "one copper layer": ((CU,), "entry 1 "),
    "three copper layers": ((CU, CORE, CU, CORE, CU), "entry 3 "),
    "dielectric on top": ((CORE, CU, CORE, CU), "entry 0 "),
    "dielectric below": ((CU, CORE, CU, CORE), "entry 3 "),
    "mask between": ((CU, stack.mask("10um"), CORE, CU), "entry 1 "),
    "two masks": ((stack.mask("10um"), stack.mask("10um"), CU, CORE, CU), "entry 1 "),
    "silkscreen under the top mask": ((stack.mask("1um"), stack.silkscreen(), CU, CORE, CU), "entry 1 "),
    "mask under the bottom silkscreen": ((CU, CORE, CU, stack.silkscreen(), stack.mask("1um")), "entry 4 "),
    "not an entry": ((CU, "1.5mm", CU), "entry 1 "),
}


@pytest.mark.parametrize("case", sorted(REFUSED))
def test_sequences_refused_at_the_call(case: str) -> None:
    entries, where = REFUSED[case]
    design = board()
    with pytest.raises(DslError) as caught:
        design.stackup(*entries)  # type: ignore[arg-type]
    assert where in str(caught.value), str(caught.value)
    assert design.stack is None


def test_other_refusals() -> None:
    with pytest.raises(DslError, match="after board"):
        Design("early").stackup(CU)
    with pytest.raises(DslError, match="4.5"):
        stack.core("1.5mm", epsilon_r=4.5)
    design = board()
    for bad in ({"finish": ""}, {"finish": 3}, {"impedance_controlled": 1}, {"locked": "yes"}):
        with pytest.raises(DslError):
            design.stackup(CU, CORE, CU, **bad)  # type: ignore[arg-type]
    design.stackup(CU, CORE, CU)
    with pytest.raises(DslError, match="once"):
        design.stackup(CU, CORE, CU)


def test_no_stackup_declared() -> None:
    design = runpy.run_path(str(ROOT / "examples" / "blink_2layer" / "design.py"))["design"]
    model = to_model(design)
    assert model.board is not None and model.board.stackup is None
    assert stackup_locked(design) is False


def test_keys_and_exports() -> None:
    assert KEYS["stackup"] == ("stk", "stackup") and KEYS["stack_layer"][0] == "sly"
    assert dsl.stack is stack and "stack" in dsl.__all__ and "stackup_locked" in dsl.__all__
    doc = (ROOT / "docs" / "dsl.md").read_text(encoding="utf-8")
    assert "| `stk` | `stackup` |" in doc and "`stack_layer:<k>`" in doc and "## Stack-up" in doc


def test_unknown_preset() -> None:
    """No preset ships with this part of the change (tasks, 9.1): every name is unknown."""
    assert stack.PRESETS == ()
    with pytest.raises(DslError, match=r"\[\]"):
        stack.preset("nope")
