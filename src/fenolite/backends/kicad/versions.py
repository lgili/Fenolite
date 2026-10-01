# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad format versions: constants, detection, read/write policy and the token inventory.

Facts and their sources: ``docs/formats/kicad/versions.md`` and ``docs/formats/kicad/tokens.md``.
Fenolite reads files from KiCad 8.0 on and writes for KiCad 9.0 or 10.0. It is deliberately stricter
than KiCad about future versions: a file newer than every known constant can be inspected but not
edited, because Fenolite cannot know what an unknown token means.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from importlib import resources
from types import MappingProxyType
from typing import Any, Literal

from fenolite.backends.kicad.sexpr import AtomKind, Node, dumps, parse, walk
from fenolite.core.errors import FenoliteError, FormatError, Issue


class FileKind(StrEnum):
    BOARD = "kicad_pcb"
    FOOTPRINT = "kicad_mod"
    SCHEMATIC = "kicad_sch"
    SYMBOL_LIB = "kicad_sym"
    WORKSHEET = "kicad_wks"
    RULES = "kicad_dru"


class VersionStatus(StrEnum):
    TOO_OLD = "too-old"
    SUPPORTED = "supported"
    FUTURE = "future"


READ_MAJORS: tuple[int, ...] = (8, 9, 10)
TARGET_MAJORS: tuple[int, ...] = (9, 10)
DEFAULT_TARGET = 10
LEGACY_WORKSHEET_VERSION = 0
GENERATOR = "fenolite"

_BOARD = MappingProxyType({8: 20240108, 9: 20241229, 10: 20260206})
FORMAT_VERSIONS: Mapping[FileKind, Mapping[int, int]] = MappingProxyType(
    {
        FileKind.BOARD: _BOARD,
        FileKind.FOOTPRINT: _BOARD,
        FileKind.SCHEMATIC: MappingProxyType({8: 20231120, 9: 20250114, 10: 20260306}),
        FileKind.SYMBOL_LIB: MappingProxyType({8: 20231120, 9: 20241209, 10: 20251024}),
        FileKind.WORKSHEET: MappingProxyType({8: 20231118, 9: 20231118, 10: 20231118}),
        FileKind.RULES: MappingProxyType({9: 1, 10: 1}),
    }
)
READ_FLOOR: Mapping[FileKind, int] = MappingProxyType(
    {
        FileKind.BOARD: 20240108,
        FileKind.FOOTPRINT: 20240108,
        FileKind.SCHEMATIC: 20231120,
        FileKind.SYMBOL_LIB: 20231120,
        FileKind.WORKSHEET: LEGACY_WORKSHEET_VERSION,
        FileKind.RULES: 1,
    }
)
ROOT_HEADS: Mapping[str, FileKind] = MappingProxyType(
    {
        "kicad_pcb": FileKind.BOARD,
        "footprint": FileKind.FOOTPRINT,
        "kicad_sch": FileKind.SCHEMATIC,
        "kicad_symbol_lib": FileKind.SYMBOL_LIB,
        "kicad_wks": FileKind.WORKSHEET,
        "page_layout": FileKind.WORKSHEET,
        "drawing_sheet": FileKind.WORKSHEET,
        "kicad_dru": FileKind.RULES,
    }
)
LEGACY_WORKSHEET_ROOTS = frozenset({"page_layout", "drawing_sheet"})
_SUFFIXES = {f".{kind.value}": kind for kind in FileKind}
UPGRADE_HINTS: Mapping[FileKind, str] = MappingProxyType(
    {
        FileKind.BOARD: "upgrade the board with 'kicad-cli pcb upgrade' (KiCad 10.0 is needed) or re-save it "
        "in KiCad 8.0 or newer",
        FileKind.FOOTPRINT: "upgrade the library with 'kicad-cli fp upgrade'",
        FileKind.SCHEMATIC: "upgrade the schematic with 'kicad-cli sch upgrade' (KiCad 10.0 is needed) "
        "or re-save it in KiCad 8.0 or newer",
        FileKind.SYMBOL_LIB: "upgrade the library with 'kicad-cli sym upgrade'",
        FileKind.WORKSHEET: "re-save the drawing sheet in the KiCad drawing sheet editor",
        FileKind.RULES: "re-save the rules in KiCad's board setup",
    }
)


