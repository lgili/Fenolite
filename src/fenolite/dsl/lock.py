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
through ``LockSection``. ``refs`` holds the refs; ``picks`` (c0254: one table per query part, filled by
the build's pick resolver, installed with ``picks_resolver``) and ``pins`` (change c0257: the pin choices of
the takes, kept here as read and replaced by the pin solve of ``fenolite build``, ``fenolite.lens.pins``)
and ``blocks`` (change c0268: ``<id>@<version>`` of every instance of a block with a record, so that a
new block version is never taken silently) have content.
``library`` (change c0279) holds the pins of the items that ``fenolite get`` vendored; a build
reads it and never changes it.
"""

from __future__ import annotations

import contextlib
import re
import tomllib
from collections.abc import Callable, Generator, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from fenolite.core.errors import FenoliteError, FormatError, Issue, Severity
from fenolite.core.partquery import LOCK_KEYS, LOCK_REQUIRED
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
    "picked",
    "query-changed",
    "row-changed",
    "updated",
    "solved",
    "stale",
    "dropped",
    "block-locked",
    "block-replaced",
    "block-released",
)
"""The reasons of a change of the lock (``picked`` to ``updated``: changes of ``picks``, change c0254;
``solved``, ``stale`` and ``dropped``: changes of ``pins``, change c0257; ``block-locked`` to
``block-released``: changes of ``blocks``, change c0268)."""
LOCK_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "lock.ref-released": "warning",
        "lock.ref-taken": "warning",
        "lock.ref-moved": "info",
        "lock.ref-explicit": "info",
        "lock.ref-prefix-changed": "info",
        "lock.design-renamed": "info",
        "lock.changed": "error",
        # the [blocks] section (change c0268)
        "lock.block-version": "error",
        "lock.block-replaced": "info",
        "lock.block-released": "info",
        "block.deprecated": "warning",
    }
)
"""The issue codes of the lock; they are also build issue codes (``lens.build.BUILD_ISSUE_CODES``).
``block.deprecated`` is reported by the resolver of ``blocks``, which sees every recorded instance."""
FROZEN_HINT = "build without --frozen, review result.lock.changes, commit the lock, then build frozen"

LockValue = str | Mapping[str, object]
"""One entry of a section: a ref (``refs``), or a table (``pins``: scalars and the ``pins`` table)."""
BLOCK_PIN = re.compile(r"[A-Za-z0-9_.+-]+:[A-Za-z0-9_.+-]+@(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
"""A ``[blocks]`` entry: ``<id>@<version>`` (change c0268)."""
PIN_FIELDS: tuple[str, ...] = ("kind", "option", "alternative", "pins", "choice")
"""The keys of a ``[pins."<key>"]`` entry, in the order the file writes them; ``choice`` is human text,
ignored when read and written again from the others."""
TAKE_KEY = re.compile(r"[A-Za-z0-9_.+-]+(#[0-9]+)?")
"""The last segment of a ``[pins]`` key: a take name, or ``<kind>#<n>``."""


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
    releases: bool = True
    """Whether the common release step drops an entry whose key is no part path; ``blocks`` (change c0268)
    keys instance paths and releases its own entries."""

    paths: bool = True
    """Whether the keys name component paths. A section of other keys (``library``: ``<kind>/<id>``, change
    c0279) is neither carried by an alias nor released: the build keeps it as it was read."""


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

_HAND: ContextVar[Mapping[str, tuple[str, str | None]]] = ContextVar(
    "fenolite_hand_refs", default=MappingProxyType({})
)


@contextlib.contextmanager
def hand_refs(edits: Mapping[str, tuple[str, str | None]]) -> Generator[None]:
    """Count the ``reference`` edits of ``edits.toml`` (path → (ref, the ref it was recorded over)) as
    explicit refs while the block runs (change c0250, "Reference edits"): ``fenolite build`` installs them,
    so the lock records a part re-annotated in KiCad."""
    token = _HAND.set(MappingProxyType(dict(edits)))
    try:
        yield
    finally:
        _HAND.reset(token)


