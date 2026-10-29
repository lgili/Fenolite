# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Neutral design rules: kind, selectors, layers, min/opt/max, severity and explicit priority.

Backends lower rules to their own form (a KiCad custom-rules file, the second backend's rule
records). Priority 1 is the highest; backends preserve that meaning when lowering.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from fenolite.core.units import Nm
from fenolite.model.base import Entity
from fenolite.model.pairs import base_matches

RuleKind = Literal[
    "clearance",
    "track_width",
    "via_diameter",
    "via_drill",
    "hole_size",
    "edge_clearance",
    "hole_to_hole",
    "hole_clearance",
    "annular_width",
    "courtyard_clearance",
    "silk_clearance",
    "creepage",
    "no_tracks",
    "diff_pair_gap",
    "diff_pair_uncoupled",
    "skew",
    "diff_pair_skew",
    "length",
]
"""The first six kinds are those of v0.1; the next six were added by change c0071, and ``no_tracks`` (no
track or arc of the selected items on the rule's layers; it takes no limit) by change c0107. The last five,
the pair and length kinds, were added by change c0104 (``skew`` compares every net a rule selects with the
longest of them, ``diff_pair_skew`` the two nets of each pair it selects). Which sides, selector ops and
layer clause a kind takes, and for which targets it is written, is the backend's to say
(``backends.kicad.rulemap.KIND_SELECTORS`` and ``KIND_SUPPORT``)."""
RuleSeverity = Literal["error", "warning", "ignore"]
SelectorOp = Literal[
    "all", "net", "netclass", "ref", "layer", "item_kind", "area", "diff_pair", "and", "or", "not"
]
LEAF_OPS = ("net", "netclass", "ref", "layer", "item_kind", "area", "diff_pair")
"""The leaves. The value of ``diff_pair`` is a pair base (``model.pairs``) or ``*``, compared with its
letter case; the value of ``area`` is the name of a rule area, compared with its letter case and with ``*``
as a glob; the other leaves hold globs over names."""


@dataclass(frozen=True, slots=True)
class RuleSubject:
    """The properties of one object a selector is evaluated against."""

    item_kind: str
    net: str | None = None
    netclass: str | None = None
    ref: str | None = None
    layer: str | None = None
    areas: frozenset[str] = frozenset()
    """The names of the rule areas the object lies in (letter case counts)."""
    #: The base of the subject's net when the design holds the coupled net (``model.pairs.net_bases``).
    diff_pair: str | None = None


@dataclass(frozen=True, slots=True)
class Selector:
    """A small predicate algebra. Leaf values are globs such as ``PWR_*`` or ``U*``."""

    op: SelectorOp
    value: str = ""
    items: tuple[Selector, ...] = field(default=(), metadata={"ordered": True})

    def __post_init__(self) -> None:
        if self.op in ("and", "or") and len(self.items) < 2:
            raise ValueError(f"selector '{self.op}' needs at least two items")
        if self.op == "not" and len(self.items) != 1:
            raise ValueError("selector 'not' needs exactly one item")
        if self.op in LEAF_OPS and not self.value:
            raise ValueError(f"selector '{self.op}' needs a value")
        if self.op in (*LEAF_OPS, "all") and self.items:
            raise ValueError(f"selector '{self.op}' takes no items")

    def matches(self, subject: RuleSubject) -> bool:
        match self.op:
            case "all":
                return True
            case "and":
                return all(item.matches(subject) for item in self.items)
            case "or":
                return any(item.matches(subject) for item in self.items)
            case "not":
                return not self.items[0].matches(subject)
            case "net":
                return _glob(subject.net, self.value)
            case "netclass":
                return _glob(subject.netclass, self.value)
            case "ref":
                return _glob(subject.ref, self.value)
            case "layer":
                return _glob(subject.layer, self.value)
            case "item_kind":
                return _glob(subject.item_kind, self.value)
            case "area":
                return any(fnmatch.fnmatchcase(name, self.value) for name in subject.areas)
            case "diff_pair":
                return base_matches(subject.diff_pair, self.value)


def _glob(value: str | None, pattern: str) -> bool:
    return value is not None and fnmatch.fnmatchcase(value, pattern)


