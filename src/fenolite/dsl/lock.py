# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The design lock: automatic reference designators and the reviewed file that keeps them (change c0249;
``docs/dsl.md``, "Reference designators and the design lock").

A component's identity is its path. A part written without a ref gets one here, per reference prefix in
natural path order, with the lowest free number; the lock file ``<script stem>.lock`` records every ref so
that it never changes by itself. ``assign_refs`` is pure: it reads the design and a ``Lock`` and returns
the refs, the new lock, the changes and the issues. Reading and writing the file and refusing a change
under ``--frozen`` are steps of ``fenolite build``.

The lock has sections. Every step (read, carry by alias, release, compare, write) works on every section
through ``LockSection``; ``refs`` is the only section with content, and ``picks`` (c0254) and ``pins``
(c0257) are reserved: a lock that gives them content is refused until their change registers a resolver.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from fenolite.core.errors import FenoliteError, FormatError, Issue, Severity
from fenolite.dsl.part import NAME, Part

if TYPE_CHECKING:
    from fenolite.dsl.design import Design

SCHEMA = "fenolite.lock.v0"
"""The schema of the lock file this version reads and writes."""
SCHEMA_PATTERN = re.compile(r"fenolite\.lock\.v([0-9]+)")
SUFFIX = ".lock"
"""The lock of ``design.py`` is ``design.lock`` beside it."""
HEADER = "# Design lock written by fenolite build. Review changes in git; hand edits are honoured."
REASONS: tuple[str, ...] = (
    "assigned",
    "released",
    "moved",
    "explicit",
    "taken",
    "prefix-changed",
    "design-renamed",
)
"""The reasons of a change of the lock."""
LOCK_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "lock.ref-released": "warning",
        "lock.ref-taken": "warning",
        "lock.ref-moved": "info",
        "lock.ref-explicit": "info",
        "lock.ref-prefix-changed": "info",
        "lock.design-renamed": "info",
        "lock.changed": "error",
    }
)
"""The issue codes of the lock; they are also build issue codes (``lens.build.BUILD_ISSUE_CODES``)."""
FROZEN_HINT = "build without --frozen, review result.lock.changes, commit the lock, then build frozen"

LockValue = str | Mapping[str, object]
"""One entry of a section: a ref (``refs``), or a table of scalars (the reserved sections)."""


class LockVersionError(FormatError):
    """A lock of a newer schema, or a reserved section with content (``FEN-3002``)."""

    cli_code = "FEN-3002"


class LockFrozenError(FenoliteError):
    """``build --frozen`` and the lock would change (``FEN-7004``); ``issues`` holds one ``lock.changed``
    per change."""

    cli_code = "FEN-7004"

    def __init__(self, issues: Sequence[Issue]) -> None:
        self.issues = tuple(issues)
        self.hint = FROZEN_HINT
        count = len(self.issues)
        super().__init__(
            f"the design lock would change under --frozen; nothing was written ({count} "
            f"change{'' if count == 1 else 's'})"
        )


@dataclass(frozen=True)
class Lock:
    """The content of a lock: the design name and, per section name, its entries (key → value).

    ``sections`` holds every name of ``SECTIONS``, each a mapping in code-point order of keys. Two locks
    are equal when their content is, whatever the formatting of their files."""

    design: str
    sections: Mapping[str, Mapping[str, LockValue]]

    @property
    def refs(self) -> Mapping[str, str]:
        return cast(Mapping[str, str], self.sections["refs"])

    def entries(self) -> int:
        return sum(len(found) for found in self.sections.values())


def make_lock(design: str, sections: Mapping[str, Mapping[str, LockValue]] | None = None) -> Lock:
    """A ``Lock`` with every section, keys sorted by code point; sections left out are empty."""
    given = sections or {}
    return Lock(
        design,
        MappingProxyType(
            {
                section.name: MappingProxyType(dict(sorted(given.get(section.name, {}).items())))
                for section in SECTIONS
            }
        ),
    )


@dataclass(frozen=True, slots=True)
class LockChange:
    """One change of the lock: ``section``, ``key``, the value ``before`` and ``after`` (``None`` for none)
    and the ``reason`` (``REASONS``); ``origin`` is the old key of an entry carried by an alias."""

    section: str
    key: str
    before: str | None
    after: str | None
    reason: str
    origin: str | None = None

    def as_json(self) -> dict[str, object]:
        return {
            "section": self.section,
            "key": self.key,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
        }

    def sort_key(self) -> tuple[str, str, int]:
        return (self.section, self.key, REASONS.index(self.reason))


