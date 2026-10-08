# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The design: its header and five layers, read-only indexes, validation and replacement helpers."""

from __future__ import annotations

import dataclasses
import random
import re
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from functools import cached_property
from types import MappingProxyType
from typing import Any

from fenolite import __version__
from fenolite.core.errors import Issue, Severity
from fenolite.core.ids import new_id
from fenolite.model.base import Entity
from fenolite.model.board import MAX_CORNER_RATIO, Board, Pad, Stackup
from fenolite.model.circuit import Circuit, Component, Net, PinRef, pin_pad_map_problems
from fenolite.model.findings import Findings
from fenolite.model.manufacturing import Manifest
from fenolite.model.presentation import PAPER_SIZES, PARAM_NAME, US_SIZES, SheetFrameRef, TitleBlock
from fenolite.model.rules import RuleSet

SCHEMA_VERSION = "0"
MODEL_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType({"model.corner-ratio": "error"})
"""The codes of ``Design.validate`` that ``fenolite explain`` knows (``cli.explain.TABLES``): those added
since change c0126. The older ``model.*`` codes are described in ``docs/cli-contract.md`` only."""


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
            for item in (*fp.graphics, *fp.texts):  # the footprint's own drawings (change c0126)
                add(item.layer, item)
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
        """Structural findings: duplicate ids/refs, dangling references, single-pin and empty nets, and
        no-connect marks on unknown or connected pins."""
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
        for component in self.circuit.components:
            for pin, text in pin_pad_map_problems(component):
                add("model.pin-pad-map", "error", text, f"{component.ref}-{pin}",
                    "give each pad one pin, and each pair once")  # fmt: skip
        for fp in self.board.footprints if self.board else ():
            for pad in fp.pads:
                ratio = pad.corner_ratio
                if ratio is None:
                    continue
                if pad.shape != "roundrect":
                    text = f"a corner ratio of {ratio} ppm on a pad of shape {pad.shape}"
                    add(
                        "model.corner-ratio", "error", text, pad.id, "only a roundrect pad has a corner ratio"
                    )
                elif not 0 <= ratio <= MAX_CORNER_RATIO:
                    text = f"a corner ratio of {ratio} ppm is outside 0 to {MAX_CORNER_RATIO}"
                    add("model.corner-ratio", "error", text, pad.id,
                        "the ratio is in parts per million of the pad's shorter side")  # fmt: skip
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
        listed: dict[PinRef, str] = {}
        for net in self.circuit.nets:
            for member in net.members:
                listed.setdefault(member, net.name)
        for mark in self.circuit.no_connects:
            component = components.get(mark.component_id)
            where = f"{component.ref if component else mark.component_id}-{mark.pin}"
            if component is None:
                add("model.unknown-component", "error", f"unknown component {mark.component_id}", where)
            elif component.pins and mark.pin not in {p.number for p in component.pins}:
                add("model.unknown-pin", "error", f"{component.ref} has no pin {mark.pin}", where)
            if mark in listed:
                add("model.no-connect-on-net", "error",
                    f"pin is marked as not connected and is on net {listed[mark]}", where,
                    "remove the mark or take the pin off the net")  # fmt: skip
        for bus in self.circuit.buses:
            for member in bus.members:
                if member.net_id not in net_ids:
                    message = f"bus member {member.index} refers to unknown net {member.net_id}"
                    add("model.unknown-net", "error", message, bus.name)
            for index, count in sorted(Counter(m.index for m in bus.members).items()):
                if count > 1:
                    add(
                        "model.duplicate-bus-index", "error", f"index {index} is used {count} times", bus.name
                    )
        if self.board is not None:
            for body in (b for fp in self.board.footprints for b in fp.bodies):
                if body.standoff < 0 or body.height < body.standoff:
                    message = (
                        f"height {body.height} nm and standoff {body.standoff} nm do not describe a body"
                    )
                    hint = "the height is at least the standoff, and the standoff is not negative"
                    add("model.body-height", "error", message, body.id, hint)
            for fp in self.board.footprints:
                if fp.component_id and fp.component_id not in components:
                    add("model.unknown-component", "error", f"unknown component {fp.component_id}", fp.id)
            for item in iter_entities(self.board):
                net_id: str | None = getattr(item, "net_id", None)
                if net_id is not None and net_id not in net_ids:
                    add("model.unknown-net", "error", f"refers to unknown net {net_id}", item.id)
            issues += presentation_issues(self.board.sheet, self.board.title_block, self.board.id)
            if self.board.stackup is not None:
                copper = [
                    la for la in sorted(self.board.layers, key=lambda la: la.ordinal) if la.kind == "copper"
                ]
                issues += stackup_issues(self.board.stackup, tuple(la.name for la in copper))
        issues += impedance_issues(self)
        return tuple(issues)


