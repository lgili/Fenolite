# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The provenance of an import (change c0275, design decision 9): the four header lines of every emitted
``.py`` file and ``PROVENANCE.json`` (schema ``fenolite.import-provenance.v0``) in canonical JSON: sorted
keys, two-space indentation, LF line ends and a final newline. No absolute path is written: inputs are
named by base name and SHA-256.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from fenolite.importer.source import InputFile, Upgrade

SCHEMA = "fenolite.import-provenance.v0"
LIBRARY_SCHEMA = "fenolite.provenance.v0"
"""The record of an item of the board library (c0279), which holds the import record as its ``import``."""
NOASSERTION = "NOASSERTION"
"""The SPDX expression of a licence nobody stated."""
UNKNOWN_SOURCE = "an unstated source"


@dataclass(frozen=True, slots=True)
class Provenance:
    """What the user states about the upstream (``--licence``, ``--copyright``, ``--source``,
    ``--revision``), the Fenolite version and the date of the conversion."""

    licence: str | None = None
    copyright: tuple[str, ...] = ()
    source: str | None = None
    revision: str | None = None
    fenolite: str = ""
    date: str = ""
    notices: tuple[str, ...] = field(default=())

    @property
    def spdx(self) -> str:
        return self.licence or NOASSERTION

    def header(self) -> list[str]:
        """The comment lines every emitted ``.py`` file starts with."""
        where = self.source or UNKNOWN_SOURCE
        at = f"{where}@{self.revision}" if self.revision else where
        notice = " Original notices in NOTICE." if "NOTICE" in self.notices else ""
        lines = [f"# SPDX-License-Identifier: {self.spdx}"]
        lines += [f"# SPDX-FileCopyrightText: {holder}" for holder in self.copyright or (NOASSERTION,)]
        lines += [
            f"# Converted from {at} by Fenolite {self.fenolite} on {self.date};",
            f"# modified: format conversion to the Fenolite DSL.{notice}",
        ]
        return lines


def record(
    provenance: Provenance,
    *,
    design: str,
    inputs: Sequence[InputFile],
    upgrades: Sequence[Upgrade],
    findings: Mapping[str, int],
    equivalence: Mapping[str, object] | None,
    tools: Mapping[str, str],
) -> str:
    """The canonical text of ``PROVENANCE.json``."""
    data: dict[str, object] = {
        "schema": SCHEMA,
        "design": design,
        "licence": provenance.spdx,
        "copyright": list(provenance.copyright),
        "source": {"url": provenance.source, "revision": provenance.revision},
        "inputs": [row.as_json() for row in sorted(inputs, key=lambda row: row.file)],
        "upgrade": [row.as_json() for row in upgrades],
        "fenolite": provenance.fenolite,
        "tools": dict(sorted(tools.items())),
        "date": provenance.date,
        "notices": list(provenance.notices),
        "findings": dict(sorted(findings.items())),
        "equivalence": dict(equivalence) if equivalence is not None else None,
        "copy": True,
    }
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def import_record(data: object) -> Mapping[str, Any] | None:
    """The import record a provenance value holds: the value itself when its ``schema`` is ``SCHEMA``, its
    member ``import`` when that member is one (a library record, c0279), else ``None``."""
    if not isinstance(data, dict):
        return None
    root = cast(dict[str, Any], data)
    if root.get("schema") == SCHEMA:
        return root
    member = root.get("import")
    if isinstance(member, dict) and cast(dict[str, Any], member).get("schema") == SCHEMA:
        return cast(dict[str, Any], member)
    return None


def copy_mode(data: object) -> bool:
    """Whether a provenance value marks its design as a copy of someone else's board (change c0281): it
    holds an import record whose ``copy`` is not ``false``. A record written before c0281 has no ``copy``
    and counts as a copy, since every import is one; ``"copy": false`` says the design is now its owner's."""
    found = import_record(data)
    return found is not None and found.get("copy", True) is not False


def copy_file(path: Path) -> bool:
    """``copy_mode`` of the provenance file at ``path``; a missing or unreadable file marks no copy (the
    commands that read the file for more than the mode report what is wrong with it)."""
    try:
        return copy_mode(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False


__all__ = [
    "LIBRARY_SCHEMA",
    "NOASSERTION",
    "SCHEMA",
    "Provenance",
    "copy_file",
    "copy_mode",
    "import_record",
    "record",
]
