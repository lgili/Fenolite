# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Alias resolution: what ``moved()`` and ``moved_net()`` mean for one build (``docs/lens.md``, "Module
aliases" and "Net aliases").

``resolve_aliases`` turns the script's aliases into the part, module and net aliases that apply to an
existing board. ``identity_map`` gives the uuids a footprint takes when it is kept under a new path.
Everything here is pure.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from fenolite.backends.kicad.embed import placement_uuid
from fenolite.core.errors import Issue
from fenolite.model.design import Design

NET_ALIAS_UNUSED = "layout.net-alias-unused"


def _empty() -> Mapping[str, str]:
    return MappingProxyType({})


@dataclass(frozen=True)
class Aliases:
    """The aliases of one build: ``parts`` and ``modules`` map a new path to the old one, ``nets`` a new
    net name to the old one; ``explicit_nets`` are the keys of ``nets`` that ``moved_net()`` gave."""

    parts: Mapping[str, str] = field(default_factory=_empty)
    modules: Mapping[str, str] = field(default_factory=_empty)
    nets: Mapping[str, str] = field(default_factory=_empty)
    explicit_nets: tuple[str, ...] = ()


def resolve_aliases(
    design: Design,
    board: Design | None,
    *,
    moves: Mapping[str, str] | None = None,
    module_moves: Mapping[str, str] | None = None,
    net_moves: Mapping[str, str] | None = None,
) -> tuple[Aliases, tuple[Issue, ...]]:
    """The aliases that apply to ``board``, and one ``layout.net-alias-unused`` per ``moved_net()`` alias
    whose old name is not a net of it.

    A module alias also renames the nets under the module: a board net ``<old>/<rest>`` that is not a net
    of ``design`` follows to ``<new>/<rest>`` when the design has that net and no ``moved_net()`` names
    it. The longest old module path wins. Without a board there are no net aliases and no issue.
    """
    parts = MappingProxyType(dict(sorted((moves or {}).items())))
    modules = MappingProxyType(dict(sorted((module_moves or {}).items())))
    if board is None:
        return Aliases(parts, modules), ()
    board_nets = {net.name for net in board.circuit.nets}
    design_nets = {net.name for net in design.circuit.nets}
    wanted = dict(net_moves or {})
    nets: dict[str, str] = {}
    issues: list[Issue] = []
    for new, old in sorted(wanted.items()):
        if old in board_nets:
            nets[new] = old
            continue
        issues.append(
            Issue(
                NET_ALIAS_UNUSED,
                "warning",
                f"moved_net({old!r}, {new!r}): the board has no net {old!r}; remove the alias",
                where=new,
            )
        )
    explicit = tuple(nets)
    taken = set(nets.values())
    for name in sorted(board_nets - design_nets - taken):
        owners = [(old, new) for new, old in modules.items() if name.startswith(f"{old}/")]
        if not owners:
            continue
        old, new = max(owners, key=lambda pair: len(pair[0]))
        renamed = new + name[len(old) :]
        if renamed in design_nets and renamed not in wanted and renamed not in nets:
            nets[renamed] = name
    return Aliases(parts, modules, MappingProxyType(dict(sorted(nets.items()))), explicit), tuple(issues)


def identity_map(old: str, new: str, locators: Iterable[str]) -> Mapping[str, str]:
    """The uuid each node of a footprint placed under ``old`` takes when it is kept under ``new``: one
    entry per locator, from ``placement_uuid(old, loc)`` to ``placement_uuid(new, loc)``."""
    return MappingProxyType({placement_uuid(old, loc): placement_uuid(new, loc) for loc in locators})


__all__ = ["NET_ALIAS_UNUSED", "Aliases", "identity_map", "resolve_aliases"]
