# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Path aliases in the DSL (capability design-dsl, "Path aliases in the DSL" and the scenario "Aliases
exported" of "DSL package"; change c0019)."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from fenolite.dsl import Design, DslError, Module, Part, moves, to_model
from fenolite.model import canonical

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "examples" / "blink_2layer" / "design.py"


def blink() -> Design:
    design = runpy.run_path(str(BLINK))["design"]
    assert isinstance(design, Design)
    return design


def test_alias_recorded() -> None:
    d = Design("a")
    power = Module("power")
    power.add(Part("R1", "Mini:Mini_R"))
    d.add(power)
    d.moved("R1", "power/R1")
    assert dict(moves(d)) == {"power/R1": "R1"}


def test_old_part_still_present() -> None:
    d = Design("a")
    d.add(Part("R1", "Mini:Mini_R"), Part("R2", "Mini:Mini_R"))
    d.moved("R1", "R2")
    with pytest.raises(DslError, match="'R1'"):
        moves(d)


def test_unknown_new_path() -> None:
    d = Design("a")
    d.moved("R0", "R9")
    with pytest.raises(DslError, match="'R9'"):
        moves(d)


def test_chain_refused() -> None:
    d = Design("a")
    d.add(Part("C", "Mini:Mini_R"))
    d.moved("A", "B")
    d.moved("B", "C")
    with pytest.raises(DslError):
        moves(d)


def test_same_new_path_twice() -> None:
    d = Design("a")
    d.moved("R1", "R7")
    with pytest.raises(DslError, match="'R7'"):
        d.moved("R2", "R7")


def test_same_old_path_twice() -> None:
    d = Design("a")
    d.moved("R1", "R7")
    with pytest.raises(DslError, match="'R1'"):
        d.moved("R1", "R8")


@pytest.mark.parametrize(("old", "new"), [("R1", "R1"), ("R 1", "R2"), ("R1", "a//b"), ("", "R2"), ("R1", 7)])
def test_malformed(old: object, new: object) -> None:
    with pytest.raises(DslError):
        Design("a").moved(old, new)  # type: ignore[arg-type]


def test_model_unchanged_by_aliases() -> None:
    plain, aliased = blink(), blink()
    aliased.moved("R0", "R1")
    assert canonical.dump_texts(to_model(plain)) == canonical.dump_texts(to_model(aliased))
    assert dict(moves(aliased)) == {"R1": "R0"} and dict(moves(plain)) == {}


def test_aliases_exported() -> None:
    assert moves.__module__ == "fenolite.dsl.convert"