class FutureFormatError(FormatError):
    """The file is newer than every format version Fenolite knows; it may be inspected, not edited."""

    cli_code = "FEN-3002"

    def __init__(
        self, message: str, *, file: str = "", locator: str = "", offset: int | None = None, hint: str = ""
    ) -> None:
        super().__init__(message, file=file, locator=locator, offset=offset)
        self.hint = hint


class UnsupportedFormatError(FormatError):
    """The file is older than the oldest format version Fenolite reads (KiCad 8.0)."""

    cli_code = "FEN-3003"

    def __init__(
        self, message: str, *, file: str = "", locator: str = "", offset: int | None = None, hint: str = ""
    ) -> None:
        super().__init__(message, file=file, locator=locator, offset=offset)
        self.hint = hint


class DowngradeRefusedError(FenoliteError):
    """Writing for an older major than the input's would drop what that major cannot read."""

    cli_code = "FEN-7002"

    def __init__(self, kind: FileKind, source_major: int, target_major: int) -> None:
        self.kind = kind
        self.source_major = source_major
        self.target_major = target_major
        self.hint = f"use a target of KiCad {source_major}.0 or newer"
        super().__init__(
            f"{kind.value} read as KiCad {source_major}.0 cannot be written for KiCad {target_major}.0"
        )


@dataclass(frozen=True, slots=True)
class FormatInfo:
    kind: FileKind
    version: int
    major: int | None
    status: VersionStatus
    generator: str | None = None
    generator_version: str | None = None


def kind_for_suffix(name: str) -> FileKind | None:
    """The kind of a file name by its suffix (``fp-lib-table`` and others give ``None``)."""
    dot = name.rfind(".")
    return _SUFFIXES.get(name[dot:]) if dot >= 0 else None


def kind_of(node: Node, *, file: str = "") -> FileKind:
    """The kind of a parsed file, from its root head (content is authoritative)."""
    head = node.name
    if head == "module":
        raise UnsupportedFormatError(
            "pre-6 footprint root 'module' is not supported",
            file=file,
            offset=node.offset,
            hint=UPGRADE_HINTS[FileKind.FOOTPRINT],
        )
    kind = ROOT_HEADS.get(head)
    if kind is None:
        raise FormatError(f"unknown root list {head!r}", file=file, offset=node.offset)
    return kind


def detect_version(node: Node, *, file: str = "") -> int:
    """The integer of the root's ``(version N)``; 0 for a legacy worksheet root without one."""
    version = node.find("version")
    if version is None:
        if node.name in LEGACY_WORKSHEET_ROOTS:
            return LEGACY_WORKSHEET_VERSION
        raise FormatError(
            "the format version is missing", file=file, offset=node.offset, locator=f"/{node.name}"
        )
    atoms = version.atoms()
    if len(atoms) != 1 or atoms[0].kind != AtomKind.NUMBER or not re.fullmatch(r"\d+", atoms[0].text):
        raise FormatError(
            "the format version is not an integer",
            file=file,
            offset=version.offset,
            locator=f"/{node.name}/version[0]",
        )
    return int(atoms[0].text)


def major_for(kind: FileKind, version: int) -> int | None:
    """The oldest supported major that reads ``version``; ``None`` below the floor or in the future."""
    if version < READ_FLOOR[kind]:
        return None
    for major in READ_MAJORS:
        constant = FORMAT_VERSIONS[kind].get(major)
        if constant is not None and constant >= version:
            return major
    return None


def classify(kind: FileKind, version: int) -> VersionStatus:
    if version < READ_FLOOR[kind]:
        return VersionStatus.TOO_OLD
    if version > max(FORMAT_VERSIONS[kind].values()):
        return VersionStatus.FUTURE
    return VersionStatus.SUPPORTED


def _text_of(node: Node, name: str) -> str | None:
    child = node.find(name)
    atoms = child.atoms() if child is not None else ()
    return atoms[0].value if atoms else None


def inspect(node: Node, *, file: str = "") -> FormatInfo:
    kind = kind_of(node, file=file)
    version = detect_version(node, file=file)
    return FormatInfo(
        kind,
        version,
        major_for(kind, version),
        classify(kind, version),
        _text_of(node, "generator"),
        _text_of(node, "generator_version"),
    )


def require_readable(info: FormatInfo, *, file: str = "") -> None:
    if info.status == VersionStatus.TOO_OLD:
        raise UnsupportedFormatError(
            f"{info.kind.value} format version {info.version} is older than the oldest supported "
            f"({READ_FLOOR[info.kind]}, KiCad 8.0)",
            file=file,
            hint=UPGRADE_HINTS[info.kind],
        )