_DRIVE = re.compile(r"^[A-Za-z]:")
PLAIN_DECIMAL = re.compile(r"\d+(?:\.\d+)?")
"""A decimal text of the model: digits, an optional point and digits, no sign and no exponent."""
_OUTER_KINDS = ("soldermask", "silkscreen", "solderpaste")


def _order_problem(stackup: Stackup) -> str | None:
    entries = stackup.layers
    copper = [i for i, entry in enumerate(entries) if entry.kind == "copper"]
    for entry in entries:
        if entry.dielectric_kind is not None and entry.kind != "dielectric":
            return (
                f"{entry.name!r} is a {entry.kind} entry with the dielectric kind {entry.dielectric_kind!r}"
            )
    if not copper:
        return None
    first, last = copper[0], copper[-1]
    for side, part in (("top", entries[:first]), ("bottom", entries[last + 1 :])):
        seen: set[str] = set()
        for entry in part:
            if entry.kind == "dielectric":
                where = "above the first" if side == "top" else "below the last"
                return f"dielectric entry {entry.name!r} lies {where} copper entry"
            if entry.kind in seen:
                return f"two {entry.kind} entries on the {side} side"
            seen.add(entry.kind)
    for upper, lower in zip(copper, copper[1:], strict=False):
        gap = entries[upper + 1 : lower]
        names = f"{entries[upper].name!r} and {entries[lower].name!r}"
        if not gap:
            return f"no entry between the copper entries {names}"
        for entry in gap:
            if entry.kind in _OUTER_KINDS:
                return f"{entry.kind} entry {entry.name!r} lies between the copper entries {names}"
        if len({entry.dielectric_kind for entry in gap}) > 1:
            return f"the dielectric entries between {names} are not of one kind"
    return None


def _value_problem(stackup: Stackup) -> str | None:
    for entry in stackup.layers:
        if entry.thickness < 0:
            return f"{entry.name!r} has the negative thickness {entry.thickness} nm"
        if entry.thickness == 0 and entry.kind in ("copper", "dielectric"):
            return f"{entry.kind} entry {entry.name!r} has the thickness 0"
        if entry.epsilon_r and (
            not PLAIN_DECIMAL.fullmatch(entry.epsilon_r) or not entry.epsilon_r.strip("0.")
        ):
            return f"epsilon_r {entry.epsilon_r!r} of {entry.name!r} is not a plain decimal above 0"
        if entry.loss_tangent and not PLAIN_DECIMAL.fullmatch(entry.loss_tangent):
            return f"loss_tangent {entry.loss_tangent!r} of {entry.name!r} is not a plain decimal"
    return None


def stackup_issues(stackup: Stackup, copper_layers: tuple[str, ...]) -> list[Issue]:
    """The ``model.stackup-order``, ``model.stackup-copper`` and ``model.stackup-value`` findings of a
    stack-up (design-model, "Stack-up in the board model"), at most one of each, naming the first problem.
    ``copper_layers`` are the names of the board's copper layers in ordinal order."""
    found: list[tuple[str, str, str]] = []
    order = _order_problem(stackup)
    if order is not None:
        found.append(("model.stackup-order", order, "list the entries from the top face to the bottom face"))
    names = tuple(entry.name for entry in stackup.layers if entry.kind == "copper")
    if not names:
        found.append(("model.stackup-copper", "the stack-up holds no copper entry", ""))
    elif copper_layers and names != copper_layers:
        message = f"the copper entries {list(names)} are not the board's copper layers {list(copper_layers)}"
        found.append(("model.stackup-copper", message, "name one copper entry per copper layer, in order"))
    value = _value_problem(stackup)
    if value is not None:
        found.append(("model.stackup-value", value, ""))
    return [Issue(code=code, severity="error", message=message, where=stackup.id, hint=hint)
            for code, message, hint in found]  # fmt: skip


POSITIVE_DECIMAL = re.compile(r"\d+(?:\.\d+)?")


def _positive_decimal(text: str) -> bool:
    return bool(POSITIVE_DECIMAL.fullmatch(text)) and any(c in "123456789" for c in text)


