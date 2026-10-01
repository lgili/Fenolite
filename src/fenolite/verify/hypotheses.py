# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The hypothesis register (``docs/hypotheses.md``): evidence labels, rows, reserved families, and the
hypothesis ids cited in the repository's text.

Rules: ``openspec/specs/verification-evidence``. Reading is strict: a malformed row raises
``ValueError`` with ``<path>:<line>`` instead of dropping out of the checks.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from fenolite.core.evidence import Level

ID_PATTERN = re.compile(r"\bH-[AGK]-[A-Z0-9]+(?:-[A-Z0-9]+)*")
REGISTER_HEADER: tuple[str, ...] = (
    "id",
    "backend",
    "statement",
    "level",
    "test or kit request",
    "criterion",
    "result",
    "date",
)
FAMILIES_HEADER: tuple[str, ...] = ("family", "backend", "rows for", "owner")
PROPOSED_HEADING = "## Hypotheses registered by this change"

_PLAIN = frozenset(
    {
        Level.KICAD_VERIFIED,
        Level.ORACLE_VERIFIED,
        Level.CORPUS_VERIFIED,
        Level.INFERRED,
        Level.UNKNOWN,
        Level.UNVERIFIED,
    }
)
_SCOPE = re.compile(r"(?P<body>.+?) \((?P<scope>[^()]+)\)")
_QUALIFIED = re.compile(r"(?P<name>ORACLE-VERIFIED|ALTIUM-VERIFIED)\((?P<qualifier>[^()]+)\)")
_FAMILY = re.compile(ID_PATTERN.pattern.removeprefix(r"\b") + r"-\*")
_SUCCESSOR = re.compile(r"superseded by\s+(" + ID_PATTERN.pattern.removeprefix(r"\b") + ")")
_FAMILY_FOLLOWERS = ("-", "*", "…")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")


def parse_level(text: str) -> Level:
    """The ``Level`` a label denotes: an exact value, or a qualified form such as
    ``KICAD-VERIFIED (9.0.x, 10.0.x)`` or ``ALTIUM-VERIFIED(author-report; AD 24.x; 2026-09; …)``."""
    body = text
    scoped = _SCOPE.fullmatch(text)
    if scoped is not None and scoped.group("scope").strip():
        body = scoped.group("body")
    for level in _PLAIN:
        if body == level.value:
            return level
    qualified = _QUALIFIED.fullmatch(body)
    if qualified is not None and qualified.group("qualifier").strip():
        if qualified.group("name") == "ORACLE-VERIFIED":
            return Level.ORACLE_VERIFIED
        kind = qualified.group("qualifier").split(";")[0].strip()
        if kind == "kit":
            return Level.ALTIUM_VERIFIED_KIT
        if kind == "author-report":
            return Level.ALTIUM_VERIFIED_AUTHOR_REPORT
    raise ValueError(f"not an evidence label: {text!r}")


@dataclass(frozen=True, slots=True)
class HypothesisRow:
    """One row of the register; ``level_text`` is the level cell as written."""

    id: str
    backend: str
    statement: str
    level: Level
    level_text: str
    test: str
    criterion: str
    result: str
    date: str

    @property
    def refuted(self) -> bool:
        """True when the result starts with ``refuted`` (``partly refuted`` is not a refutation)."""
        return self.result.startswith("refuted")

    @property
    def successor(self) -> str | None:
        """The first id after ``superseded by`` in the result, or ``None``."""
        found = _SUCCESSOR.search(self.result)
        return found.group(1) if found else None


def _cells(line: str) -> list[str]:
    inner = line.strip()
    inner = inner[1:] if inner.startswith("|") else inner
    inner = inner[:-1] if inner.endswith("|") and not inner.endswith("\\|") else inner
    return [cell.strip().replace("\\|", "|") for cell in _CELL_SPLIT.split(inner)]