def require_editable(info: FormatInfo, *, file: str = "") -> None:
    require_readable(info, file=file)
    if info.status == VersionStatus.FUTURE:
        newest = max(FORMAT_VERSIONS[info.kind].values())
        raise FutureFormatError(
            f"{info.kind.value} format version {info.version} is newer than {newest}, the newest supported",
            file=file,
            hint="inspect it read-only, or use a Fenolite release that supports this KiCad version",
        )


def version_issues(info: FormatInfo) -> tuple[Issue, ...]:
    """A ``kicad.version.future`` warning, or a ``kicad.version.dev`` info for development versions."""
    if info.status == VersionStatus.FUTURE:
        return (
            Issue(
                "kicad.version.future",
                "warning",
                f"{info.kind.value} format version {info.version} is newer than every supported version; "
                "the file is read-only for Fenolite",
            ),
        )
    released = set(FORMAT_VERSIONS[info.kind].values())
    if (
        info.status == VersionStatus.SUPPORTED
        and info.version > min(released)
        and info.version not in released
    ):
        return (
            Issue(
                "kicad.version.dev",
                "info",
                f"{info.kind.value} format version {info.version} was written by a development build; "
                f"KiCad {info.major}.0 reads it",
            ),
        )
    return ()


def check_target(info: FormatInfo, target_major: int) -> int:
    """The header version to write for ``target_major``; refuses old, future and downgrades."""
    if target_major not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target_major}; supported targets: {TARGET_MAJORS}")
    require_editable(info)
    source = major_for(info.kind, info.version)
    assert source is not None  # SUPPORTED always has a major
    if target_major < source:
        raise DowngradeRefusedError(info.kind, source, target_major)
    return FORMAT_VERSIONS[info.kind][target_major]


# --- custom-rules text ----------------------------------------------------------------------------

_RULES_PREFIX = "(kicad_dru\n"


def _shift(node: Node, delta: int) -> Node:
    children = tuple(_shift(c, delta) if isinstance(c, Node) else c for c in node.children)
    offset = None if node.offset is None else node.offset - delta
    return Node(node.head, children, offset, node.comments)


def wrap_rules(text: str, *, file: str = "") -> Node:
    """A synthetic ``kicad_dru`` node over the top-level lists of a rules file (common subset only)."""
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip(" \t").startswith("#"):
            raise FormatError(
                f"line {number}: comment lines in rules files need the rules reader",
                file=file,
                locator=f"line {number}",
            )
    try:
        node = parse(_RULES_PREFIX + text + "\n)", file=file)
    except FormatError as error:
        size = len(text.encode("utf-8"))
        offset = None if error.offset is None else min(size, max(0, error.offset - len(_RULES_PREFIX)))
        raise FormatError(error.message, file=file, locator=error.locator, offset=offset) from error
    node = _shift(node, len(_RULES_PREFIX))
    for locator, current in walk(node):
        for atom in current.atoms():
            if atom.kind == AtomKind.SYMBOL and "'" in atom.text:
                raise FormatError(
                    f"single-quoted names ({atom.text}) need the rules reader",
                    file=file,
                    locator=locator,
                    offset=current.offset,
                )
    return node


def rules_text(node: Node) -> str:
    """The rules file text of a synthetic ``kicad_dru`` node (the wrapper itself is not written)."""
    parts = [dumps(child) if isinstance(child, Node) else child.text + "\n" for child in node.children]
    return "".join(parts)


# --- token inventory ------------------------------------------------------------------------------

NO_ROW_REASONS = frozenset({"no-token-change", "superseded-in-cycle"})
_TOKEN_KEYS = {
    "id",
    "kinds",
    "path",
    "value",
    "since_major",
    "since_version",
    "until_major",
    "older_readers",
    "sources",
    "hypothesis",
    "note",
}
_TOKEN_REQUIRED = {"id", "kinds", "path", "since_major", "sources"}
_FORM_KEYS = {
    "id",
    "kinds",
    "applies_to",
    "since_major",
    "since_version",
    "description",
    "sources",
    "hypothesis",
}
_FORM_REQUIRED = {"id", "kinds", "since_major", "description", "sources"}
_NOTE_KEYS = {"version", "rows", "no_row"}
_TOP_KEYS = {"format", "collected_at", "token", "form", "note"}


