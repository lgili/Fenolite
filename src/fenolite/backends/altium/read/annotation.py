# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The annotation file (``.Annotation``) read byte for byte (capability altium-project-reader, "Annotation
file read"; change c0083).

Board-level annotation stores its designators in a text file named after the project (S-0725). Its form is
stated by no public source (``docs/formats/altium/project.md``, "The annotation file": ``UNKNOWN``), so the
entry form below is this reader's assumption (``H-A-IMP-RPT-ANNOT``), settled by Part R, step R4: an entry
is a ``<key>=<value>`` line, in any section, whose key is a unique-id path (``\\<id>\\<id>…``, the form of a
board component's ``SOURCEUNIQUEID``) and whose value is the designator. Every other key line is kept and
reported with ``altium.text.unknown-key``. The bytes are kept: ``to_bytes()`` returns the input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fenolite.backends.altium.read.ini import IniDocument, parse_ini
from fenolite.backends.altium.read.textfile import text_issue
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-IMP-RPT-ANNOT",))
"""The annotation reader: ``INFERRED`` for what the file means, its entry form assumed (``UNKNOWN`` on the
facts page) until the author report."""

UNIQUE_ID_PATH = re.compile(r"(?:\\[A-Za-z0-9]+)+")
"""A unique-id path: one or more unique ids, each after a ``\\`` (``connectivity.md``, ``H-A-IMP-LINK``)."""


@dataclass(frozen=True, slots=True)
class AnnotationEntry:
    """One entry: the unique-id path of a component, the designator assigned to it, its section and its
    1-based line."""

    path: str
    designator: str
    section: str
    line: int


@dataclass(frozen=True, slots=True)
class AnnotationFile:
    """An annotation file: its INI view (``ini``, the bytes kept), its entries in file order and the issues
    of reading it."""

    ini: IniDocument
    entries: tuple[AnnotationEntry, ...]
    issues: tuple[Issue, ...]

    def to_bytes(self) -> bytes:
        return self.ini.to_bytes()

    def designators(self) -> dict[str, str]:
        """Unique-id path → designator; the first entry of a path wins."""
        found: dict[str, str] = {}
        for entry in self.entries:
            found.setdefault(entry.path, entry.designator)
        return found


def read_annotation(data: bytes, *, file: str = "") -> AnnotationFile:
    """Read the annotation file ``data``; ``to_bytes()`` of the result equals ``data``. ``FormatError`` for
    a compound file or a NUL byte (``textfile.split_text``). Info ``altium.text.unknown-key`` for each key
    line that names no unique-id path; the issues of ``parse_ini`` come first. An empty file has no
    entry."""
    ini = parse_ini(data, file=file)
    issues = list(ini.issues)
    entries: list[AnnotationEntry] = []
    for section in ini.sections:
        for entry in section.entries:
            if UNIQUE_ID_PATH.fullmatch(entry.key) and entry.value:
                entries.append(AnnotationEntry(entry.key, entry.value, section.name, entry.line))
                continue
            where = f"{file}:{entry.line}" if file else f"line {entry.line}"
            issues.append(
                text_issue(
                    "altium.text.unknown-key",
                    f"the key {entry.key!r} names no unique-id path with a designator; the line is kept and "
                    "gives no designator",
                    where,
                )
            )
    return AnnotationFile(ini, tuple(entries), tuple(issues))


__all__ = ["EVIDENCE", "UNIQUE_ID_PATH", "AnnotationEntry", "AnnotationFile", "read_annotation"]