@dataclass(frozen=True, slots=True)
class Rule(Entity):
    """One design rule. Binary rules (clearance, creepage) use ``selector_b`` for the second object."""

    name: str
    kind: RuleKind
    selector_a: Selector
    selector_b: Selector | None = None
    layers: tuple[str, ...] = ()
    min: Nm | None = None
    opt: Nm | None = None
    max: Nm | None = None
    severity: RuleSeverity = "error"
    priority: int = 0


PlacementSeverity = Literal["error", "warning"]
"""The severity of a placement rule. A rule that judges nothing (``ignore``) is not a value."""


@dataclass(frozen=True, slots=True)
class PadSelection:
    """Pads of one part, named by its component path.

    Every pad of the part, those of one ``number``, or the one at ``index`` among the pads of that number
    in the footprint's pad order.
    """

    path: str
    number: str = ""
    index: int | None = None

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("a pad selection needs a component path")
        if self.index is not None:
            if isinstance(self.index, bool) or self.index < 0:
                raise ValueError("the index of a pad selection is a non-negative integer")
            if not self.number:
                raise ValueError("the index of a pad selection needs a pad number")


@dataclass(frozen=True, slots=True)
class ProximityRule:
    """A placement rule: each part of ``parts`` stays near a pad of ``anchor``.

    A part keeps one of its selected pads within ``within`` (nm, pad centre to pad centre) of a selected
    pad of ``anchor``. A value object of the rules layer: its ``name`` is its key, it has no id and no
    ``RuleKind``, and no backend lowers it.
    """

    name: str
    parts: tuple[PadSelection, ...] = field(metadata={"ordered": True})
    anchor: tuple[PadSelection, ...] = field(metadata={"ordered": True})
    within: Nm
    severity: PlacementSeverity = "error"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a proximity rule needs a name")
        if not self.parts:
            raise ValueError(f"proximity rule {self.name!r} names no part")
        if not self.anchor:
            raise ValueError(f"proximity rule {self.name!r} names no anchor")
        if isinstance(self.within, bool) or self.within <= 0:
            raise ValueError(f"proximity rule {self.name!r} needs a positive distance")
        if self.severity not in ("error", "warning"):
            raise ValueError(f"proximity rule {self.name!r}: severity is 'error' or 'warning'")


ImpedanceKind = Literal["single", "differential"]
"""A ``single`` target governs single-ended tracks; a ``differential`` one the two tracks of a pair, whose
rows carry a gap (change c0105)."""


@dataclass(frozen=True, slots=True)
class TraceGeometry:
    """One layer of an impedance target: the signal layer, its one or two reference layers in stack
    order, the track width and, for a differential target, the gap between the two tracks (nm).

    A value object of the rules layer; the geometry is always the user's (``docs/impedance.md``)."""

    layer: str
    references: tuple[str, ...] = field(metadata={"ordered": True})
    width: Nm
    gap: Nm | None = None


@dataclass(frozen=True, slots=True)
class ImpedanceTarget(Entity):
    """An impedance target of net classes (change c0105): its name, kind, the ids of the classes it
    governs, the target in ohms and its tolerance in percent as decimal text (``"90"``, ``"7.5"``; ``""``
    when not given), and one ``TraceGeometry`` per layer in stack order.

    ``ohms`` is ``""`` only for a target read from a file that gives none."""

    name: str
    kind: ImpedanceKind
    netclass_ids: tuple[str, ...] = field(metadata={"ordered": True})
    ohms: str
    tolerance_percent: str = ""
    layers: tuple[TraceGeometry, ...] = field(default=(), metadata={"ordered": True})


@dataclass(frozen=True, slots=True)
class HeightLimit:
    """A height limit: the parts under every rule area named ``area`` stay at most ``max`` tall.

    The height of a part is ``fenolite.model.board.outward_height`` of its footprint (change c0140). A
    value object of the rules layer: its ``area`` is its key, it has no id and no ``RuleKind``, and no
    backend lowers it.
    """

    area: str
    max: Nm
    severity: PlacementSeverity = "error"

    def __post_init__(self) -> None:
        if not self.area:
            raise ValueError("a height limit needs the name of a rule area")
        if isinstance(self.max, bool) or self.max <= 0:
            raise ValueError(f"height limit {self.area!r} needs a positive height")
        if self.severity not in ("error", "warning"):
            raise ValueError(f"height limit {self.area!r}: severity is 'error' or 'warning'")


