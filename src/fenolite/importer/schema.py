# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The wire shape of the ``result`` of ``fenolite import`` (change c0275, design decision 15).

``tools/gen_schemas.py`` writes ``schemas/fenolite.import.v0.json`` from ``ImportReply``; nothing builds a
reply from these classes (``cli/cmd_import.py`` does), they only describe it, and the consistency suite
validates every reply against the schema.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Literal

_COUNT = {"minimum": 0}


@dataclass(frozen=True)
class ImportSource:
    """The board read: its file name, the backend and the format version of each input that has one."""

    file: str
    backend: str
    versions: dict[str, int]


@dataclass(frozen=True)
class ImportFile:
    """One file of the project folder, relative to ``--out``."""

    path: str
    bytes: int = dataclasses.field(metadata=_COUNT)


@dataclass(frozen=True)
class ImportCounts:
    """What the emitted code holds."""

    parts: int = dataclasses.field(metadata=_COUNT)
    nets: int = dataclasses.field(metadata=_COUNT)
    tracks: int = dataclasses.field(metadata=_COUNT)
    arcs: int = dataclasses.field(metadata=_COUNT)
    vias: int = dataclasses.field(metadata=_COUNT)
    zones: int = dataclasses.field(metadata=_COUNT)
    rule_areas: int = dataclasses.field(metadata=_COUNT)
    drawings: int = dataclasses.field(metadata=_COUNT)
    tables: int = dataclasses.field(metadata=_COUNT)


@dataclass(frozen=True)
class ImportUnexpressed:
    """One kind of item no DSL call expresses, its count and up to three examples."""

    kind: str
    count: int = dataclasses.field(metadata={"minimum": 1})
    examples: list[str] = dataclasses.field(default_factory=lambda: [])


@dataclass(frozen=True)
class ImportUpgrade:
    """One file upgraded by ``kicad-cli`` on a private copy."""

    file: str
    tool: str
    tool_version: str
    from_version: int
    to_version: int | None
    sha256_before: str
    sha256_after: str


@dataclass(frozen=True)
class ImportEquivalence:
    """The self-check: the levels compared and whether every difference is explained."""

    levels: list[int]
    equivalent: bool


@dataclass(frozen=True)
class ImportProvenance:
    """The upstream as the command line states it."""

    licence: str
    source: str | None
    revision: str | None


@dataclass(frozen=True)
class ImportReportReason:
    """The items of one kind changed, lost or kept for one reason (``ReportReason`` of ``convert``)."""

    reason: str
    outcome: Literal["changed", "lost", "kept"]
    count: int = dataclasses.field(metadata={"minimum": 1})
    ids: list[str] = dataclasses.field(
        default_factory=lambda: [], metadata={"optional": True, "description": "with --report-ids"}
    )


@dataclass(frozen=True)
class ImportReportRow:
    """One kind of the conversion report (``ReportRowReply`` of ``convert``)."""

    kind: str
    group: Literal["circuit", "footprint", "copper", "board", "presentation", "project", "downgrade"]
    loss: Literal["refuse", "report"]
    source: int = dataclasses.field(metadata=_COUNT)
    written: int = dataclasses.field(metadata=_COUNT)
    changed: int = dataclasses.field(metadata=_COUNT)
    lost: int = dataclasses.field(metadata=_COUNT)
    kept: int = dataclasses.field(
        default=0,
        metadata={
            **_COUNT,
            "optional": True,
            "description": "items kept in the model for the source's format; shown when above 0 (c0424)",
        },
    )
    reasons: list[ImportReportReason] = dataclasses.field(default_factory=lambda: [])


@dataclass(frozen=True)
class ImportReport:
    """The report of the conversion an Altium source goes through (``ReportReply`` of ``convert``, change
    c0429). The importer may not import ``fenolite.api``, so the shape is repeated here; a unit test keeps
    the two equal."""

    lossy: bool
    refused: list[str]
    rows: list[ImportReportRow]


@dataclass(frozen=True)
class ImportReply:
    """The result of fenolite import."""

    source: ImportSource
    out: str
    design: str
    files: list[ImportFile]
    modules: list[str]
    counts: ImportCounts
    unexpressed: list[ImportUnexpressed]
    upgrade: list[ImportUpgrade]
    equivalence: ImportEquivalence | None
    provenance: ImportProvenance
    adopted: dict[str, Any] | None
    plan: list[dict[str, Any]] = dataclasses.field(
        default_factory=lambda: [], metadata={"optional": True, "description": "the planned writes"}
    )
    plan_id: str = dataclasses.field(
        default="", metadata={"optional": True, "description": "the id of the staged plan"}
    )
    page: dict[str, Any] = dataclasses.field(
        default_factory=lambda: {}, metadata={"optional": True, "description": "with --limit"}
    )
    report: ImportReport | None = dataclasses.field(
        default=None,
        metadata={
            "optional": True,
            "description": "the conversion report of an Altium source, null for a KiCad source (c0429)",
        },
    )


__all__ = ["ImportReply"]