def _tables(lines: list[str], header: tuple[str, ...]) -> list[list[tuple[int, list[str]]]]:
    """The tables whose header row is exactly ``header``: their rows as ``(line number, cells)``."""
    tables: list[list[tuple[int, list[str]]]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("|") and tuple(_cells(line)) == header:
            rows: list[tuple[int, list[str]]] = []
            index += 1
            while index < len(lines) and lines[index].startswith("|"):
                cells = _cells(lines[index])
                if not all(set(c) <= {"-", ":", " "} for c in cells):
                    rows.append((index + 1, cells))
                index += 1
            tables.append(rows)
            continue
        index += 1
    return tables


def _lines(path: str | os.PathLike[str]) -> list[str]:
    return Path(path).read_text(encoding="utf-8").splitlines()


def load_register(path: str | os.PathLike[str]) -> tuple[HypothesisRow, ...]:
    """The rows of the one register table of ``path``, in file order."""
    shown = os.fspath(path)
    tables = _tables(_lines(path), REGISTER_HEADER)
    if len(tables) != 1:
        raise ValueError(f"{shown}: expected one register table, found {len(tables)}")
    rows: list[HypothesisRow] = []
    for number, cells in tables[0]:
        where = f"{shown}:{number}"
        if len(cells) != len(REGISTER_HEADER):
            raise ValueError(
                f"{where}: a register row needs {len(REGISTER_HEADER)} cells, found {len(cells)}"
            )
        ident, backend, statement, level_text, test, criterion, result, date = cells
        if not ID_PATTERN.fullmatch(ident):
            raise ValueError(f"{where}: {ident!r} is not a hypothesis id")
        try:
            level = parse_level(level_text)
        except ValueError as error:
            raise ValueError(f"{where}: {error}") from None
        rows.append(
            HypothesisRow(ident, backend, statement, level, level_text, test, criterion, result, date)
        )
    return tuple(rows)


def load_families(path: str | os.PathLike[str]) -> tuple[str, ...]:
    """The reserved families of ``path`` as written (``H-K-KRT-*``); ``()`` without such a table."""
    shown = os.fspath(path)
    tables = _tables(_lines(path), FAMILIES_HEADER)
    if not tables:
        return ()
    if len(tables) > 1:
        raise ValueError(f"{shown}: expected at most one reserved-families table, found {len(tables)}")
    families: list[str] = []
    for number, cells in tables[0]:
        cell = cells[0]
        if len(cell) >= 2 and cell.startswith("`") and cell.endswith("`"):
            cell = cell[1:-1]
        if not _FAMILY.fullmatch(cell):
            raise ValueError(f"{shown}:{number}: {cells[0]!r} is not a family such as `H-K-KRT-*`")
        families.append(cell)
    return tuple(families)


def _files(root: Path, excluded: list[Path]) -> Iterator[Path]:
    if any(root == e or e in root.parents for e in excluded):
        return
    if root.is_file():
        yield root
        return
    for current, folders, files in os.walk(root):
        here = Path(current)
        folders[:] = sorted(
            f
            for f in folders
            if not f.startswith(".") and f != "__pycache__" and not any(here / f == e for e in excluded)
        )
        for name in sorted(files):
            path = here / name
            if not name.startswith(".") and path not in excluded:
                yield path


def cited_ids(
    roots: Iterable[str | os.PathLike[str]],
    *,
    base: str | os.PathLike[str],
    exclude: Iterable[str | os.PathLike[str]] = (),
) -> dict[str, tuple[str, ...]]:
    """Every hypothesis id or family (``<stem>-*``) cited under ``roots``, with the sorted POSIX paths,
    relative to ``base``, of the files that cite it. Dot files and folders, ``__pycache__``, the
    ``exclude`` paths and files that are not UTF-8 are skipped."""
    base_path = Path(base)
    excluded = [p if p.is_absolute() else base_path / p for p in map(Path, exclude)]
    found: dict[str, set[str]] = {}
    for root in roots:
        root_path = Path(root)
        root_path = root_path if root_path.is_absolute() else base_path / root_path
        for path in _files(root_path, excluded):
            try:
                text = path.read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = path.relative_to(base_path).as_posix()
            for match in ID_PATTERN.finditer(text):
                follower = text[match.end() : match.end() + 1]
                key = match.group() + "-*" if follower in _FAMILY_FOLLOWERS else match.group()
                found.setdefault(key, set()).add(rel)
    return {key: tuple(sorted(paths)) for key, paths in sorted(found.items())}


def proposed_ids(changes_dir: str | os.PathLike[str]) -> frozenset[str]:
    """The ids that active changes declare in the tables of their design's section
    "Hypotheses registered by this change" (``archive/`` excluded)."""
    folder = Path(changes_dir)
    ids: set[str] = set()
    if not folder.is_dir():
        return frozenset()
    for change in sorted(p for p in folder.iterdir() if p.is_dir() and p.name != "archive"):
        design = change / "design.md"
        if not design.is_file():
            continue
        inside = False
        for line in _lines(design):
            if line.startswith("## "):
                inside = line.strip() == PROPOSED_HEADING
                continue
            if not inside or not line.startswith("|"):
                continue
            cell = _cells(line)[0]
            if len(cell) >= 2 and cell.startswith("`") and cell.endswith("`"):
                cell = cell[1:-1]
            match = ID_PATTERN.match(cell)
            if match is not None:
                ids.add(match.group())
    return frozenset(ids)


__all__ = [
    "FAMILIES_HEADER",
    "ID_PATTERN",
    "PROPOSED_HEADING",
    "REGISTER_HEADER",
    "HypothesisRow",
    "cited_ids",
    "load_families",
    "load_register",
    "parse_level",
    "proposed_ids",
]
