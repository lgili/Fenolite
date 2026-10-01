# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The design: its header and five layers, read-only indexes, validation and replacement helpers."""

from __future__ import annotations

import dataclasses
import random
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from fenolite import __version__
from fenolite.core.errors import Issue, Severity
from fenolite.core.ids import new_id
from fenolite.model.base import Entity
from fenolite.model.board import Board, Pad
from fenolite.model.circuit import Circuit, Component, Net
from fenolite.model.findings import Findings
from fenolite.model.manufacturing import Manifest
from fenolite.model.rules import RuleSet

SCHEMA_VERSION = "0"


@dataclass(frozen=True, slots=True)
class DesignHeader(Entity):
    """Identity of a design (``meta.json``)."""

    name: str
    schema_version: str
    fenolite_version: str


def iter_entities(value: Any) -> Iterator[Entity]:
    """Every entity reachable from ``value`` (depth first, in field order)."""
    if isinstance(value, Entity):
        yield value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for f in dataclasses.fields(value):
            yield from iter_entities(getattr(value, f.name))
    elif isinstance(value, (tuple, list)):
        for item in value:  # pyright: ignore[reportUnknownVariableType]
            yield from iter_entities(item)


def _replace_in(value: Any, new: Entity) -> tuple[Any, bool]:
    if isinstance(value, Entity) and value.id == new.id:
        return new, True
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        changes: dict[str, Any] = {}
        for f in dataclasses.fields(value):
            replaced, hit = _replace_in(getattr(value, f.name), new)
            if hit:
                changes[f.name] = replaced
        return (dataclasses.replace(value, **changes), True) if changes else (value, False)
    if isinstance(value, tuple):
        original: tuple[Any, ...] = value  # pyright: ignore[reportUnknownVariableType]
        items: list[Any] = []
        any_hit = False
        for item in original:
            replaced, hit = _replace_in(item, new)
            items.append(replaced)
            any_hit = any_hit or hit
        return (tuple(items), True) if any_hit else (original, False)
    return value, False


