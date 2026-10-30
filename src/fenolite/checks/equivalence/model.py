# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The values of a design comparison (capability design-equivalence, "Differences are located").

A comparison runs the levels 1 to N in order and gives, per level, the differences it found and those
that a rule excluded. Every value is an integer or a string: lengths in nanometres and angles in
microdegrees, as in the model.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from fenolite.core.coords import Point

LEVELS: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7)
LEVEL_NAMES: Mapping[int, str] = MappingProxyType(
    {
        1: "components",
        2: "netlist",
        3: "footprints",
        4: "placement",
        5: "routing",
        6: "rules",
        7: "geometry",
    }
)
"""The levels ``compare_designs`` runs, with their names."""
PRESENTATION_LEVEL = 8
"""The level that renders both sides and compares the pictures (``view.fidelity``); ``compare_designs`` never
runs it."""
SCHEMATIC_LEVEL = "S"
"""The level that compares two drawn schematics; ``compare_designs`` never runs it."""
LevelId = int | str
"""A level: an integer of 1 to 8, or ``SCHEMATIC_LEVEL``."""
ALL_LEVEL_NAMES: Mapping[LevelId, str] = MappingProxyType(
    {**LEVEL_NAMES, PRESENTATION_LEVEL: "presentation", SCHEMATIC_LEVEL: "schematic"}
)
"""Every level a difference may name, with its name."""
Frame = Literal["absolute", "relative"]
FRAMES: tuple[Frame, ...] = ("absolute", "relative")
KINDS: tuple[tuple[LevelId, str, str], ...] = (
    (1, "component-missing", "ref"),
    (1, "ref-ambiguous", "ref"),
    (1, "value", "value"),
    (1, "dnp", "dnp"),
    (2, "pin-missing", "pin"),
    (2, "net", "net"),
    (3, "footprint-missing", "footprint"),
    (3, "footprint-name", "lib_ref"),
    (3, "pad-missing", "pad"),
    (3, "pad-kind", "kind"),
    (3, "pad-shape", "shape"),
    (3, "pad-size", "size"),
    (3, "pad-drill", "drill"),
    (3, "pad-position", "position"),
    (3, "pad-rotation", "rotation"),
    (3, "pad-copper", "layers"),
    (4, "side", "side"),
    (4, "position", "position"),
    (4, "rotation", "rotation"),
    (5, "route-missing", "copper"),
    (5, "route-connectivity", "pads"),
    (5, "route-vias", "vias"),
    (5, "route-length", "length"),
    (5, "route-stub", "stubs"),
    (5, "route-unjudged", "zones"),
    (5, "track-missing", "track"),
    (5, "track-width", "width"),
    (5, "track-net", "net"),
    (5, "arc-missing", "arc"),
    (5, "arc-width", "width"),
    (5, "arc-net", "net"),
    (5, "via-missing", "via"),
    (5, "via-size", "diameter"),
    (5, "via-drill", "drill"),
    (5, "via-span", "layers"),
    (5, "via-net", "net"),
    (5, "copper-locked", "locked"),
    (6, "netclass-missing", "name"),
    (6, "netclass-field", "field"),
    (6, "netclass-members", "nets"),
    (6, "rule-missing", "name"),
    (6, "rule-field", "field"),
    (6, "ruleset-field", "field"),
    (6, "stackup-missing", "layer"),
    (6, "stackup-field", "field"),
    (6, "layer-missing", "layer"),
    (7, "outline-missing", "ring"),
    (7, "zone-missing", "zone"),
    (7, "zone-field", "field"),
    (7, "keepout-missing", "keepout"),
    (7, "keepout-field", "field"),
    (7, "graphic-missing", "graphic"),
    (7, "text-missing", "text"),
    (7, "text-field", "field"),
    (7, "field-pose", "field"),
    (7, "hole-missing", "hole"),
    (7, "dimension-missing", "dimension"),
    (8, "render-missing", "layer"),
    (8, "render-pixels", "pixels"),
    ("S", "sheet-missing", "sheet"),
    ("S", "symbol-missing", "symbol"),
    ("S", "symbol-pose", "field"),
    ("S", "symbol-field", "field"),
    ("S", "item-missing", "item"),
    ("S", "item-field", "field"),
    ("S", "drawn-net", "net"),
)
"""Every kind of difference as ``(level, kind, field)``; the table is closed. A ``field`` of ``field`` or
``item`` is a placeholder: the difference names the dotted path of the field (``settings.clearance``) or the
item kind (``junction``) that differs, so the table stays closed while the model grows."""
FREE_FIELDS = frozenset({"field", "item"})
"""The placeholders of the field column: a difference of such a kind carries its own field."""
KIND_LEVELS: Mapping[str, tuple[LevelId, ...]] = MappingProxyType(
    {
        kind: tuple(level for level, name, _ in KINDS if name == kind)
        for kind in dict.fromkeys(name for _, name, _ in KINDS)
    }
)
"""The levels of each kind name (``rotation`` is a kind of level 4 only; a pad's is ``pad-rotation``)."""
NOTICE_SEVERITY: Mapping[str, Literal["warning", "info"]] = MappingProxyType(
    {"route-stub": "warning", "route-unjudged": "info", "copper-locked": "warning"}
)
"""The kinds that are notices, with their severity: they are reported and located as differences are,
and they never make two designs unequal. Every other kind is an error."""


