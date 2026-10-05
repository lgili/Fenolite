# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Alias resolution (capability layout-lens, "Alias resolution"; change c0069). The old design stands for the
board: ``resolve_aliases`` reads only the net names of its second argument."""

from __future__ import annotations

from fenolite.backends.kicad.embed import placement_uuid
from fenolite.dsl import Design, Module, Net, Part, connect, module_moves, moves, net_moves, to_model
from fenolite.lens.moved import Aliases, identity_map, resolve_aliases
from fenolite.lens.preserve import PRESERVE_ISSUE_CODES
from fenolite.model.design import Design as ModelDesign


def design(module: str, net: str = "FB", *extra: str) -> Design:
    """A module ``module`` with ``R1`` and ``R2`` joined by the net ``<module>/<net>``, and the top-level
    nets ``extra``."""
    d = Design("a")
    m = Module(module)
    r1, r2 = Part("R1", "Mini:Mini_R"), Part("R2", "Mini:Mini_R")
    m.add(r1, r2)
    d.add(m)
    connect(Net(f"{m.path}/{net}"), r1[1], r2[1])
    d.add(*(Net(name) for name in extra))
    return d


def resolve(d: Design, board: ModelDesign | None) -> tuple[Aliases, list[str]]:
    aliases, issues = resolve_aliases(
        to_model(d), board, moves=moves(d), module_moves=module_moves(d), net_moves=net_moves(d)
    )
    assert all(PRESERVE_ISSUE_CODES[i.code] == i.severity for i in issues)
    return aliases, [i.code for i in issues]


def test_module_alias_with_its_nets() -> None:
    d = design("supply")
    d.moved("power", "supply")
    aliases, codes = resolve(d, to_model(design("power")))
    assert dict(aliases.parts) == {"supply/R1": "power/R1", "supply/R2": "power/R2"}
    assert dict(aliases.modules) == {"supply": "power"}
    assert dict(aliases.nets) == {"supply/FB": "power/FB"}
    assert aliases.explicit_nets == () and codes == []


def test_an_explicit_net_alias_wins() -> None:
    d = design("supply", "VFB")
    d.moved("power", "supply")
    d.moved_net("power/FB", "supply/VFB")
    aliases, codes = resolve(d, to_model(design("power")))
    assert dict(aliases.nets) == {"supply/VFB": "power/FB"}
    assert aliases.explicit_nets == ("supply/VFB",) and codes == []


def test_explicit_alias_without_a_board_net() -> None:
    d = design("supply", "FB", "VY")
    d.moved_net("VX", "VY")
    aliases, issues = resolve_aliases(to_model(d), to_model(design("supply")), net_moves=net_moves(d))
    assert dict(aliases.nets) == {} and aliases.explicit_nets == ()
    (found,) = issues
    assert (found.code, found.severity) == ("layout.net-alias-unused", "warning")
    assert "VX" in found.message and "VY" in found.message


def test_no_board_no_net_aliases() -> None:
    d = design("supply", "FB", "VY")
    d.moved("power", "supply")
    d.moved_net("VX", "VY")
    aliases, codes = resolve(d, None)
    assert dict(aliases.nets) == {} and codes == []
    assert dict(aliases.parts) == {"supply/R1": "power/R1", "supply/R2": "power/R2"}


def test_module_nets_follow_only_to_design_nets() -> None:
    """A board net of the old module stays unmapped when the design still has a net of that name, or has no
    net of the new name."""
    d = design("supply", "FB", "power/KEPT")
    d.moved("power", "supply")
    board = design("power", "FB", "power/KEPT", "power/GONE")
    aliases, codes = resolve(d, to_model(board))
    assert dict(aliases.nets) == {"supply/FB": "power/FB"} and codes == []


def test_longest_old_module_path_wins() -> None:
    old = Design("a")
    outer, inner = Module("a"), Module("x")
    r1 = Part("R1", "Mini:Mini_R")
    inner.add(r1)
    outer.add(inner)
    old.add(outer)
    connect(Net("a/x/N"), r1[1])
    new = Design("a")
    outer2, inner2 = Module("b"), Module("y")
    r2 = Part("R1", "Mini:Mini_R")
    inner2.add(r2)
    outer2.add(inner2)
    new.add(outer2)
    connect(Net("b/y/N"), r2[1])
    connect(Net("b/x/N"), r2[2])
    new.moved("a", "b")
    new.moved("a/x", "b/y")
    aliases, _ = resolve(new, to_model(old))
    assert dict(aliases.nets) == {"b/y/N": "a/x/N"}


def test_identity_map() -> None:
    locators = ["/footprint", "/footprint/pad[0]"]
    mapping = identity_map("R1", "R7", locators)
    assert dict(mapping) == {placement_uuid("R1", loc): placement_uuid("R7", loc) for loc in locators}
    assert len(mapping) == 2 and dict(identity_map("R1", "R7", [])) == {}