@dataclass(frozen=True, slots=True)
class SectionResult:
    """What a section's resolver gives: its new entries, its changes and its issues."""

    entries: Mapping[str, LockValue]
    changes: tuple[LockChange, ...] = ()
    issues: tuple[Issue, ...] = ()
    values: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    """What the design reads from the section (``refs``: path → ref)."""


Resolver = Callable[["Design", Mapping[str, LockValue]], SectionResult]


@dataclass(frozen=True, slots=True)
class LockSection:
    """A section of the lock: its ``name`` and the ``resolve`` step that turns the entries kept after the
    carry and release steps into the new entries. ``resolve`` is ``None`` for a reserved section, whose
    content is refused (``FEN-3002``) until the change that defines it registers a resolver. An entry is
    released when its key is no component path and, unless ``exact``, starts with none."""

    name: str
    resolve: Resolver | None
    exact: bool = False
    """Whether a key is exactly a component path (``refs``); otherwise it starts with one."""


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, LOCK_CODES[code], message, where=where, hint=hint)


# -- natural path order


def natural_key(path: str) -> tuple[tuple[int, int, int, str], ...]:
    """The sort key of ``path`` in natural path order: maximal runs of digits and non-digits, compared in
    turn; two digit runs by integer value and then by length, two non-digit runs by code point, a digit run
    before a non-digit run. ``ch2/R`` sorts before ``ch10/R``."""
    runs = re.findall(r"[0-9]+|[^0-9]+", path)
    return tuple((0, int(run), len(run), "") if run.isdigit() else (1, 0, 0, run) for run in runs)


# -- the refs section


def _resolve_refs(design: Design, entries: Mapping[str, LockValue]) -> SectionResult:
    """The refs of every part: explicit refs, then kept lock entries, then new refs per prefix in natural
    path order with the lowest free number. ``entries`` are the lock's refs after carry and release."""
    # a board-only part keeps its ref as written and no lock entry: KiCad does not annotate it (change c0277)
    parts: dict[str, Part] = {path: part for path, part in design.parts.items() if not part.board_only}
    explicit = {path: part.explicit_ref for path, part in parts.items() if part.explicit_ref is not None}
    owners = {ref: path for path, ref in explicit.items()}
    refs: dict[str, str] = dict(explicit)
    changes: list[LockChange] = []
    issues: list[Issue] = []
    replaced: dict[str, tuple[str, str]] = {}
    """Path → (locked ref, reason) of a part whose locked ref could not be kept."""
    for path in sorted(entries, key=natural_key):
        locked = cast(str, entries[path])
        part = parts.get(path)
        if part is None:
            continue
        if path in explicit:
            ref = explicit[path]
            if locked != ref:
                changes.append(LockChange("refs", path, locked, ref, "explicit"))
                issues.append(
                    issue(
                        "lock.ref-explicit",
                        f"the explicit ref {ref} of {path} replaces its locked ref {locked}",
                        path,
                    )
                )
            continue
        owner = owners.get(locked)
        if owner is not None:
            replaced[path] = (locked, "taken")
            issues.append(
                issue(
                    "lock.ref-taken",
                    f"the locked ref {locked} of {path} is now the explicit ref of {owner}; "
                    f"{path} is renumbered",
                    path,
                    f"give {path} another ref in the lock, or name it with its own explicit ref",
                )
            )
            continue
        prefix = part.prefix or ""
        if not locked.startswith(prefix):
            replaced[path] = (locked, "prefix-changed")
            issues.append(
                issue(
                    "lock.ref-prefix-changed",
                    f"the prefix of {path} is now {prefix}, so its locked ref {locked} is replaced",
                    path,
                )
            )
            continue
        refs[path] = locked
    for path, ref in sorted(explicit.items()):
        if path not in entries:
            changes.append(LockChange("refs", path, None, ref, "assigned"))
    used = set(refs.values())
    waiting = sorted((path for path in parts if path not in refs), key=natural_key)
    for path in waiting:
        prefix = cast(str, parts[path].prefix)
        number = 1
        while f"{prefix}{number}" in used:
            number += 1
        ref = f"{prefix}{number}"
        used.add(ref)
        refs[path] = ref
        before, reason = replaced.get(path, (None, "assigned"))
        changes.append(LockChange("refs", path, before, ref, reason))
    ordered = dict(sorted(refs.items()))
    return SectionResult(
        entries=MappingProxyType(dict(ordered)),
        changes=tuple(changes),
        issues=tuple(issues),
        values=MappingProxyType(ordered),
    )


SECTIONS: tuple[LockSection, ...] = (
    LockSection("refs", _resolve_refs, exact=True),
    LockSection("picks", None),  # c0254 registers its resolver
    LockSection("pins", None),  # c0257 registers its resolver
)
"""The sections of the lock, in the order the file writes them."""