def _resolve_refs(design: Design, entries: Mapping[str, LockValue]) -> SectionResult:
    """The refs of every part: explicit refs, then kept lock entries, then new refs per prefix in natural
    path order with the lowest free number. ``entries`` are the lock's refs after carry and release.

    A reference edit (``hand_refs``) is an explicit ref when it was recorded over the part's explicit or
    locked ref, or the part has neither; an edit made over another ref is stale and left to the build's
    merge, which reports it."""
    parts: dict[str, Part] = dict(design.parts)
    explicit = {path: part.explicit_ref for path, part in parts.items() if part.explicit_ref is not None}
    for path, (ref, over) in sorted(_HAND.get().items()):
        if path not in parts:
            continue
        code = explicit.get(path, cast("str | None", entries.get(path)))
        if code is None or over is None or over == code or ref == code:
            explicit[path] = ref
    owners = {ref: path for path, ref in explicit.items()}
    refs: dict[str, str] = dict(explicit)
    changes: list[LockChange] = []
    issues: list[Issue] = []
    replaced: dict[str, tuple[str, str]] = {}
    """Path → (locked ref, reason) of a part whose locked ref could not be kept."""
    for path in sorted(entries, key=natural_key):
        locked = cast(str, entries[path])
        part = parts[path]
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


# -- the picks section (change c0254)

_PICKS: ContextVar[Resolver | None] = ContextVar("fenolite_picks_resolver", default=None)


@contextlib.contextmanager
def picks_resolver(resolve: Resolver) -> Generator[None]:
    """Resolve the ``picks`` section with ``resolve`` while the block runs (``fenolite build`` and
    ``fenolite pick`` install the resolver of ``fenolite.pick``, which needs the catalog in hand)."""
    token = _PICKS.set(resolve)
    try:
        yield
    finally:
        _PICKS.reset(token)


def _resolve_picks(design: Design, entries: Mapping[str, LockValue]) -> SectionResult:
    """The installed pick resolver's result; without one, the kept entries as they are."""
    resolve = _PICKS.get()
    if resolve is None:
        return SectionResult(entries=MappingProxyType(dict(sorted(entries.items()))))
    return resolve(design, entries)


def _keep(design: Design, entries: Mapping[str, LockValue]) -> SectionResult:
    """The ``pins`` entries kept after carry and release, unchanged: ``fenolite build`` replaces them with
    the pin solve (change c0257)."""
    del design
    return SectionResult(entries=MappingProxyType(dict(sorted(entries.items()))))


# -- the blocks section (change c0268)


def block_issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, LOCK_CODES[code], message, where=where, hint=hint)


def _resolve_blocks(design: Design, entries: Mapping[str, LockValue]) -> SectionResult:
    """``<id>@<version>`` of every instance of a block with a record, keyed by its path, against the
    entries kept after the carry step: a first pin is planned, another version of a locked id is refused
    (``lock.block-version``, the entry kept), another id replaces the entry, and an entry whose path is
    no recorded instance is released. ``block.deprecated`` is reported once per id."""
    from fenolite.dsl.block import blocks

    used: dict[str, tuple[str, str]] = {}
    deprecated: dict[str, str] = {}
    for found in blocks(design):
        header = found.definition.header
        if header is None:
            continue
        used[found.path] = (header.id, header.pin)
        if header.deprecated is not None:
            gone = header.deprecated
            deprecated[header.id] = f"{gone.by} (since {gone.since}: {gone.reason})"
    out: dict[str, LockValue] = {}
    changes: list[LockChange] = []
    issues: list[Issue] = []
    for path, value in sorted(entries.items()):
        locked = cast(str, value)
        if path not in used:
            changes.append(LockChange("blocks", path, locked, None, "block-released"))
            issues.append(
                block_issue(
                    "lock.block-released",
                    f"{path} is no instance of a block with a record any more, so its entry {locked} is "
                    "released",
                    path,
                )
            )
            continue
        block_id, pin = used[path]
        if locked == pin:
            out[path] = locked
            continue
        locked_id, _, locked_version = locked.rpartition("@")
        if locked_id == block_id:
            out[path] = locked  # never taken silently: the build stops for a review
            issues.append(
                block_issue(
                    "lock.block-version",
                    f"{path} is locked to {block_id} {locked_version}, and the script uses version "
                    f"{pin.rpartition('@')[2]}; nothing is written",
                    path,
                    f"review `fenolite blocks show {block_id}`, then change the entry of {path} in the "
                    "design lock",
                )
            )
            continue
        out[path] = pin
        changes.append(LockChange("blocks", path, locked, pin, "block-replaced"))
        issues.append(
            block_issue(
                "lock.block-replaced",
                f"{path} now uses {pin} in place of {locked}; the entry is replaced",
                path,
            )
        )
    for path, (_, pin) in sorted(used.items()):
        if path not in entries:
            out[path] = pin
            changes.append(LockChange("blocks", path, None, pin, "block-locked"))
    for block_id, by in sorted(deprecated.items()):
        issues.append(
            block_issue(
                "block.deprecated",
                f"the block {block_id} is deprecated; use {by}",
                block_id,
                f"replace the uses of {block_id} with {by.split(' ', 1)[0]}",
            )
        )
    return SectionResult(
        entries=MappingProxyType(dict(sorted(out.items()))), changes=tuple(changes), issues=tuple(issues)
    )


