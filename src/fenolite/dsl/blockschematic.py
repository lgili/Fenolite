# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block-local schematic groups (``docs/dsl.md``, "Block schematic groups"; change c0269).

``schematic_group(key, *members, title=, anchor=, after=, flow=)`` is a frozen value; a block passes its
groups to ``b.schematic(...)`` once. The groups are declared once in the block and reused by every
instance: KiCad's readable layout orders the block's sheet by them, and Altium's block composition turns
each into a ``schematic_block`` keyed ``<instance path>/<key>``. They are not design-level intent, so they
never give "unused intent" and a KiCad build never refuses them. Nothing reaches the circuit model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fenolite.dsl.errors import DslError
from fenolite.dsl.part import NAME, Part
from fenolite.schematic.block_sheets import FLOWS, BlockSchematic, SheetGroup

if TYPE_CHECKING:
    from fenolite.dsl.block import Block
    from fenolite.dsl.design import Design


@dataclass(frozen=True)
class SchematicGroup:
    """A group of a block's own parts, as ``schematic_group`` records it; checked by ``b.schematic``."""

    key: str
    members: tuple[Part | str, ...]
    title: str | None = None
    anchor: Part | str | None = None
    after: str | None = None
    flow: str = "left-to-right"


def schematic_group(
    key: str,
    *members: Part | str,
    title: str | None = None,
    anchor: Part | str | None = None,
    after: str | None = None,
    flow: str = "left-to-right",
) -> SchematicGroup:
    """A group of a block's own parts for ``b.schematic``: a member is a part handle or a local part name;
    ``anchor`` is a member, ``after`` the key of another group of the call, ``flow`` ``left-to-right`` or
    ``top-to-bottom``. The block checks the group when it calls ``b.schematic``."""
    return SchematicGroup(key, tuple(members), title, anchor, after, flow)


def _local(block: Block, member: object, key: str) -> str:
    """The local name of a member of group ``key``: a part the block owns directly."""
    if isinstance(member, Part):
        if member.parent is not block:
            raise DslError(
                f"{block.describe()}: schematic group {key}: {member.path} is not a part of this block; a "
                "group holds the block's own parts (a nested block's part belongs to its own sheet)"
            )
        return member.key
    if isinstance(member, str):
        if block._local_part(member) is None:  # pyright: ignore[reportPrivateUsage]
            raise DslError(
                f"{block.describe()}: schematic group {key}: {member} is not a part of this block; a group "
                "holds the block's own parts (a nested block's part belongs to its own sheet)"
            )
        return member
    raise DslError(
        f"{block.describe()}: schematic group {key}: a member is a part or a local part name, not {member!r}"
    )


def _order(block: Block, groups: Sequence[SheetGroup]) -> tuple[SheetGroup, ...]:
    """The call order, each group moved after the group its ``after`` names (a stable topological order)."""
    done: list[SheetGroup] = []
    placed: set[str] = set()
    left = list(groups)
    while left:
        ready = next((g for g in left if g.after is None or g.after in placed), None)
        if ready is None:
            names = " and ".join(sorted(g.key for g in left))
            raise DslError(f"{block.describe()}: the schematic groups {names} follow each other in a cycle")
        left.remove(ready)
        done.append(ready)
        placed.add(ready.key)
    return tuple(done)


def declare(block: Block, groups: Sequence[object]) -> tuple[SheetGroup, ...]:
    """The checked groups of ``b.schematic(*groups)``, in their resolved order, with local part names as
    members; every refusal names the block."""
    where = block.describe()
    if block.schematic_groups is not None:
        raise DslError(f"{where}: b.schematic is called a second time; declare every group in one call")
    keys: list[str] = []
    seen: dict[str, str] = {}
    made: list[SheetGroup] = []
    for group in groups:
        if not isinstance(group, SchematicGroup):
            raise DslError(f"{where}: b.schematic takes schematic_group(...) values, not {group!r}")
        key = group.key
        if not isinstance(key, str) or not NAME.fullmatch(key):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{where}: schematic group key {key!r} must match {NAME.pattern}")
        if key in keys:
            raise DslError(f"{where}: the schematic group key {key} is used twice")
        keys.append(key)
        if group.flow not in FLOWS:
            raise DslError(
                f"{where}: schematic group {key}: flow {group.flow!r} is not one of {', '.join(FLOWS)}"
            )
        if group.title is not None and (
            not isinstance(group.title, str) or any(c in group.title for c in "\n\r\x00")  # pyright: ignore[reportUnnecessaryIsInstance]
        ):
            raise DslError(f"{where}: schematic group {key}: title must be single-line text")
        if not group.members:
            raise DslError(f"{where}: schematic group {key} has no member")
        members: list[str] = []
        for member in group.members:
            local = _local(block, member, key)
            other = seen.get(local)
            if other is not None:
                raise DslError(f"{where}: the part {local} is in the schematic groups {other} and {key}")
            seen[local] = key
            members.append(local)
        anchor: str | None = None
        if group.anchor is not None:
            anchor = _local(block, group.anchor, key)
            if anchor not in members:
                raise DslError(f"{where}: schematic group {key}: the anchor {anchor} is not a member")
            members = [anchor, *(m for m in members if m != anchor)]
        made.append(
            SheetGroup(key, tuple(members), group.title or key, anchor, group.after, group.flow)  # type: ignore[arg-type]
        )
    for group in made:
        if group.after is not None and group.after not in keys:
            raise DslError(
                f"{where}: schematic group {group.key}: after={group.after!r} names no group of the call"
            )
    return _order(block, made)


def block_schematics(design: Design) -> tuple[BlockSchematic, ...]:
    """Each block instance of ``design`` with its groups, members as component paths, in path order."""
    from fenolite.dsl.block import blocks

    found: list[BlockSchematic] = []
    for instance in blocks(design):
        groups = instance.schematic_groups or ()
        found.append(
            BlockSchematic(
                instance.path,
                instance.definition.name,
                tuple(
                    SheetGroup(
                        g.key,
                        tuple(f"{instance.path}/{m}" for m in g.members),
                        g.title,
                        f"{instance.path}/{g.anchor}" if g.anchor is not None else None,
                        g.after,
                        g.flow,
                    )
                    for g in groups
                ),
            )
        )
    return tuple(found)


__all__ = ["SchematicGroup", "block_schematics", "declare", "schematic_group"]