@dataclass(frozen=True, slots=True)
class TokenRow:
    id: str
    kinds: frozenset[FileKind]
    pattern: tuple[str, ...]
    anchored: bool
    value: str | None
    since_major: int
    since_version: int | None
    until_major: int | None
    older_readers: Literal["reject", "ignore"]
    sources: tuple[str, ...]
    hypothesis: str | None
    note: str

    @property
    def path(self) -> str:
        return ("/" if self.anchored else "") + "/".join(self.pattern)


@dataclass(frozen=True, slots=True)
class FormRow:
    id: str
    kinds: frozenset[FileKind]
    applies_to: str
    since_major: int
    since_version: int | None
    description: str
    sources: tuple[str, ...]
    hypothesis: str | None


@dataclass(frozen=True, slots=True)
class Note:
    version: int
    rows: tuple[str, ...]
    no_row: str | None


def _head_matches(pattern: str, head: str) -> bool:
    return head.isdigit() if pattern == "#" else pattern == head


@dataclass(frozen=True, slots=True)
class Inventory:
    tokens: tuple[TokenRow, ...]
    forms: tuple[FormRow, ...]
    notes: tuple[Note, ...]
    collected_at: tuple[str, ...]
    _by_last: dict[str, tuple[TokenRow, ...]] = field(default_factory=lambda: {}, compare=False, repr=False)

    def __post_init__(self) -> None:
        index: dict[str, list[TokenRow]] = {}
        for row in self.tokens:
            index.setdefault(row.pattern[-1], []).append(row)
        object.__setattr__(self, "_by_last", {k: tuple(v) for k, v in index.items()})

    def match(self, kind: FileKind, chain: Sequence[str], value: str | None = None) -> TokenRow | None:
        """The most specific token row for a node (``value`` None) or a symbol value under it."""
        if not chain:
            return None
        candidates = list(self._by_last.get(chain[-1], ()))
        if chain[-1].isdigit():
            candidates += self._by_last.get("#", ())
        best: TokenRow | None = None
        for row in candidates:
            if kind not in row.kinds or row.value != value:
                continue
            pattern = row.pattern
            if row.anchored:
                if len(pattern) != len(chain):
                    continue
                window: Sequence[str] = chain
            else:
                if len(pattern) > len(chain):
                    continue
                window = chain[len(chain) - len(pattern) :]
            if all(_head_matches(p, h) for p, h in zip(pattern, window, strict=True)):
                key = (len(pattern), row.anchored)
                if best is None or key > (len(best.pattern), best.anchored):
                    best = row
        return best

    def form(self, form_id: str) -> FormRow:
        for row in self.forms:
            if row.id == form_id:
                return row
        raise KeyError(form_id)


def _fail(message: str, file: str) -> FormatError:
    return FormatError(message, file=file)


def _kinds(raw: Any, ident: str, file: str) -> frozenset[FileKind]:
    if not isinstance(raw, list) or not raw:
        raise _fail(f"row {ident}: kinds must be a non-empty list", file)
    try:
        return frozenset(FileKind(k) for k in raw)  # pyright: ignore[reportUnknownVariableType]
    except ValueError as exc:
        raise _fail(f"row {ident}: unknown kind in {raw!r}", file) from exc


def _common(
    entry: dict[str, Any], ident: str, kinds: frozenset[FileKind], file: str
) -> tuple[int, int | None]:
    since = entry["since_major"]
    if since not in READ_MAJORS:
        raise _fail(f"row {ident}: since_major {since!r} is not one of {READ_MAJORS}", file)
    dated = entry.get("since_version")
    if dated is not None:
        if FileKind.RULES in kinds:
            raise _fail(
                f"row {ident}: rules rows have no since_version (every rules file is version 1)", file
            )
        for kind in kinds:
            if major_for(kind, int(dated)) != since:
                owner = major_for(kind, int(dated))
                raise _fail(f"row {ident}: since_version {dated} belongs to major {owner}, not {since}", file)
    sources = entry["sources"]
    if not isinstance(sources, list) or not sources:
        raise _fail(f"row {ident}: sources must not be empty", file)
    return since, dated


def _check_keys(entry: dict[str, Any], allowed: set[str], required: set[str], label: str, file: str) -> None:
    unknown = sorted(set(entry) - allowed)
    if unknown:
        raise _fail(f"{label}: unknown key(s) {', '.join(unknown)}", file)
    missing = sorted(required - set(entry))
    if missing:
        raise _fail(f"{label}: missing key(s) {', '.join(missing)}", file)