@dataclass(frozen=True, slots=True)
class Tolerances:
    """How far two lengths (per coordinate) and two angles (on the circle) may differ and stay equal.
    ``length_ppm`` is relative to a routed length of level 5 and applies to nothing else: two routed
    lengths are equal within the larger of ``length_nm`` and that share of the longer one."""

    length_nm: int = 0
    angle_udeg: int = 0
    length_ppm: int = 0

    def __post_init__(self) -> None:
        for name, value in (
            ("length_nm", self.length_nm),
            ("angle_udeg", self.angle_udeg),
            ("length_ppm", self.length_ppm),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} is a non-negative integer, got {value!r}")


EXACT = Tolerances()
"""No tolerance: the default of every comparison."""


@dataclass(frozen=True, slots=True)
class Difference:
    """One located difference. ``where`` is ``REF`` or ``REF-PIN``, and at level 5 the net's name on side
    ``a``, followed by ``:`` and the first pads of a pad set; ``a`` and ``b`` are the two values as exact
    strings, ``""`` for a missing object."""

    level: LevelId
    kind: str
    where: str
    field: str
    a: str
    b: str


@dataclass(frozen=True, slots=True)
class Excluded:
    """A difference that a rule matched, with the rule's id and reason. It never fails a comparison."""

    difference: Difference
    rule_id: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class LevelResult:
    """One level: the count of compared objects, the differences in ``(where, kind, field)`` order, those
    a rule excluded, the level's counts, and its notices (the kinds of ``NOTICE_SEVERITY``), which fail
    nothing."""

    level: LevelId
    compared: int
    differences: tuple[Difference, ...] = ()
    excluded: tuple[Excluded, ...] = ()
    summary: Mapping[str, object] = field(default_factory=lambda: {})
    notices: tuple[Difference, ...] = ()

    @property
    def name(self) -> str:
        return ALL_LEVEL_NAMES[self.level]


@dataclass(frozen=True, slots=True)
class EquivalenceReport:
    """The levels that ran, in order, with the tolerances, the frame and the translation removed from
    side ``b`` (``(0, 0)`` in the absolute frame and below level 4)."""

    levels: tuple[LevelResult, ...]
    tolerances: Tolerances = EXACT
    frame: Frame = "absolute"
    translation: Point = Point(0, 0)

    @property
    def equivalent(self) -> bool:
        """True when no level holds a difference that no rule excludes."""
        return not any(level.differences for level in self.levels)

    @property
    def differences(self) -> tuple[Difference, ...]:
        return tuple(d for level in self.levels for d in level.differences)

    @property
    def excluded(self) -> tuple[Excluded, ...]:
        return tuple(e for level in self.levels for e in level.excluded)

    @property
    def notices(self) -> tuple[Difference, ...]:
        return tuple(d for level in self.levels for d in level.notices)


__all__ = [
    "ALL_LEVEL_NAMES",
    "EXACT",
    "FREE_FIELDS",
    "PRESENTATION_LEVEL",
    "SCHEMATIC_LEVEL",
    "LevelId",
    "FRAMES",
    "KINDS",
    "KIND_LEVELS",
    "LEVELS",
    "LEVEL_NAMES",
    "NOTICE_SEVERITY",
    "Difference",
    "EquivalenceReport",
    "Excluded",
    "Frame",
    "LevelResult",
    "Tolerances",
]
