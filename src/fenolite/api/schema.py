# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The wire shapes of the ``result`` of ``fenolite equivalent`` (capability design-equivalence, "Equivalent
result schema"; change c0158) and of ``fenolite convert`` (capability design-conversion, "Convert result and
exit codes"; change c0159).

``tools/gen_schemas.py`` writes ``schemas/fenolite.equivalent.v0.json`` from ``EquivalentReply``; nothing
builds a reply from these classes (``EquivalenceResult.to_json`` does), they only describe it. The kinds of
difference are the closed table ``checks.equivalence.model.KINDS``. A key added to the reply needs its field
here in the same commit: the consistency suite validates every reply against the schema.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Literal

from fenolite.checks.equivalence.model import KINDS, LEVEL_NAMES

KIND_NAMES: tuple[str, ...] = tuple(dict.fromkeys(kind for _, kind, _ in KINDS))
NETLIST_SOURCES = ("board", "circuit", "schematic")
_COUNT = {"minimum": 0}


@dataclass(frozen=True)
class ReplySide:
    """One side of the comparison."""

    path: str = dataclasses.field(metadata={"description": "the file or folder name, without its folder"})
    sha256: str | None = dataclasses.field(metadata={"pattern": "^[0-9a-f]{64}$"})
    backend: str
    netlist_source: str = dataclasses.field(metadata={"enum": list(NETLIST_SOURCES)})
    components: int = dataclasses.field(metadata=_COUNT)
    footprints: int = dataclasses.field(metadata=_COUNT)
    tool_version: str = dataclasses.field(
        default="", metadata={"optional": True, "description": "kicad-cli of the triangle's side b"}
    )
    power_symbols: int = dataclasses.field(
        default=0,
        metadata={"optional": True, "minimum": 0, "description": "a schematic side's power symbols"},
    )


@dataclass(frozen=True)
class ReplySides:
    """The two sides; ``b`` is null when the triangle's converter gave no board."""

    a: ReplySide
    b: ReplySide | None


@dataclass(frozen=True)
class ReplyTolerances:
    """The tolerances of the comparison."""

    length_nm: int = dataclasses.field(metadata=_COUNT)
    angle_udeg: int = dataclasses.field(metadata=_COUNT)
    length_ppm: int = dataclasses.field(metadata=_COUNT)


@dataclass(frozen=True)
class ReplyLevel:
    """One level that ran, with its counts and summary."""

    level: int = dataclasses.field(metadata={"minimum": 1})
    name: str = dataclasses.field(metadata={"enum": list(LEVEL_NAMES.values())})
    compared: int = dataclasses.field(metadata=_COUNT)
    differences: int = dataclasses.field(metadata=_COUNT)
    excluded: int = dataclasses.field(metadata=_COUNT)
    notices: int = dataclasses.field(metadata=_COUNT)
    summary: dict[str, Any]


@dataclass(frozen=True)
class ReplyDifference:
    """A difference or a notice, located at ``REF``, ``REF-PIN`` or a net."""

    level: int = dataclasses.field(metadata={"minimum": 1})
    kind: str = dataclasses.field(metadata={"enum": list(KIND_NAMES)})
    where: str
    field: str
    a: str
    b: str


@dataclass(frozen=True)
class ReplyExcluded:
    """A difference that a rule of the profile excluded."""

    level: int = dataclasses.field(metadata={"minimum": 1})
    kind: str = dataclasses.field(metadata={"enum": list(KIND_NAMES)})
    where: str
    field: str
    a: str
    b: str
    rule: str


@dataclass(frozen=True)
class ReplyProfile:
    """The exclusion profile applied."""

    name: str
    tool_version: str
    rules: int = dataclasses.field(metadata=_COUNT)


@dataclass(frozen=True)
class EquivalentReply:
    """The result of fenolite equivalent."""

    level: int = dataclasses.field(
        metadata={"minimum": 0, "description": "the highest level run; 0 when none ran"}
    )
    equivalent: bool
    sides: ReplySides
    tolerances: ReplyTolerances
    frame: Literal["absolute", "relative"]
    translation: tuple[int, int]
    levels: list[ReplyLevel]
    differences: list[ReplyDifference]
    notices: list[ReplyDifference]
    excluded: list[ReplyExcluded]
    profile: ReplyProfile | None
    tool_version: str = dataclasses.field(
        default="",
        metadata={"optional": True, "description": "kicad-cli of a triangle whose converter gave no board"},
    )


@dataclass(frozen=True)
class ReplyExplained:
    """A difference of the read-back that a lost item of the report explains."""

    level: int = dataclasses.field(metadata={"minimum": 1})
    kind: str = dataclasses.field(metadata={"enum": list(KIND_NAMES)})
    where: str
    field: str
    a: str
    b: str
    by: str = dataclasses.field(metadata={"description": "the kind of the lost item, or source"})


@dataclass(frozen=True)
class ConvertEquivalence(EquivalentReply):
    """The verification of a conversion: the reply of fenolite equivalent with the explained differences."""

    explained: list[ReplyExplained] = dataclasses.field(default_factory=lambda: [])
    unexplained: int = dataclasses.field(default=0, metadata=_COUNT)


@dataclass(frozen=True)
class ConvertSource:
    """The source as read: the file read, its backend and input kind, and a KiCad board's format version."""

    path: str
    backend: str
    kind: str
    format_version: int | None


@dataclass(frozen=True)
class ConvertTarget:
    """The target backend, and the KiCad major of a KiCad target."""

    backend: Literal["kicad", "altium"]
    major: int | None


@dataclass(frozen=True)
class ConvertFile:
    """One file of the converted project."""

    name: str
    bytes: int = dataclasses.field(metadata=_COUNT)


@dataclass(frozen=True)
class ReportReason:
    """The items of one kind changed or lost for one reason."""

    reason: str
    outcome: Literal["changed", "lost"]
    count: int = dataclasses.field(metadata={"minimum": 1})
    ids: list[str] = dataclasses.field(
        default_factory=lambda: [], metadata={"optional": True, "description": "with --report-ids"}
    )


@dataclass(frozen=True)
class ReportRowReply:
    """One kind of the report."""

    kind: str
    group: Literal["circuit", "footprint", "copper", "board", "presentation", "project", "downgrade"]
    loss: Literal["refuse", "report"]
    source: int = dataclasses.field(metadata=_COUNT)
    written: int = dataclasses.field(metadata=_COUNT)
    changed: int = dataclasses.field(metadata=_COUNT)
    lost: int = dataclasses.field(metadata=_COUNT)
    reasons: list[ReportReason] = dataclasses.field(default_factory=lambda: [])


@dataclass(frozen=True)
class ReportReply:
    """The conversion report."""

    lossy: bool
    refused: list[str]
    rows: list[ReportRowReply]


@dataclass(frozen=True)
class ConvertReply:
    """The result of fenolite convert."""

    source: ConvertSource
    target: ConvertTarget
    files: list[ConvertFile]
    report: ReportReply
    equivalence: ConvertEquivalence | None
    experimental: bool
    plan: list[dict[str, Any]] = dataclasses.field(
        default_factory=lambda: [], metadata={"optional": True, "description": "the planned writes"}
    )
    plan_id: str = dataclasses.field(
        default="", metadata={"optional": True, "description": "the id of the staged plan"}
    )


__all__ = ["KIND_NAMES", "NETLIST_SOURCES", "ConvertReply", "EquivalentReply"]