def _parse_inventory(text: str, file: str) -> Inventory:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise _fail(f"invalid TOML: {exc}", file) from exc
    unknown = sorted(set(data) - _TOP_KEYS)
    if unknown:
        raise _fail(f"unknown top-level key(s) {', '.join(unknown)}", file)
    if data.get("format") != 1:
        raise _fail("format must be 1", file)
    tokens: list[TokenRow] = []
    forms: list[FormRow] = []
    ids: set[str] = set()
    seen_paths: dict[tuple[FileKind, str, str | None], str] = {}
    for entry in data.get("token", []):
        ident = str(entry.get("id", "?"))
        _check_keys(entry, _TOKEN_KEYS, _TOKEN_REQUIRED, f"row {ident}", file)
        if ident in ids:
            raise _fail(f"row {ident}: duplicate id", file)
        ids.add(ident)
        kinds = _kinds(entry["kinds"], ident, file)
        since, dated = _common(entry, ident, kinds, file)
        until = entry.get("until_major")
        if until is not None and (until not in READ_MAJORS or until <= since):
            raise _fail(
                f"row {ident}: until_major {until} must be a major greater than since_major {since}", file
            )
        readers = entry.get("older_readers", "reject")
        if readers not in ("reject", "ignore"):
            raise _fail(f"row {ident}: older_readers must be 'reject' or 'ignore'", file)
        path = str(entry["path"])
        anchored = path.startswith("/")
        pattern = tuple(p for p in path.strip("/").split("/"))
        if not all(pattern):
            raise _fail(f"row {ident}: empty head in path {path!r}", file)
        value = entry.get("value")
        for kind in kinds:
            key = (kind, path, value)
            if key in seen_paths:
                raise _fail(f"rows {seen_paths[key]} and {ident}: duplicate kinds, path and value", file)
            seen_paths[key] = ident
        tokens.append(
            TokenRow(
                ident,
                kinds,
                pattern,
                anchored,
                value,
                since,
                dated,
                until,
                readers,
                tuple(entry["sources"]),
                entry.get("hypothesis"),
                str(entry.get("note", "")),
            )
        )
    for entry in data.get("form", []):
        ident = str(entry.get("id", "?"))
        _check_keys(entry, _FORM_KEYS, _FORM_REQUIRED, f"row {ident}", file)
        if ident in ids:
            raise _fail(f"row {ident}: duplicate id", file)
        ids.add(ident)
        kinds = _kinds(entry["kinds"], ident, file)
        since, dated = _common(entry, ident, kinds, file)
        forms.append(
            FormRow(
                ident,
                kinds,
                str(entry.get("applies_to", "")),
                since,
                dated,
                str(entry["description"]),
                tuple(entry["sources"]),
                entry.get("hypothesis"),
            )
        )
    notes: list[Note] = []
    raw_notes: list[dict[str, Any]] = list(data.get("note", []))
    for entry in raw_notes:
        label = f"note {entry.get('version', '?')}"
        _check_keys(entry, _NOTE_KEYS, {"version"}, label, file)
        rows: list[str] | None = entry.get("rows")
        reason: str | None = entry.get("no_row")
        if (rows is None) == (reason is None):
            raise _fail(f"{label}: exactly one of rows and no_row is required", file)
        if reason is not None and reason not in NO_ROW_REASONS:
            raise _fail(f"{label}: unknown no_row reason {reason!r}", file)
        for ident in rows or []:
            if ident not in ids:
                raise _fail(f"{label}: unknown row id {ident!r}", file)
        notes.append(Note(int(entry["version"]), tuple(rows or ()), reason))
    return Inventory(tuple(tokens), tuple(forms), tuple(notes), tuple(data.get("collected_at", ())))


@cache
def _packaged() -> Inventory:
    text = resources.files("fenolite.backends.kicad").joinpath("data/tokens.toml").read_text(encoding="utf-8")
    return _parse_inventory(text, "fenolite/backends/kicad/data/tokens.toml")


def load_inventory(text: str | None = None, *, file: str = "") -> Inventory:
    """The packaged inventory (cached), or the inventory in ``text`` after validation."""
    return _packaged() if text is None else _parse_inventory(text, file)


def _row_for(kind: FileKind, token_path: str, value: str | None) -> TokenRow | None:
    return load_inventory().match(kind, [h for h in token_path.split("/") if h], value)