RoleKind = Literal["power", "switch_node", "ground", "kelvin", "gate", "signal", "high_voltage"]
"""The kind of a net's role (change c0222; ``docs/roles.md``)."""
ROLE_KINDS: tuple[RoleKind, ...] = (
    "power",
    "switch_node",
    "ground",
    "kelvin",
    "gate",
    "signal",
    "high_voltage",
)
RoleSource = Literal["inferred", "confirmed", "declared"]
"""Where a role or a role group comes from: inferred by Fenolite, confirmed by the user through
``fenolite roles``, or declared by a design script."""
ROLE_SOURCES: tuple[RoleSource, ...] = ("inferred", "confirmed", "declared")
Confidence = Literal["", "high", "medium", "low"]
"""The confidence of an inferred role or group; ``""`` for one the user stated."""
CONFIDENCES: tuple[Confidence, ...] = ("", "high", "medium", "low")
ROLE_KEY = re.compile(r"^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$")
"""The pattern of a role group's name: the copper key pattern of the DSL (``dsl.intents.KEY``)."""
ROLE_LIMIT_UNITS: dict[str, str] = {
    "width_per_amp_nm": "nm per ampere",
    "milliamps_per_via": "mA",
    "kelvin_inner_edge": "flag (1 judges, 0 does not)",
    "kelvin_pair": "flag (1 judges, 0 does not)",
    "loop_ratio_max": "per mille",
    "loop_bound_floor_nm2": "nm²",
    "pair_ratio_max": "per mille",
    "switching_distance_nm": "nm",
    "gate_ratio_max": "per mille",
    "shunt_max_mohm": "mΩ",
    "high_voltage_mv": "mV",
    "loop_max": "nm²",
    "gate_max": "nm²",
    "temp_rise_mk": "mK",
}
"""The keys of a ``RoleLimit`` and the unit of each value. The defaults and their sources are the role
profile's (``fenolite.roles.profile``); ``high_voltage_mv``, ``loop_max``, ``gate_max`` and ``temp_rise_mk``
have none."""


def _pad_name(text: object) -> bool:
    if not isinstance(text, str):
        return False
    ref, dash, pin = text.rpartition("-")
    return bool(dash and ref and pin)


def _whole(value: object, what: str, *, positive: bool = False) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{what} must be an integer")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{what} must be {'above' if positive else 'at least'} 0")


def _check_origin(what: str, origin: object, confidence: object) -> None:
    if origin not in ROLE_SOURCES:
        raise ValueError(f"{what}: source {origin!r} is not one of {', '.join(ROLE_SOURCES)}")
    if confidence not in CONFIDENCES:
        raise ValueError(f"{what}: confidence {confidence!r} is not one of high, medium, low")


def _check_pads(what: str, pads: Sequence[str], count: int | None = None, least: int = 0) -> None:
    for pad in pads:
        if not _pad_name(pad):
            raise ValueError(f"{what}: {pad!r} is not a pad name REF-PIN")
    if count is not None and len(pads) != count:
        raise ValueError(f"{what}: names {len(pads)} pad(s), not {count}")
    if len(pads) < least:
        raise ValueError(f"{what}: names {len(pads)} pad(s); it needs at least {least}")
    if len(set(pads)) != len(pads):
        raise ValueError(f"{what}: names a pad twice")


def _check_name(what: str, name: object) -> None:
    if not isinstance(name, str) or not ROLE_KEY.fullmatch(name):
        raise ValueError(f"{what}: the name {name!r} must match {ROLE_KEY.pattern}")


@dataclass(frozen=True, slots=True)
class NetRole:
    """The role of one net (change c0222): its kind, where it comes from, the inference rule and its
    confidence (``""`` for a role the user stated), and the optional current (mA), working voltage against
    the design's ground (mV) and the ``sensitive`` flag of a ``signal``. A value object keyed by the net's
    name; no backend lowers it."""

    net: str
    kind: RoleKind
    source: RoleSource
    rule: str = ""
    confidence: Confidence = ""
    milliamps: int | None = None
    working_mv: int | None = None
    sensitive: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.net, str) or not self.net:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError("a net role needs a net name")
        if self.kind not in ROLE_KINDS:
            raise ValueError(
                f"net role {self.net!r}: kind {self.kind!r} is not one of {', '.join(ROLE_KINDS)}"
            )
        _check_origin(f"net role {self.net!r}", self.source, self.confidence)
        _whole(self.milliamps, f"net role {self.net!r}: milliamps", positive=True)
        _whole(self.working_mv, f"net role {self.net!r}: working_mv", positive=True)
        if self.sensitive and self.kind != "signal":
            raise ValueError(f"net role {self.net!r}: sensitive is a flag of a signal role")