# -- assignment


@dataclass(frozen=True, slots=True)
class RefAssignment:
    """``refs`` (path → ref of every part), the new ``lock``, its ``changes`` sorted by section and key,
    and the ``issues``."""

    refs: Mapping[str, str]
    lock: Lock
    changes: tuple[LockChange, ...]
    issues: tuple[Issue, ...]


def _owner(key: str, roots: Sequence[str]) -> str | None:
    """The longest of ``roots`` that is ``key`` or a path prefix of it."""
    found = [root for root in roots if key == root or key.startswith(f"{root}/")]
    return max(found, key=len) if found else None


def assign_refs(design: Design, lock: Lock, *, moves: Mapping[str, str]) -> RefAssignment:
    """The refs of ``design`` against ``lock``, and the new lock (pure; ``docs/dsl.md``, "Reference
    designators and the design lock").

    1. Each alias new → old of ``moves`` (``dsl.moves``) carries the entries of every section whose key is
       ``old`` or starts with ``old/`` to ``new`` (``lock.ref-moved``).
    2. An entry whose key is no part path, and does not start with one, is released
       (``lock.ref-released``).
    3. Each section's ``resolve`` gives its new entries: for ``refs``, explicit refs first, then kept
       entries, then new refs per prefix in natural path order with the lowest free number.
    """
    changes: list[LockChange] = []
    issues: list[Issue] = []
    if lock.design != design.name:
        changes.append(LockChange("design", "design", lock.design, design.name, "design-renamed"))
        issues.append(
            issue(
                "lock.design-renamed",
                f"the lock names the design {lock.design}; it is rewritten for {design.name}",
                "design",
            )
        )
    by_old = {old: new for new, old in moves.items()}
    roots = sorted(by_old)
    parts = sorted(design.parts)
    new_sections: dict[str, Mapping[str, LockValue]] = {}
    refs: Mapping[str, str] = MappingProxyType({})
    for section in SECTIONS:
        entries = lock.sections.get(section.name, {})
        carried: dict[str, LockValue] = {}
        moved: dict[str, tuple[str, LockValue]] = {}
        for key, value in entries.items():
            root = _owner(key, roots)
            if root is None:
                carried.setdefault(key, value)
                continue
            target = by_old[root] + key[len(root) :]
            moved[target] = (key, value)
        for target, (key, value) in sorted(moved.items()):
            carried[target] = value  # a carried entry wins over a stale entry of its new path
            shown = value if isinstance(value, str) else None
            changes.append(LockChange(section.name, target, shown, shown, "moved", origin=key))
            issues.append(
                issue(
                    "lock.ref-moved",
                    f"moved() carries the {section.name} entry of {key} to {target}",
                    target,
                )
            )
        kept: dict[str, LockValue] = {}
        for key, value in sorted(carried.items()):
            owner = _owner(key, parts)
            if owner is not None and (owner == key or not section.exact):
                kept[key] = value
                continue
            shown = value if isinstance(value, str) else None
            changes.append(LockChange(section.name, key, shown, None, "released"))
            what = f"ref {shown}" if shown is not None else f"{section.name} entry"
            issues.append(
                issue(
                    "lock.ref-released",
                    f"{key} is no part of the design, so its {what} is released and may be given to "
                    "another part",
                    key,
                    f"if the part was renamed, record it with design.moved({key!r}, <new path>)",
                )
            )
        if section.resolve is None:
            new_sections[section.name] = MappingProxyType(dict(sorted(kept.items())))
            continue
        result = section.resolve(design, kept)
        new_sections[section.name] = result.entries
        changes.extend(result.changes)
        issues.extend(result.issues)
        if section.name == "refs":
            refs = result.values
    return RefAssignment(
        refs=refs,
        lock=make_lock(design.name, new_sections),
        changes=tuple(sorted(changes, key=LockChange.sort_key)),
        issues=tuple(issues),
    )


def frozen_issues(changes: Sequence[LockChange]) -> list[Issue]:
    """One ``lock.changed`` error per change, naming its section, key, values and reason."""
    found: list[Issue] = []
    for change in changes:
        carried = "" if change.origin is None else f", carried from {change.origin}"
        found.append(
            issue(
                "lock.changed",
                f"under --frozen the lock would change: {change.section} {change.key}: "
                f"{change.before} -> {change.after} ({change.reason}{carried})",
                f"{change.section}:{change.key}",
                FROZEN_HINT,
            )
        )
    return found


# -- reading


def _refuse(message: str, file: str, key: str) -> FormatError:
    return FormatError(message, file=file, locator=key)