SECTIONS: tuple[LockSection, ...] = (
    LockSection("refs", _resolve_refs, exact=True),
    LockSection("picks", _resolve_picks, exact=True),  # c0254
    LockSection("pins", _keep),  # c0257: replaced by the pin solve of fenolite build
    LockSection("blocks", _resolve_blocks, releases=False),  # c0268
    LockSection("library", _keep, paths=False),  # c0279: only fenolite get changes it
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
       ``old`` or starts with ``old/`` to ``new`` (``lock.ref-moved``); the ``blocks`` section, keyed by
       instance paths, also follows the module aliases (``dsl.module_moves``).
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
    from fenolite.dsl.convert import module_moves

    by_part = {old: new for new, old in moves.items()}
    by_module = {**by_part, **{old: new for new, old in module_moves(design).items()}}
    parts = sorted(design.parts)
    new_sections: dict[str, Mapping[str, LockValue]] = {}
    refs: Mapping[str, str] = MappingProxyType({})
    for section in SECTIONS:
        # a section keyed by instance paths (blocks, change c0268) follows the module aliases too
        by_old = by_part if section.releases else by_module
        roots = sorted(by_old)
        entries = lock.sections.get(section.name, {})
        if not section.paths:
            new_sections[section.name] = MappingProxyType(dict(sorted(entries.items())))
            continue
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
            if not section.releases:
                kept[key] = value
                continue
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
        if section.name == "refs":
            sections[section.name] = _read_refs(table, file)
        elif section.name == "blocks":
            sections[section.name] = _read_blocks(table, file)
        elif section.name == "picks":
            sections[section.name] = _read_picks(table, file)
        elif section.name == "library":
            sections[section.name] = _read_library(table, file)
        else:
            sections[section.name] = _read_pins(table, file)
    return make_lock(design, sections)


def _read_pins(table: Mapping[str, object], file: str) -> dict[str, LockValue]:
    """The ``[pins]`` entries (change c0257): ``kind``, ``option``, ``alternative`` (an index), ``pins``
    (role → pin) and the ignored ``choice`` text."""
    out: dict[str, LockValue] = {}
    for key, raw in table.items():
        where = f"pins.{key}"
        path, _, last = key.rpartition("/")
        if not path or not all(NAME.fullmatch(s) for s in path.split("/")) or not TAKE_KEY.fullmatch(last):
            raise _refuse(f"{key!r} is not a take key <part path>/<take>", file, where)
        if not isinstance(raw, dict):
            raise _refuse(f"the pins entry {key} must be a table", file, where)
        entry = cast(dict[str, object], raw)
        unknown = sorted(set(entry) - set(PIN_FIELDS))
        if unknown:
            raise _refuse(f"unknown key {unknown[0]!r} in the pins entry {key}", file, where)
        for name in ("kind", "option"):
            if not isinstance(entry.get(name), str) or not entry[name]:
                raise _refuse(f"the pins entry {key} needs {name}, a non-empty string", file, where)
        alternative = entry.get("alternative")
        if isinstance(alternative, bool) or not isinstance(alternative, int) or alternative < 0:
            raise _refuse(f"the pins entry {key} needs alternative, an index from 0", file, where)
        pins = entry.get("pins")
        if not isinstance(pins, dict) or not pins:
            raise _refuse(f"the pins entry {key} needs pins, a table of role = pin", file, where)
        roles = cast(dict[str, object], pins)
        if not all(isinstance(pin, str) and pin for pin in roles.values()):
            raise _refuse(f"the pins of {key} map each role to a pin name", file, where)
        if "choice" in entry and not isinstance(entry["choice"], str):
            raise _refuse(f"the choice of {key} is text", file, where)
        out[key] = MappingProxyType(
            {
                "kind": entry["kind"],
                "option": entry["option"],
                "alternative": alternative,
                "pins": MappingProxyType(dict(sorted(cast(dict[str, str], roles).items()))),
            }
        )
    return out


LIBRARY_FIELDS: tuple[str, ...] = ("index", "path", "release", "spdx", "tree", "version")
"""The keys of a ``[library.items."<kind>/<id>"]`` entry (change c0279), in the order the file writes them."""
LIBRARY_TABLE = "items"
LIBRARY_KEY = re.compile(r"(symbol|footprint|device|block|board)/[A-Za-z0-9][A-Za-z0-9_.+:/-]*")


def _read_library(table: Mapping[str, object], file: str) -> dict[str, LockValue]:
    """The ``[library.items]`` entries (change c0279): per ``<kind>/<id>`` the pin of a vendored item,
    every key of ``LIBRARY_FIELDS`` a non-empty string. ``path`` is relative to the script folder."""
    unknown = sorted(set(table) - {LIBRARY_TABLE})
    if unknown:
        raise _refuse(f"unknown key {unknown[0]!r} in the section library; it holds items", file, "library")
    items = table.get(LIBRARY_TABLE, {})
    if not isinstance(items, dict):
        raise _refuse("library.items must be a table", file, "library.items")
    out: dict[str, LockValue] = {}
    for key, raw in cast(dict[str, object], items).items():
        where = f"library.items.{key}"
        if not LIBRARY_KEY.fullmatch(key) or ".." in key:
            raise _refuse(f"{key!r} is not a library item key <kind>/<id>", file, where)
        if not isinstance(raw, dict):
            raise _refuse(f"the library entry {key} must be a table", file, where)
        entry = cast(dict[str, object], raw)
        unknown = sorted(set(entry) - set(LIBRARY_FIELDS))
        if unknown:
            raise _refuse(f"unknown key {unknown[0]!r} in the library entry {key}", file, where)
        for name in LIBRARY_FIELDS:
            if not isinstance(entry.get(name), str) or not entry[name]:
                raise _refuse(f"the library entry {key} needs {name}, a non-empty string", file, where)
        path = cast(str, entry["path"])
        if path.startswith("/") or "\\" in path or any(part == ".." for part in path.split("/")):
            raise _refuse(f"the path of {key} stays inside the script folder", file, where)
        out[key] = MappingProxyType({name: entry[name] for name in LIBRARY_FIELDS})
    return out


def pin_choice_text(entry: Mapping[str, object]) -> str:
    """The ``choice`` text of a ``[pins]`` entry: ``I2C1 on PB8/PB9`` (pins in code-point order of roles)."""
    pins = cast(Mapping[str, str], entry.get("pins", {}))
    return f"{entry.get('option', '')} on {'/'.join(pin for _, pin in sorted(pins.items()))}"


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


def _read_blocks(table: Mapping[str, object], file: str) -> dict[str, LockValue]:
    """The ``[blocks]`` entries (change c0268): instance path → ``<id>@<version>``."""
    out: dict[str, LockValue] = {}
    for path, value in table.items():
        where = f"blocks.{path}"
        if not all(NAME.fullmatch(segment) for segment in path.split("/")):
            raise _refuse(f"{path!r} is not an instance path", file, where)
        if not isinstance(value, str) or not BLOCK_PIN.fullmatch(value):
            raise _refuse(f"the block of {path} must be <id>@<MAJOR.MINOR.PATCH>, not {value!r}", file, where)
        out[path] = value
    return out


def _read_picks(table: Mapping[str, object], file: str) -> dict[str, LockValue]:
    """The ``picks`` tables: one table of strings per component path, keys of ``LOCK_KEYS`` in that order."""
    out: dict[str, LockValue] = {}
    for path, entry in table.items():
        where = f"picks.{path}"
        if not all(NAME.fullmatch(segment) for segment in path.split("/")):
            raise _refuse(f"{path!r} is not a component path", file, where)
        if not isinstance(entry, dict):
            raise _refuse(f"the pick of {path} must be a table", file, where)
        values = cast(dict[str, object], entry)
        for key, value in values.items():
            if key not in LOCK_KEYS:
                raise _refuse(
                    f"unknown key {key!r} in the pick of {path}; the keys are {', '.join(LOCK_KEYS)}",
                    file,
                    f"{where}.{key}",
                )
            if not isinstance(value, str):
                raise _refuse(
                    f"{key} of the pick of {path} must be a string, not {value!r}", file, f"{where}.{key}"
                )
        for key in LOCK_REQUIRED:
            if key not in values:
                raise _refuse(f"the pick of {path} has no {key}", file, f"{where}.{key}")
        out[path] = MappingProxyType({key: values[key] for key in LOCK_KEYS if key in values})
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
    if isinstance(value, Mapping):
        table = cast(Mapping[str, object], value)
        keys = {k: k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else _string(k) for k in table}
        return "{ " + ", ".join(f"{keys[k]} = {_scalar(v)}" for k, v in sorted(table.items())) + " }"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return _string(str(value))


def lock_text(lock: Lock) -> str:
    """The canonical text of ``lock``: the header comment, ``schema`` and ``design``, then the non-empty
    sections in the order of ``SECTIONS`` with keys in code-point order (the keys inside a table, such as a
    pick, in the order of the table); LF line ends, one final newline,
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
            if section.name == "library":
                lines += ["", f"[library.{LIBRARY_TABLE}.{_string(key)}]"]
                lines += [f"{name} = {_scalar(value[name])}" for name in LIBRARY_FIELDS if name in value]
                continue
            lines += ["", f"[{section.name}.{_string(key)}]"]
            if section.name == "pins":
                shown = {**value, "choice": pin_choice_text(value)}
                lines += [f"{name} = {_scalar(shown[name])}" for name in PIN_FIELDS if name in shown]
                continue
            lines += [f"{_string(name)} = {_scalar(item)}" for name, item in value.items()]  # fixed key order
    return "\n".join(lines) + "\n"


def needs_lock(design: Design) -> bool:
    """Whether ``design`` has a part without an explicit ref, a query part (change c0254), a take (change
    c0257) or an instance of a block with a record (change c0268), whose ref, pick, pin choice or block
    version the lock keeps (a design with a lock file needs it too)."""
    from fenolite.dsl.block import blocks
    from fenolite.dsl.take import design_takes

    return (
        any(part.explicit_ref is None or part.call_query is not None for part in design.parts.values())
        or bool(design_takes(design))
        or any(found.definition.header is not None for found in blocks(design))
    )


__all__ = [
    "BLOCK_PIN",
    "HEADER",
    "LIBRARY_FIELDS",
    "LOCK_CODES",
    "PIN_FIELDS",
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
    "hand_refs",
    "lock_text",
    "make_lock",
    "natural_key",
    "needs_lock",
    "picks_resolver",
    "pin_choice_text",
    "read_lock",
]
