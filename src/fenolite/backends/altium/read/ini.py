# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A lossless INI layer for the project file and the output job (change c0042, Decision 3).

``parse_ini`` knows nothing of Altium. It keeps every line in the bytes of ``split_text`` and gives a
typed view of the sections in file order: repeated sections, repeated keys, empty lines, lines before
the first section and lines that are neither a section nor a key all stay, and ``to_bytes()`` returns
the input. Names are matched exactly as written (``docs/formats/altium/project.md``).
"""

# evidence: see read.project

from __future__ import annotations

import re
from dataclasses import dataclass

from fenolite.backends.altium.read.textfile import TextBytes, split_text, text_issue
from fenolite.core.errors import Issue

_SECTION = re.compile(r"^\[(.*)\]$", re.DOTALL)


@dataclass(frozen=True, slots=True)
class IniEntry:
    """One ``<key>=<value>`` line: the text before the first ``=`` and everything after it, spaces kept.
    ``line`` is the 1-based line number."""

    key: str
    value: str
    line: int


@dataclass(frozen=True, slots=True)
class IniSection:
    """One section and its entries in file order. Key lines before the first section form a section
    named ``""`` whose ``line`` is 0."""

    name: str
    entries: tuple[IniEntry, ...]
    line: int

    def get(self, key: str) -> str | None:
        """The first value of ``key``, or ``None``."""
        for entry in self.entries:
            if entry.key == key:
                return entry.value
        return None

    def keys(self) -> tuple[str, ...]:
        return tuple(entry.key for entry in self.entries)


@dataclass(frozen=True, slots=True)
class IniDocument:
    """The bytes of an INI file (``form``), its sections in file order and the issues of reading it."""

    form: TextBytes
    sections: tuple[IniSection, ...]
    issues: tuple[Issue, ...]

    def to_bytes(self) -> bytes:
        return self.form.to_bytes()

    def section(self, name: str) -> IniSection | None:
        """The first section named exactly ``name``, or ``None``."""
        for section in self.sections:
            if section.name == name:
                return section
        return None

    def numbered(self, stem: str) -> tuple[tuple[int, IniSection], ...]:
        """``(n, section)`` for every section named ``<stem><n>`` (``n`` a positive decimal number), in
        file order. The numbers need not be consecutive."""
        pattern = re.compile(re.escape(stem) + r"([1-9][0-9]*)")
        found: list[tuple[int, IniSection]] = []
        for section in self.sections:
            match = pattern.fullmatch(section.name)
            if match:
                found.append((int(match.group(1)), section))
        return tuple(found)


def parse_ini(data: bytes, *, file: str = "") -> IniDocument:
    """Read the INI bytes ``data``; ``to_bytes()`` of the result equals ``data``. ``FormatError`` (from
    ``split_text``) for a compound file or a NUL byte. Infos: ``altium.text.duplicate-key`` for each
    repeated key of a section, ``altium.text.stray-line`` for a line that is neither ``[<name>]``,
    ``<key>=<value>`` nor empty."""
    issues: list[Issue] = []
    form = split_text(data, file=file, issues=issues)
    sections: list[IniSection] = []
    name: str | None = None
    start = 0
    entries: list[IniEntry] = []

    def close() -> None:
        if name is not None:
            seen: set[str] = set()
            for entry in entries:
                if entry.key in seen:
                    issues.append(
                        text_issue(
                            "altium.text.duplicate-key",
                            f"the key {entry.key!r} is repeated in the section [{name}]; "
                            "the first value is used and every line is kept",
                            _where(file, entry.line),
                        )
                    )
                seen.add(entry.key)
            sections.append(IniSection(name, tuple(entries), start))

    for number, text in enumerate(form.texts(), start=1):
        match = _SECTION.match(text)
        if match:
            close()
            name, start, entries = match.group(1), number, []
            continue
        if not text:
            continue
        if "=" in text:
            if name is None:
                name, start, entries = "", 0, []
            key, value = text.split("=", 1)
            entries.append(IniEntry(key, value, number))
            continue
        issues.append(
            text_issue(
                "altium.text.stray-line",
                "a line that is neither a section, a key nor empty is kept",
                _where(file, number),
            )
        )
    close()
    return IniDocument(form, tuple(sections), tuple(issues))


def _where(file: str, line: int) -> str:
    return f"{file}:{line}" if file else f"line {line}"


__all__ = ["IniDocument", "IniEntry", "IniSection", "parse_ini"]