def read_lock(text: str, *, file: str) -> Lock:
    """The lock in ``text`` (the content of ``file``), checked.

    An unknown top-level key, a value of the wrong type, a ref that is not a valid name or two paths with
    one ref raise ``FormatError`` (``FEN-3004``); a newer schema, or a reserved section with content,
    raises ``LockVersionError`` (``FEN-3002``)."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise FormatError(f"the lock is not valid TOML: {error}", file=file) from None
    allowed = ("schema", "design", *(section.name for section in SECTIONS))
    for key in data:
        if key not in allowed:
            raise _refuse(f"unknown key {key!r} in the lock; the keys are {', '.join(allowed)}", file, key)
    schema = data.get("schema")
    if not isinstance(schema, str):
        raise _refuse(f"schema must be the string {SCHEMA!r}", file, "schema")
    version = SCHEMA_PATTERN.fullmatch(schema)
    if version is None:
        raise _refuse(
            f"schema {schema!r} is not a lock schema; this version reads {SCHEMA!r}", file, "schema"
        )
    if int(version.group(1)) > 0:
        raise LockVersionError(
            f"the lock has the newer schema {schema!r}; this version reads {SCHEMA!r}",
            file=file,
            locator="schema",
        )
    design = data.get("design")
    if not isinstance(design, str) or not design:
        raise _refuse("design must be the design name, a non-empty string", file, "design")
    sections: dict[str, dict[str, LockValue]] = {}
    for section in SECTIONS:
        raw = data.get(section.name, {})
        if not isinstance(raw, dict):
            raise _refuse(f"{section.name} must be a table", file, section.name)
        table = cast(dict[str, object], raw)
        if section.resolve is None:
            if table:
                raise LockVersionError(
                    f"the section {section.name} has content, which this version does not define yet",
                    file=file,
                    locator=section.name,
                )
            sections[section.name] = {}
            continue
        sections[section.name] = _read_refs(table, file) if section.name == "refs" else {}
    return make_lock(design, sections)


def _read_refs(table: Mapping[str, object], file: str) -> dict[str, LockValue]:
    out: dict[str, LockValue] = {}
    owners: dict[str, str] = {}
    for path, ref in table.items():
        where = f"refs.{path}"
        if not all(NAME.fullmatch(segment) for segment in path.split("/")):
            raise _refuse(f"{path!r} is not a component path", file, where)
        if not isinstance(ref, str) or not NAME.fullmatch(ref):
            raise _refuse(
                f"the ref of {path} must be a name matching {NAME.pattern}, not {ref!r}", file, where
            )
        if ref in owners:
            raise _refuse(f"two paths have the ref {ref}: {owners[ref]} and {path}", file, where)
        owners[ref] = path
        out[path] = ref
    return out


# -- writing


def _string(text: str) -> str:
    """``text`` as a TOML basic string."""
    out = ['"']
    for char in text:
        if char in ('"', "\\"):
            out.append("\\" + char)
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04X}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return _string(str(value))


def lock_text(lock: Lock) -> str:
    """The canonical text of ``lock``: the header comment, ``schema`` and ``design``, then the non-empty
    sections in the order of ``SECTIONS`` with keys in code-point order; LF line ends, one final newline,
    no date and no absolute path."""
    lines = [HEADER, f"schema = {_string(SCHEMA)}", f"design = {_string(lock.design)}"]
    for section in SECTIONS:
        entries = lock.sections.get(section.name, {})
        if not entries:
            continue
        flat = {key: value for key, value in entries.items() if isinstance(value, str)}
        if flat:
            lines += ["", f"[{section.name}]"]
            lines += [f"{_string(key)} = {_string(value)}" for key, value in sorted(flat.items())]
        for key, value in sorted(entries.items()):
            if isinstance(value, str):
                continue
            lines += ["", f"[{section.name}.{_string(key)}]"]
            lines += [f"{_string(name)} = {_scalar(item)}" for name, item in sorted(value.items())]
    return "\n".join(lines) + "\n"


def needs_lock(design: Design) -> bool:
    """Whether ``design`` has a part without an explicit ref (a design with a lock file needs it too)."""
    return any(part.explicit_ref is None for part in design.parts.values())


__all__ = [
    "HEADER",
    "LOCK_CODES",
    "REASONS",
    "SCHEMA",
    "SECTIONS",
    "SUFFIX",
    "Lock",
    "LockChange",
    "LockFrozenError",
    "LockSection",
    "LockVersionError",
    "RefAssignment",
    "SectionResult",
    "assign_refs",
    "frozen_issues",
    "lock_text",
    "make_lock",
    "natural_key",
    "needs_lock",
    "read_lock",
]
