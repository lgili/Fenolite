# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Canonical block records, shared by result and public block-data schemas."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BlockDeprecation:
    by: str
    since: str
    reason: str


@dataclass(frozen=True)
class BlockParameter:
    name: str
    type: str
    unit: str | None
    required: bool
    default: str | None
    min: str | None
    max: str | None
    choices: list[str | None] | None
    doc: str


@dataclass(frozen=True)
class BlockPort:
    name: str
    kind: str
    direction: str
    optional: bool
    members: list[str]
    doc: str


@dataclass(frozen=True)
class BlockNested:
    name: str
    block: str


@dataclass(frozen=True)
class BlockRequires:
    devices: list[str]
    lib_ids: list[str]
    queries: list[str]


@dataclass(frozen=True)
class BlockElaboration:
    reason: str = field(metadata={"optional": True})
    error: str = field(metadata={"optional": True})


@dataclass(frozen=True)
class BlockDigests:
    definition: str
    interface: str
    record: str


@dataclass(frozen=True)
class BlockData:
    schema: str
    name: str
    id: str | None
    version: str | None
    summary: str | None
    category: str | None
    licence: str | None
    evidence: str | None
    replaces: str | None
    deprecated: BlockDeprecation | None
    sources: list[str]
    params: list[BlockParameter]
    ports: list[BlockPort] | None
    parts: list[str] | None
    nets: list[str] | None
    blocks: list[BlockNested] | None
    requires: BlockRequires | None
    elaboration: BlockElaboration | None
    digests: BlockDigests


@dataclass(frozen=True)
class BlockShown(BlockData):
    source: str
    where: str
    layout: str | None
    usage: str | None
    tests: str | None
    golden: str | None
