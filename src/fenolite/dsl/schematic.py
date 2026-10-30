# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Record schematic intent without touching the electrical model or filesystem."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fenolite.dsl.errors import DslError
from fenolite.dsl.part import Part
from fenolite.schematic.intent import BlockIntent, CompositionIntent, Flow

if TYPE_CHECKING:
    from fenolite.dsl.design import Design


@dataclass(frozen=True)
class BlockRequest:
    key: str
    members: tuple[Part, ...]
    title: str
    anchor: Part | None
    after: str | None


def record_block(
    design: Design,
    key: str,
    *,
    members: Sequence[Part],
    title: str | None,
    anchor: Part | None,
    after: str | None,
) -> None:
    if not key or key != key.strip() or any(c in key for c in "\n\r\x00"):
        raise DslError("schematic_block: key must be nonempty text without control characters")
    if key in design.schematic_blocks:
        raise DslError(f"schematic_block {key}: duplicate key")
    if not members or any(not isinstance(p, Part) for p in members):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"schematic_block {key}: members must be existing Part objects")
    if title is not None and (not isinstance(title, str) or any(c in title for c in "\n\r\x00")):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"schematic_block {key}: title must be single-line text")
    if after is not None and (not isinstance(after, str) or not after):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"schematic_block {key}: after must name a block")
    if anchor is not None and not isinstance(anchor, Part):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"schematic_block {key}: anchor must be a member Part")
    design.schematic_blocks[key] = BlockRequest(key, tuple(members), title or key, anchor, after)


def extract(design: Design, *, target: str | None = None, enabled: bool = False) -> CompositionIntent | None:
    if design.schematic_flow is None and not design.schematic_blocks and not enabled:
        return None
    if target not in (None, "altium"):
        raise DslError("schematic composition currently requires the Altium target")
    if design.schematic_flow is None and design.schematic_blocks and not enabled:
        raise DslError("schematic blocks require schematic_layout(mode='blocks') or --altium-layout blocks")
    used: set[str] = set()
    blocks: list[BlockIntent] = []
    for key, request in sorted(design.schematic_blocks.items()):
        for part in request.members:
            if design.parts.get(part.path) is not part:
                raise DslError(f"schematic_block {key}: {part.path} is not a member of this design")
            if part.path in used:
                raise DslError(f"schematic_block {key}: duplicate membership of {part.path}")
            used.add(part.path)
        if request.anchor is not None and request.anchor not in request.members:
            raise DslError(f"schematic_block {key}: anchor must belong to the block")
        if request.after is not None and request.after not in design.schematic_blocks:
            raise DslError(f"schematic_block {key}: unknown predecessor {request.after}")
        blocks.append(
            BlockIntent(
                key,
                tuple(sorted(p.path for p in request.members)),
                request.title,
                request.anchor.path if request.anchor else None,
                request.after,
            )
        )
    blocks = sorted(blocks + _implicit(design, used), key=lambda b: b.key)
    predecessors = {b.key: b.after for b in blocks}
    for key in predecessors:
        seen: set[str] = set()
        current: str | None = key
        while current is not None:
            if current in seen:
                raise DslError(f"schematic_block {key}: ordering cycle at {current}")
            seen.add(current)
            current = predecessors[current]
    return CompositionIntent(design.schematic_flow or "left-to-right", tuple(blocks))


def _implicit(design: Design, used: set[str]) -> list[BlockIntent]:
    """One block per block instance that owns parts directly (change c0251): keyed by its path, holding
    those parts minus the members of declared blocks, titled ``<path> (<block name>)``; a declared block
    of the same key replaces it."""
    from fenolite.dsl.block import blocks as block_instances

    found: list[BlockIntent] = []
    for instance in block_instances(design):
        if instance.path in design.schematic_blocks:
            continue
        members = sorted(
            child.path for child in instance.children if isinstance(child, Part) and child.path not in used
        )
        if members:
            title = f"{instance.path} ({instance.definition.name})"
            found.append(BlockIntent(instance.path, tuple(members), title, None, None))
    return found


def set_flow(design: Design, *, mode: str, flow: str) -> None:
    if mode != "blocks" or flow not in ("left-to-right", "top-to-bottom"):
        raise DslError("schematic_layout requires mode='blocks' and a supported flow direction")
    if design.schematic_flow is not None:
        raise DslError("schematic_layout is declared twice")
    design.schematic_flow = "left-to-right" if flow == "left-to-right" else "top-to-bottom"


__all__ = ["BlockRequest", "Flow", "extract", "record_block", "set_flow"]