@dataclass(frozen=True)
class Design:
    """A complete design. Immutable; indexes are built on first use and cached per instance."""

    header: DesignHeader
    circuit: Circuit = field(default_factory=Circuit)
    board: Board | None = None
    rules: RuleSet | None = None
    manufacturing: Manifest | None = None
    findings: Findings = field(default_factory=Findings)

    @classmethod
    def new(cls, name: str, *, seed: int | None = None) -> Design:
        """An empty design with fresh ids (reproducible with ``seed``)."""
        rng = random.Random(seed)
        return cls(
            header=DesignHeader(
                id=new_id("dsn", rng), name=name, schema_version=SCHEMA_VERSION, fenolite_version=__version__
            ),
            board=Board(id=new_id("brd", rng)),
            rules=RuleSet(id=new_id("rst", rng)),
            manufacturing=Manifest(id=new_id("mfn", rng)),
        )

    @property
    def id(self) -> str:
        return self.header.id

    def entities(self) -> Iterator[Entity]:
        for part in (self.header, self.circuit, self.board, self.rules, self.manufacturing):
            yield from iter_entities(part)

    @cached_property
    def by_id(self) -> dict[str, Entity]:
        return {e.id: e for e in self.entities()}

    @cached_property
    def by_ref(self) -> dict[str, Component]:
        return {c.ref: c for c in self.circuit.components}

    @cached_property
    def nets_by_name(self) -> dict[str, Net]:
        return {n.name: n for n in self.circuit.nets}

    @cached_property
    def by_net(self) -> dict[str, tuple[Pad, ...]]:
        """Net name → pads assigned to that net."""
        names = {n.id: n.name for n in self.circuit.nets}
        pads: dict[str, list[Pad]] = {name: [] for name in names.values()}
        for fp in self.board.footprints if self.board else ():
            for pad in fp.pads:
                if pad.net_id in names:
                    pads[names[pad.net_id]].append(pad)
        return {name: tuple(items) for name, items in pads.items()}

    @cached_property
    def by_layer(self) -> dict[str, tuple[Entity, ...]]:
        """Layer name → board objects on that layer (pads, tracks, arcs, vias, zones, keepouts, text…)."""
        index: dict[str, list[Entity]] = {}
        board = self.board
        if board is None:
            return {}

        def add(layer: str, item: Entity) -> None:
            index.setdefault(layer, []).append(item)

        for fp in board.footprints:
            for pad in fp.pads:
                for layer in pad.layers:
                    add(layer, pad)
        for item in (*board.tracks, *board.arcs, *board.texts, *board.graphics):
            add(item.layer, item)
        for item in (*board.vias, *board.zones, *board.keepouts):
            for layer in item.layers:
                add(layer, item)
        return {layer: tuple(items) for layer, items in index.items()}

    def replace_entity(self, new: Entity) -> Design:
        """A copy of the design with the entity whose id equals ``new.id`` replaced by ``new``."""
        changes: dict[str, Any] = {}
        for name in ("header", "circuit", "board", "rules", "manufacturing"):
            replaced, hit = _replace_in(getattr(self, name), new)
            if hit:
                changes[name] = replaced
        if not changes:
            raise KeyError(f"no entity with id {new.id!r}")
        return dataclasses.replace(self, **changes)

    def validate(self) -> tuple[Issue, ...]:
        """Structural findings: duplicate ids/refs, dangling references, single-pin and empty nets."""
        issues: list[Issue] = []

        def add(code: str, severity: Severity, message: str, where: str, hint: str = "") -> None:
            issues.append(Issue(code=code, severity=severity, message=message, where=where, hint=hint))

        for entity_id, count in sorted(Counter(e.id for e in self.entities()).items()):
            if count > 1:
                add("model.duplicate-id", "error", f"id used {count} times", entity_id)
        placed: dict[str, list[tuple[str, ...]]] = {}
        for fp in self.board.footprints if self.board else ():
            placed.setdefault(fp.component_id, []).append(fp.attributes)
        for ref, count in sorted(Counter(c.ref for c in self.circuit.components).items()):
            if count > 1:
                sharing = [c for c in self.circuit.components if c.ref == ref]
                board_only = all(
                    placed.get(c.id) and all("board_only" in attrs for attrs in placed[c.id]) for c in sharing
                )
                severity: Severity = "warning" if board_only or ref.endswith("**") else "error"
                add("model.duplicate-ref", severity, f"reference used {count} times", ref)
        components = {c.id: c for c in self.circuit.components}
        netclasses = {c.id for c in self.circuit.netclasses}
        net_ids = {n.id for n in self.circuit.nets}
        for net in self.circuit.nets:
            if net.netclass_id is not None and net.netclass_id not in netclasses:
                add("model.unknown-netclass", "error", f"unknown net class {net.netclass_id}", net.name)
            for member in net.members:
                component = components.get(member.component_id)
                if component is None:
                    add(
                        "model.unknown-component",
                        "error",
                        f"unknown component {member.component_id}",
                        net.name,
                    )
                elif component.pins and member.pin not in {p.number for p in component.pins}:
                    add("model.unknown-pin", "error", f"{component.ref} has no pin {member.pin}", net.name)
            pads = self.by_net.get(net.name, ())
            if not net.members and not pads:
                add("model.dangling-net", "warning", "net connects nothing", net.name)
            elif len(net.members) == 1 and len(pads) <= 1:
                add("model.single-pin-net", "warning", "net connects a single pin", net.name,
                    "a single-pin net is often a floating pin")  # fmt: skip
        if self.board is not None:
            for fp in self.board.footprints:
                if fp.component_id and fp.component_id not in components:
                    add("model.unknown-component", "error", f"unknown component {fp.component_id}", fp.id)
            for item in iter_entities(self.board):
                net_id: str | None = getattr(item, "net_id", None)
                if net_id is not None and net_id not in net_ids:
                    add("model.unknown-net", "error", f"refers to unknown net {net_id}", item.id)
        return tuple(issues)


__all__ = ["SCHEMA_VERSION", "Design", "DesignHeader", "iter_entities"]
