# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Path and net aliases in the DSL (capability design-dsl, "Path aliases in the DSL", "Net aliases in the
DSL" and the scenario "Aliases exported" of "DSL package"; changes c0019 and c0069)."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from fenolite.dsl import Design, DslError, Module, Net, Part, module_moves, moves, net_moves, to_model
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


# -- module aliases (c0069)


def supply(*refs: str) -> Design:
    d = Design("a")
    module = Module("supply")
    module.add(*(Part(ref, "Mini:Mini_R") for ref in refs))
    d.add(module)
    return d


def test_module_alias_expanded() -> None:
    d = supply("R1", "C1")
    d.moved("power", "supply")
    assert dict(moves(d)) == {"supply/C1": "power/C1", "supply/R1": "power/R1"}
    assert list(moves(d)) == ["supply/C1", "supply/R1"]
    assert dict(module_moves(d)) == {"supply": "power"}


def test_part_renamed_inside_a_renamed_module() -> None:
    d = supply("R9", "C1")
    d.moved("power", "supply")
    d.moved("power/R1", "supply/R9")
    assert dict(moves(d)) == {"supply/C1": "power/C1", "supply/R9": "power/R1"}


def test_part_alias_keeps_its_old_path_from_a_new_part() -> None:
    d = supply("R9", "R1")
    d.moved("power", "supply")
    d.moved("power/R1", "supply/R9")
    assert dict(moves(d)) == {"supply/R9": "power/R1"}


def test_longer_module_path_wins() -> None:
    d = Design("a")
    outer, inner = Module("b"), Module("y")
    inner.add(Part("R1", "Mini:Mini_R"))
    outer.add(inner, Part("R2", "Mini:Mini_R"))
    d.add(outer)
    d.moved("a", "b")
    d.moved("a/x", "b/y")
    assert dict(moves(d)) == {"b/R2": "a/R2", "b/y/R1": "a/x/R1"}
    assert dict(module_moves(d)) == {"b": "a", "b/y": "a/x"}


def test_old_module_still_present() -> None:
    d = supply("R1")
    d.add(Module("power"))
    d.moved("power", "supply")
    with pytest.raises(DslError, match="'power'"):
        module_moves(d)
    with pytest.raises(DslError, match="'power'"):
        moves(d)


def test_module_moves_exported_and_empty() -> None:
    assert module_moves.__module__ == net_moves.__module__ == "fenolite.dsl.convert"
    assert dict(module_moves(blink())) == {} and dict(net_moves(blink())) == {}


# -- net aliases (c0069)


def test_net_alias_recorded() -> None:
    d = Design("a")
    d.add(Net("LED_ANODE"))
    d.moved_net("LED_A", "LED_ANODE")
    assert dict(net_moves(d)) == {"LED_ANODE": "LED_A"}


def test_old_net_still_present() -> None:
    d = Design("a")
    d.add(Net("VIN"), Net("VBUS"))
    d.moved_net("VIN", "VBUS")
    with pytest.raises(DslError, match="'VIN'"):
        net_moves(d)


def test_unknown_new_net_and_chain() -> None:
    d = Design("a")
    d.moved_net("A", "B")
    with pytest.raises(DslError, match="'B'"):
        net_moves(d)
    d.add(Net("C"))
    d.moved_net("B", "C")
    with pytest.raises(DslError):
        net_moves(d)


@pytest.mark.parametrize(("old", "new"), [("A", "A"), ("", "B"), ("A", ""), ("A", 7)])
def test_malformed_net_alias(old: object, new: object) -> None:
    with pytest.raises(DslError):
        Design("a").moved_net(old, new)  # type: ignore[arg-type]


def test_net_alias_twice() -> None:
    d = Design("a")
    d.moved_net("A", "B")
    with pytest.raises(DslError, match="'B'"):
        d.moved_net("C", "B")
    with pytest.raises(DslError, match="'A'"):
        d.moved_net("A", "D")


def test_model_unchanged_by_net_aliases() -> None:
    plain, aliased = blink(), blink()
    aliased.moved_net("LED_X", "LED_A")
    assert canonical.dump_texts(to_model(plain)) == canonical.dump_texts(to_model(aliased))
    assert dict(net_moves(aliased)) == {"LED_A": "LED_X"}