@dataclass(frozen=True, slots=True)
class HotLoop:
    """A commutation loop (change c0222): its name and its pads (``REF-PIN``) in loop order, at least
    three. ``origin`` says where the group comes from, ``rule`` and ``confidence`` how it was inferred."""

    name: str
    pads: tuple[str, ...] = field(metadata={"ordered": True})
    origin: RoleSource = "declared"
    rule: str = ""
    confidence: Confidence = ""

    def __post_init__(self) -> None:
        _check_name("hot loop", self.name)
        _check_pads(f"hot loop {self.name!r}", self.pads, least=3)
        _check_origin(f"hot loop {self.name!r}", self.origin, self.confidence)


@dataclass(frozen=True, slots=True)
class KelvinPair:
    """A Kelvin connection (change c0222): the two sense pads of the shunt (``element``), the two inputs of
    the receiver (``receiver``), and for a four-terminal shunt its two force pads (``force``)."""

    name: str
    element: tuple[str, ...] = field(metadata={"ordered": True})
    receiver: tuple[str, ...] = field(metadata={"ordered": True})
    force: tuple[str, ...] = field(default=(), metadata={"ordered": True})
    origin: RoleSource = "declared"
    rule: str = ""
    confidence: Confidence = ""

    def __post_init__(self) -> None:
        _check_name("kelvin pair", self.name)
        what = f"kelvin pair {self.name!r}"
        _check_pads(f"{what}: element", self.element, 2)
        _check_pads(f"{what}: receiver", self.receiver, 2)
        if self.force:
            _check_pads(f"{what}: force", self.force, 2)
        if self.element[0].rpartition("-")[0] != self.element[1].rpartition("-")[0]:
            raise ValueError(f"{what}: both element pads must belong to one part")
        _check_pads(what, (*self.element, *self.receiver, *self.force))
        _check_origin(what, self.origin, self.confidence)

    @property
    def pads(self) -> tuple[str, ...]:
        """The pads of the pair's loop: element ``+``, receiver ``+``, receiver ``-``, element ``-``."""
        return (self.element[0], self.receiver[0], self.receiver[1], self.element[1])


@dataclass(frozen=True, slots=True)
class GateLoop:
    """A gate loop (change c0222): the driver's output pad, the switch's gate pad, its source pad (the
    Kelvin-source pad when the package has one), the driver's return pad, and the two pads of the gate
    resistor when there is one. The loop runs drive, resistor, gate, source, return."""

    name: str
    drive: str
    gate: str
    source: str
    ret: str
    resistor: tuple[str, ...] = field(default=(), metadata={"ordered": True})
    origin: RoleSource = "declared"
    rule: str = ""
    confidence: Confidence = ""

    def __post_init__(self) -> None:
        _check_name("gate loop", self.name)
        what = f"gate loop {self.name!r}"
        if self.resistor:
            _check_pads(f"{what}: resistor", self.resistor, 2)
        _check_pads(what, (self.drive, self.gate, self.source, self.ret, *self.resistor))
        if self.gate.rpartition("-")[0] != self.source.rpartition("-")[0]:
            raise ValueError(f"{what}: the gate and source pads must belong to one part")
        _check_origin(what, self.origin, self.confidence)

    @property
    def pads(self) -> tuple[str, ...]:
        """The pads in loop order: drive, the resistor's two pads, gate, source, return."""
        return (self.drive, *self.resistor, self.gate, self.source, self.ret)


@dataclass(frozen=True, slots=True)
class RoleLimit:
    """An override of a key of the role profile (change c0222) for the design, for one kind (``kind``) or
    for one net (``net``); the unit of ``value`` is the key's (``ROLE_LIMIT_UNITS``)."""

    key: str
    value: int
    net: str | None = None
    kind: RoleKind | None = None

    def __post_init__(self) -> None:
        if self.key not in ROLE_LIMIT_UNITS:
            raise ValueError(f"role limit: unknown key {self.key!r}; keys: {', '.join(ROLE_LIMIT_UNITS)}")
        if self.value is None:  # pyright: ignore[reportUnnecessaryComparison]
            raise ValueError(f"role limit {self.key!r} needs a value")
        _whole(self.value, f"role limit {self.key!r}")
        if self.net is not None and self.kind is not None:
            raise ValueError(f"role limit {self.key!r}: give a net or a kind, not both")
        if self.net is not None and not self.net:
            raise ValueError(f"role limit {self.key!r}: the net name is empty")
        if self.kind is not None and self.kind not in ROLE_KINDS:
            raise ValueError(
                f"role limit {self.key!r}: kind {self.kind!r} is not one of {', '.join(ROLE_KINDS)}"
            )