def min_version(kind: FileKind, token_path: str, *, value: str | None = None) -> int | None:
    """The oldest format version that may carry ``token_path`` (head chain from the root)."""
    row = _row_for(kind, token_path, value)
    if row is None:
        return None
    if row.since_version is not None:
        return row.since_version
    return FORMAT_VERSIONS[kind].get(row.since_major, READ_FLOOR[kind])


def min_major(kind: FileKind, token_path: str, *, value: str | None = None) -> int | None:
    row = _row_for(kind, token_path, value)
    return None if row is None else row.since_major


def _row_issue(row: TokenRow, locator: str, target_major: int, what: str) -> Issue | None:
    sources = ", ".join(row.sources)
    if row.since_major > target_major:
        return Issue(
            "kicad.token.too-new",
            "error",
            f"{what} needs KiCad {row.since_major}.0; the target is KiCad {target_major}.0",
            where=locator,
            hint=f"row {row.id} ({sources})",
        )
    if row.until_major is not None and row.until_major < target_major:
        return Issue(
            "kicad.token.obsolete",
            "warning",
            f"{what} is no longer written by KiCad {target_major}.0 (last: {row.until_major}.0)",
            where=locator,
            hint=f"row {row.id} ({sources})",
        )
    return None


def check_emittable(node: Node, kind: FileKind, target_major: int) -> tuple[Issue, ...]:
    """Every header or token in ``node`` that KiCad ``target_major`` cannot read, in document order."""
    if target_major not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target_major}; supported targets: {TARGET_MAJORS}")
    inventory = load_inventory()
    issues: list[Issue] = []
    root = f"/{node.name}"
    try:
        version = detect_version(node)
    except FormatError:
        issues.append(
            Issue("kicad.version.header-missing", "error", "the root has no (version N)", where=root)
        )
    else:
        limit = FORMAT_VERSIONS[kind].get(target_major)
        if limit is not None and version > limit:
            issues.append(
                Issue(
                    "kicad.version.header-too-new",
                    "error",
                    f"header version {version} is newer than {limit}, KiCad {target_major}.0's",
                    where=root,
                )
            )
    vocabulary = kind in (FileKind.WORKSHEET, FileKind.RULES)
    chains: dict[str, tuple[str, ...]] = {}
    for locator, current in walk(node):
        parent = locator.rsplit("/", 1)[0]
        chain = (*chains.get(parent, ()), current.name)
        chains[locator] = chain
        row = inventory.match(kind, chain)
        if row is not None:
            issue = _row_issue(row, locator, target_major, f"'{current.name}'")
            if issue is not None:
                issues.append(issue)
        elif vocabulary and locator != root:
            issues.append(
                Issue(
                    "kicad.token.uninventoried",
                    "warning",
                    f"'{current.name}' is not in the {kind.value} inventory",
                    where=locator,
                )
            )
        for atom in current.atoms():
            if atom.kind != AtomKind.SYMBOL:
                continue
            value_row = inventory.match(kind, chain, atom.text)
            if value_row is not None:
                issue = _row_issue(value_row, locator, target_major, f"'{current.name} {atom.text}'")
                if issue is not None:
                    issues.append(issue)
            elif kind == FileKind.RULES and current.name == "constraint":
                issues.append(
                    Issue(
                        "kicad.token.uninventoried",
                        "warning",
                        f"constraint value '{atom.text}' is not in the rules inventory",
                        where=locator,
                    )
                )
    return tuple(issues)


__all__ = [
    "DEFAULT_TARGET",
    "FORMAT_VERSIONS",
    "GENERATOR",
    "LEGACY_WORKSHEET_VERSION",
    "READ_FLOOR",
    "READ_MAJORS",
    "ROOT_HEADS",
    "TARGET_MAJORS",
    "DowngradeRefusedError",
    "FileKind",
    "FormRow",
    "FormatInfo",
    "FutureFormatError",
    "Inventory",
    "Note",
    "TokenRow",
    "UnsupportedFormatError",
    "VersionStatus",
    "check_emittable",
    "check_target",
    "classify",
    "detect_version",
    "inspect",
    "kind_for_suffix",
    "kind_of",
    "load_inventory",
    "major_for",
    "min_major",
    "min_version",
    "require_editable",
    "require_readable",
    "rules_text",
    "version_issues",
    "wrap_rules",
]