def impedance_issues(design: Design) -> list[Issue]:
    """``model.impedance-invalid`` for each problem of the impedance targets of ``design`` (change c0105):
    an unknown class, a class of two targets, two targets of one name, a layer twice, a gap that does not
    fit the kind, a length of 0 or less, a reference count other than one or two or a reference equal to
    the layer, and an ``ohms`` or tolerance text that is not a positive decimal (tolerance below 100)."""
    targets = design.rules.impedance if design.rules is not None else ()
    if not targets:
        return []
    found: list[Issue] = []
    classes = {c.id: c.name for c in design.circuit.netclasses}

    def add(target: str, message: str, hint: str = "") -> None:
        found.append(
            Issue("model.impedance-invalid", "error", message, where=f"impedance/{target}", hint=hint)
        )

    for name, count in sorted(Counter(t.name for t in targets).items()):
        if count > 1:
            add(name, f"{count} impedance targets are named {name!r}")
    owners: dict[str, list[str]] = {}
    for target in targets:
        if not target.name:
            add(target.name, "an impedance target has no name")
        for class_id in target.netclass_ids:
            if class_id not in classes:
                add(target.name, f"target {target.name}: {class_id} names no net class")
            else:
                owners.setdefault(class_id, []).append(target.name)
        if not target.netclass_ids:
            add(target.name, f"target {target.name} names no net class")
        if target.ohms and not _positive_decimal(target.ohms):
            add(target.name, f"target {target.name}: ohms {target.ohms!r} is not a positive decimal")
        tolerance = target.tolerance_percent
        if tolerance and (not _positive_decimal(tolerance) or int(tolerance.split(".")[0]) >= 100):
            add(
                target.name,
                f"target {target.name}: tolerance {tolerance!r} is not a positive decimal below 100",
            )
        for layer, count in sorted(Counter(row.layer for row in target.layers).items()):
            if count > 1:
                add(target.name, f"target {target.name}: layer {layer} is given {count} times")
        for row in target.layers:
            where = f"target {target.name}, layer {row.layer}"
            if row.width <= 0:
                add(target.name, f"{where}: width {row.width} nm is not above 0")
            if target.kind == "differential" and (row.gap is None or row.gap <= 0):
                add(target.name, f"{where}: a differential target needs a gap above 0")
            if target.kind == "single" and row.gap is not None:
                add(target.name, f"{where}: a single-ended target takes no gap")
            if len(row.references) not in (1, 2) or len(set(row.references)) != len(row.references):
                add(target.name, f"{where}: give one or two distinct reference layers")
            if row.layer in row.references:
                add(target.name, f"{where}: the layer is its own reference")
    for class_id, names in sorted(owners.items()):
        if len(names) > 1:
            add(
                names[0],
                f"targets {', '.join(names)} both govern the net class {classes[class_id]}",
                "give each net class one impedance target",
            )
    return found


def _sheet_path_problem(path: str) -> str | None:
    """Why ``path`` is not a project-relative path (``${KIPRJMOD}/`` allowed), or None."""
    rest = path.removeprefix("${KIPRJMOD}/")
    if rest.startswith(("/", "\\")) or _DRIVE.match(rest):
        return "an absolute path"
    if ".." in re.split(r"[/\\]", rest):
        return "a '..' segment"
    return None


def presentation_issues(sheet: SheetFrameRef | None, block: TitleBlock | None, where: str) -> list[Issue]:
    """The ``model.sheet-path``, ``model.sheet-size`` and ``model.param-name`` findings of a board's
    presentation fields (design-model, "Presentation values are validated")."""
    issues: list[Issue] = []
    if sheet is not None:
        if sheet.drawing_sheet is not None:
            why = _sheet_path_problem(sheet.drawing_sheet)
            if why:
                issues.append(Issue(code="model.sheet-path", severity="error", where=where,
                                    message=f"drawing sheet {sheet.drawing_sheet!r} is {why}",
                                    hint="name the sheet relative to the project folder"))  # fmt: skip
        size = _sheet_size_problem(sheet)
        if size:
            issues.append(Issue(code="model.sheet-size", severity="error", message=size, where=where))
    for name in sorted(block.params) if block is not None else ():
        if not PARAM_NAME.fullmatch(name):
            message = f"parameter name {name!r} does not match [A-Za-z_][A-Za-z0-9_]*"
            issues.append(Issue(code="model.param-name", severity="error", message=message, where=where))
    return issues


def _sheet_size_problem(sheet: SheetFrameRef) -> str | None:
    if sheet.paper == "custom":
        if sheet.width is None or sheet.height is None:
            return "a custom paper needs both width and height"
        if sheet.portrait:
            return "portrait is not set on a custom paper; give width and height in the wanted orientation"
        for name in US_SIZES:
            w, h = PAPER_SIZES[name]
            if (sheet.width, sheet.height) in ((w, h), (h, w)):
                return f"a custom paper of {name} size is the named size {name!r}"
        return None
    if sheet.width is not None or sheet.height is not None:
        return f"width and height are set only on a custom paper, not on {sheet.paper!r}"
    return None


__all__ = [
    "MODEL_ISSUE_CODES",
    "PLAIN_DECIMAL",
    "SCHEMA_VERSION",
    "Design",
    "DesignHeader",
    "impedance_issues",
    "iter_entities",
    "presentation_issues",
    "stackup_issues",
]