PartClassName = Literal[
    "transistor",
    "diode",
    "inductor",
    "capacitor",
    "resistor",
    "shunt",
    "driver",
    "amplifier",
    "controller",
    "connector",
    "net_tie",
    "other",
]
"""The class of a part for the inference of net roles (change c0222; ``fenolite.roles.classify``)."""
PART_CLASSES: tuple[PartClassName, ...] = (
    "transistor",
    "diode",
    "inductor",
    "capacitor",
    "resistor",
    "shunt",
    "driver",
    "amplifier",
    "controller",
    "connector",
    "net_tie",
    "other",
)
PART_TERMINALS: dict[str, tuple[str, ...]] = {
    "transistor": ("gate", "drain", "source", "kelvin_source"),
    "diode": ("anode", "cathode"),
    "shunt": ("force", "sense"),
    "amplifier": ("in_p", "in_n", "out"),
    "driver": ("drive", "ret", "sw", "in_p", "in_n"),
    "controller": ("drive", "ret", "sw", "in_p", "in_n"),
}
"""The terminals of each class that has any; a terminal names one or more pins of the part."""


@dataclass(frozen=True, slots=True)
class Terminal:
    """A terminal of a part class and the pins (numbers) it names."""

    name: str
    pins: tuple[str, ...] = field(metadata={"ordered": True})

    def __post_init__(self) -> None:
        if not self.pins or not all(isinstance(pin, str) and pin for pin in self.pins):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError(f"terminal {self.name!r} names no pin")


@dataclass(frozen=True, slots=True)
class PartClass:
    """The class of a part that the user states (change c0222; ``design.part_class``, ``--class``): the
    reference, the class and, for a class with terminals, which pins are which terminal. The strongest
    evidence of the inference; a value keyed by the reference."""

    ref: str
    cls: PartClassName
    terminals: tuple[Terminal, ...] = field(default=(), metadata={"ordered": True})

    def __post_init__(self) -> None:
        if not isinstance(self.ref, str) or not self.ref:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError("a part class needs a reference")
        if self.cls not in PART_CLASSES:
            raise ValueError(f"part class {self.ref!r}: {self.cls!r} is not one of {', '.join(PART_CLASSES)}")
        allowed = PART_TERMINALS.get(self.cls, ())
        names = [terminal.name for terminal in self.terminals]
        for name in names:
            if name not in allowed:
                shown = ", ".join(allowed) or "none"
                raise ValueError(
                    f"part class {self.ref!r}: {self.cls} has no terminal {name!r} (terminals: {shown})"
                )
        if len(set(names)) != len(names):
            raise ValueError(f"part class {self.ref!r}: a terminal is named twice")


def _limit_order(limit: RoleLimit) -> tuple[str, str, str]:
    return (limit.key, limit.kind or "", limit.net or "")


