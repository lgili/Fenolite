# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The wire shape of the ``result`` of ``fenolite equivalent`` (capability design-equivalence, "Equivalent
result schema"; change c0158).

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


__all__ = ["KIND_NAMES", "NETLIST_SOURCES", "EquivalentReply"]
