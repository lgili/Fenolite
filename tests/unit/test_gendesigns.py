# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The seeded design generator of the netlist acceptance test (capability kicad-oracle, "Own netlists
equal kicad-cli's", scenario "The generator is deterministic"; change c0063). Hermetic: every design is
built with the authored mini library and no tool."""

from __future__ import annotations

from functools import cache

import _gendesigns as gen
import pytest
from _buildhelp import build, codes

from fenolite.backends.kicad.netlist import differences
from fenolite.backends.kicad.sch_netlist import grammar_issues, own_netlist
from fenolite.dsl import placements, to_model
from fenolite.lens.build import BuildOutput


@cache
def built(index: int, target: int = 10) -> BuildOutput:
    return build(gen.design(gen.SEED, index), target)


def test_the_generator_is_deterministic() -> None:
    first, second = gen.designs(seed=20261004, count=25), gen.designs(seed=20261004, count=25)
    assert len(first) == 25 and [d.name for d in first] == [f"gen{i:02d}" for i in range(25)]
    assert [to_model(d) for d in first] == [to_model(d) for d in second]
    assert [placements(d) for d in first] == [placements(d) for d in second]
    assert first[3] is not second[3], "every call makes new designs"
    for made in first:
        errors = [issue for issue in to_model(made).validate() if issue.severity == "error"]
        assert errors == [], (made.name, errors)


def test_defaults_are_the_acceptance_set() -> None:
    assert (gen.SEED, gen.COUNT) == (20261004, 25)
    assert [to_model(d) for d in gen.designs()] == [to_model(d) for d in gen.designs(20261004, 25)]


def test_another_seed_gives_other_designs() -> None:
    assert [to_model(d) for d in gen.designs(1, 5)] != [to_model(d) for d in gen.designs(2, 5)]
    assert to_model(gen.design(gen.SEED, 7)) == to_model(gen.designs()[7])


def test_one_to_twelve_parts_of_the_mini_library() -> None:
    sizes = [len(d.parts) for d in gen.designs()]
    assert min(sizes) == 1 and max(sizes) == 12 and len(set(sizes)) >= 6
    symbols = {part.lib_id for d in gen.designs() for part in d.parts.values()}
    assert symbols == {kind.symbol for kind in gen.KINDS}
    assert all(symbol.startswith("Mini:") for symbol in symbols)


def test_the_set_holds_every_feature() -> None:
    found = gen.features(gen.designs())
    assert set(found) == {"units", "pad_map", "no_connect", "power", "slash", "module", "open"}
    assert all(count >= 5 for count in found.values()), found
    assert found["power"] < 25, "some designs have no power interface"


@pytest.mark.parametrize("index", range(gen.COUNT))
def test_every_design_builds_and_passes_the_guard(index: int) -> None:
    output = built(index)
    errors = [issue for issue in output.issues if issue.severity == "error"]
    assert errors == [], errors
    name = f"gen{index:02d}"
    assert f"{name}.kicad_sch" in output.files and f"{name}.kicad_pcb" in output.files
    assert "build.schematic-netlist-differs" not in codes(output)
    assert output.schematic is not None and grammar_issues(output.schematic.sheet) == ()


@pytest.mark.parametrize("index", [0, 1, 5, 12, 24])
def test_both_targets_mean_the_same_netlist(index: int) -> None:
    """The target changes the written form, not the circuit: the own netlists of the two sheets agree."""
    nine, ten = built(index, 9).schematic, built(index, 10).schematic
    assert nine is not None and ten is not None
    name = f"gen{index:02d}"
    first, second = own_netlist(nine.sheet, project=name), own_netlist(ten.sheet, project=name)
    assert [c.ref for c in first.components] == [c.ref for c in second.components]
    assert differences(first, second) == ()
