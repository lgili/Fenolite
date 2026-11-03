# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Typed public documents introduced by the final pre-activation source union."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fenolite.cli.file_formats import Document

Pair = tuple[int, int]


@dataclass(frozen=True, kw_only=True)
class RouteEnd:
    kind: str
    name: str
    layers: list[str]
    at: Pair = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class RouteTrack:
    kind: Literal["track"]
    layer: str
    width: int
    points: list[Pair]


@dataclass(frozen=True, kw_only=True)
class RouteVia:
    kind: Literal["via"]
    at: Pair
    diameter: int
    drill: int
    layers: list[str]


@dataclass(frozen=True, kw_only=True)
class RouteCorridor:
    name: str
    layers: list[str]
    outline: list[Pair]


@dataclass(frozen=True, kw_only=True)
class RouteLocked:
    candidate: str
    proposal: str
    subject: str
    net: str
    ends: list[RouteEnd]
    items: list[RouteTrack | RouteVia]
    corridors: list[RouteCorridor]
    relaxed: list[str]
    plan: str


@dataclass(frozen=True, kw_only=True)
class RouteRejected:
    id: str
    subject: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class RouteDecisionsFile(Document):
    board: str
    locked: list[RouteLocked]
    rejected: list[RouteRejected]


@dataclass(frozen=True, kw_only=True)
class SupplierProvenance:
    source: str
    query: str
    retrieved: str
    attribution: str
    decoded_by: str = ""


@dataclass(frozen=True, kw_only=True)
class SupplierDecoded:
    device_toml: str


@dataclass(frozen=True, kw_only=True)
class SupplierProposalFile(Document):
    evidence: Literal["UNVERIFIED"]
    licence: str
    mpn: str
    provenance: SupplierProvenance
    manufacturer: str = ""
    datasheet: str = ""
    decoded: SupplierDecoded = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ObservationF0:
    case: str
    file: str
    sha256: str
    elements: int
    sheets: int
    items: dict[str, int]
    control: str | None
    changed_members: list[str] | None


@dataclass(frozen=True, kw_only=True)
class ObservationJ:
    case: str
    file: str
    sha256: str
    control: str | None
    changes_by_kind: dict[str, int] | None
    resave_changes: int | None


@dataclass(frozen=True, kw_only=True)
class AltiumObservationsFile(Document):
    round: Literal["F0", "J"]
    native_verdict: Literal["unjudged"]
    evidence: Literal["INFERRED"]
    privacy_scan: Literal["passed"]
    files: list[ObservationF0 | ObservationJ]
    missing: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class SymbolContext:
    sheet: str
    native_id: str
    asset: str
    asset_sha256: str = field(metadata={"pattern": r"^[0-9a-f]{64}$"})
    definition_sha256: str = field(metadata={"pattern": r"^[0-9a-f]{64}$"})
    input: str
    input_sha256: str = field(metadata={"pattern": r"^[0-9a-f]{64}$"})
    binding_sha256: str = field(metadata={"pattern": r"^[0-9a-f]{64}$"})


@dataclass(frozen=True, kw_only=True)
class SymbolContextsFile(Document):
    drawing: str
    target: Literal[9, 10]
    symbol: list[SymbolContext] = field(metadata={"minItems": 1})
