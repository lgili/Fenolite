# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite-artifacts.json``: which file came from which board, by which tool, with its hashes
(capability manufacturing-exports, "Artefact manifest"; schema ``schemas/fenolite.artifacts.v0.json``).

KiCad stamps the creation date into Gerber and drill files, so two exports of one board are not
byte-equal. ``content_sha256`` is the hash of a file without those lines: equal for two exports of an
unchanged board. The files themselves are never edited.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fenolite import __version__
from fenolite.exports import EVIDENCE
from fenolite.exports.plan import VOLATILE_PREFIXES, Artifact

SCHEMA = "fenolite.artifacts.v0"
FILE_NAME = "fenolite-artifacts.json"
_SHA = {"pattern": "^[0-9a-f]{64}$"}


@dataclass(frozen=True, slots=True)
class BoardRef:
    """The board the artefacts were made from."""

    path: str
    sha256: str = dataclasses.field(metadata=_SHA)
    format_version: int | None


@dataclass(frozen=True, slots=True)
class ToolRef:
    """The tool that wrote the artefacts."""

    name: str
    version: str


@dataclass(frozen=True, slots=True)
class ArtifactEntry:
    """One artefact: its path below the manifest's folder, its kind, the layer of a Gerber, its size, the
    hash of its bytes, the hash without date-bearing lines, and the evidence level of the entry."""

    path: str
    kind: str
    layer: str | None
    bytes: int = dataclasses.field(metadata={"minimum": 0})
    sha256: str = dataclasses.field(metadata=_SHA)
    content_sha256: str = dataclasses.field(metadata=_SHA)
    evidence: str


@dataclass(frozen=True, slots=True)
class Manifest:
    """The artefact manifest of ``fenolite export --manifest``."""

    schema: str
    fenolite: str
    generated: str
    board: BoardRef
    tool: ToolRef
    artifacts: list[ArtifactEntry]


def content_sha256(data: bytes, kind: str) -> str:
    """The SHA-256 of ``data`` without the lines that carry the creation date for ``kind``."""
    prefixes = VOLATILE_PREFIXES.get(kind, ())
    if not prefixes:
        return hashlib.sha256(data).hexdigest()
    kept = [line for line in data.splitlines(keepends=True) if not line.lstrip(b" \t").startswith(prefixes)]
    return hashlib.sha256(b"".join(kept)).hexdigest()


def entry(artifact: Artifact) -> ArtifactEntry:
    return ArtifactEntry(
        path=artifact.path,
        kind=artifact.kind,
        layer=artifact.layer,
        bytes=len(artifact.data),
        sha256=hashlib.sha256(artifact.data).hexdigest(),
        content_sha256=content_sha256(artifact.data, artifact.kind),
        evidence=EVIDENCE.level.value,
    )


def build(
    *, board: BoardRef, tool_version: str, artifacts: Sequence[Artifact], timestamp: datetime
) -> dict[str, Any]:
    """The manifest as JSON data, its artefacts sorted by path."""
    manifest = Manifest(
        schema=SCHEMA,
        fenolite=__version__,
        generated=timestamp.isoformat(),
        board=board,
        tool=ToolRef("kicad-cli", tool_version),
        artifacts=[entry(a) for a in sorted(artifacts, key=lambda a: a.path)],
    )
    return dataclasses.asdict(manifest)


def dumps(manifest: dict[str, Any]) -> str:
    """Canonical JSON: sorted keys, two-space indent, a final newline."""
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


__all__ = [
    "FILE_NAME",
    "SCHEMA",
    "ArtifactEntry",
    "BoardRef",
    "Manifest",
    "ToolRef",
    "build",
    "content_sha256",
    "dumps",
    "entry",
]
