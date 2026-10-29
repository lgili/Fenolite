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

from fenolite.importer.source import InputFile, Upgrade

SCHEMA = "fenolite.import-provenance.v0"
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
    }
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


__all__ = ["NOASSERTION", "SCHEMA", "Provenance", "record"]