@dataclass(frozen=True, slots=True)
class RoleSet:
    """The net roles of a design (change c0222): one role per net, the three kinds of role groups, the
    limit overrides, the part classes the user states and the names of the inferred groups the user rejected,
    each sorted by its key (a net role by its net, a group by its name, a limit by key, kind and net, a class
    by its reference). A value, not an entity;
    ``RuleSet`` stores it under ``roles``, and the role document ``fenolite.roles.v0`` beside a board holds
    one."""

    nets: tuple[NetRole, ...] = field(default=(), metadata={"ordered": True})
    loops: tuple[HotLoop, ...] = field(default=(), metadata={"ordered": True})
    kelvins: tuple[KelvinPair, ...] = field(default=(), metadata={"ordered": True})
    gates: tuple[GateLoop, ...] = field(default=(), metadata={"ordered": True})
    limits: tuple[RoleLimit, ...] = field(default=(), metadata={"ordered": True})
    classes: tuple[PartClass, ...] = field(default=(), metadata={"ordered": True})
    rejected: tuple[str, ...] = field(default=(), metadata={"ordered": True})

    def __post_init__(self) -> None:
        object.__setattr__(self, "classes", tuple(sorted(self.classes, key=lambda found: found.ref)))
        object.__setattr__(self, "rejected", tuple(sorted(set(self.rejected))))
        for name in self.rejected:
            _check_name("rejected group", name)
        object.__setattr__(self, "nets", tuple(sorted(self.nets, key=lambda role: role.net)))
        object.__setattr__(self, "loops", tuple(sorted(self.loops, key=lambda group: group.name)))
        object.__setattr__(self, "kelvins", tuple(sorted(self.kelvins, key=lambda group: group.name)))
        object.__setattr__(self, "gates", tuple(sorted(self.gates, key=lambda group: group.name)))
        object.__setattr__(self, "limits", tuple(sorted(self.limits, key=_limit_order)))
        for what, names in (
            ("net roles", [role.net for role in self.nets]),
            ("hot loops", [group.name for group in self.loops]),
            ("kelvin pairs", [group.name for group in self.kelvins]),
            ("gate loops", [group.name for group in self.gates]),
            ("role limits", ["/".join(_limit_order(limit)) for limit in self.limits]),
            ("part classes", [found.ref for found in self.classes]),
        ):
            twice = sorted({name for name in names if names.count(name) > 1})
            if twice:
                raise ValueError(f"two {what} have the key {twice[0]!r}")

    def __bool__(self) -> bool:
        return bool(
            self.nets
            or self.loops
            or self.kelvins
            or self.gates
            or self.limits
            or self.classes
            or self.rejected
        )

    def role_of(self, net: str) -> NetRole | None:
        """The role of ``net``, or ``None``."""
        return next((role for role in self.nets if role.net == net), None)


@dataclass(frozen=True, slots=True)
class RuleSet(Entity):
    """The rules layer of a design (``rules.json``). ``severities`` gives the checks of a design-rule tool
    a severity, by the finding code of the check (``<oracle>.drc.<suffix>``; change c0114): a severity is
    not a rule, so it has no ``RuleKind``.

    ``proximity`` holds the placement rules, in name order; it is left out of the file when empty
    (change c0113). ``heights`` holds the height limits, in area order, left out when empty (change c0140).
    ``impedance`` holds the impedance targets in declaration order; it is left out of the file when empty
    (change c0105). ``roles`` holds the net roles (change c0222); an empty ``RoleSet`` is stored as ``None``,
    so the key is left out of the file.
    """

    rules: tuple[Rule, ...] = ()
    severities: dict[str, RuleSeverity] = field(default_factory=lambda: {})
    proximity: tuple[ProximityRule, ...] = field(default=(), metadata={"ordered": True})
    heights: tuple[HeightLimit, ...] = field(default=(), metadata={"ordered": True})
    impedance: tuple[ImpedanceTarget, ...] = field(default=(), metadata={"ordered": True})
    roles: RoleSet | None = None

    def __post_init__(self) -> None:
        if self.roles is not None and not self.roles:
            object.__setattr__(self, "roles", None)
        seen: set[str] = set()
        for rule in self.proximity:
            if rule.name in seen:
                raise ValueError(f"two proximity rules are named {rule.name!r}")
            seen.add(rule.name)
        areas: set[str] = set()
        for limit in self.heights:
            if limit.area in areas:
                raise ValueError(f"two height limits name the area {limit.area!r}")
            areas.add(limit.area)


__all__ = [
    "CONFIDENCES",
    "LEAF_OPS",
    "ROLE_KEY",
    "ROLE_KINDS",
    "ROLE_LIMIT_UNITS",
    "ROLE_SOURCES",
    "Confidence",
    "GateLoop",
    "HeightLimit",
    "HotLoop",
    "ImpedanceKind",
    "ImpedanceTarget",
    "KelvinPair",
    "NetRole",
    "PART_CLASSES",
    "PART_TERMINALS",
    "PadSelection",
    "PartClass",
    "PartClassName",
    "PlacementSeverity",
    "ProximityRule",
    "RoleKind",
    "RoleLimit",
    "RoleSet",
    "RoleSource",
    "Rule",
    "RuleKind",
    "RuleSet",
    "RuleSeverity",
    "RuleSubject",
    "Selector",
    "SelectorOp",
    "Terminal",
    "TraceGeometry",
]
