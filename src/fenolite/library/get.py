# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What ``fenolite get`` plans (change c0279, ``docs/library-repo.md``, "fenolite get"; ADR-0008).

The planner is pure: it takes one release (:class:`Source`: its index and the archives at hand), the project
(the script folder and its lock) and the request, and returns the files to write and remove, the new lock
section ``library``, ``fenolite_library/ATTRIBUTION.md`` and the result rows. It never imports, runs or
builds a payload. Every archive is checked against its index row and every item against its tree before a
byte is planned; a difference is ``FEN-3006``. The client checks licences too (``FEN-3021``).
"""

from __future__ import annotations

import ast
import hashlib
import posixpath
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from fenolite.core.errors import FenoliteError, Issue
from fenolite.dsl.lock import Lock, LockValue, lock_text, make_lock, read_lock
from fenolite.library.codes import issue
from fenolite.library.items import (
    ALWAYS_ALLOWED,
    FOLDERS,
    ITEM_FILE,
    KINDS,
    LICENSE_FILE,
    NOTICE_FILE,
    PROVENANCE_FILE,
    VENDOR_FOLDER,
    ItemError,
    folder_files,
    item_folder,
    item_key,
    load_json,
    read_item,
    tree_digest,
    version_key,
)
from fenolite.library.licences import CC0, shipped
from fenolite.library.release import archive_members

ITEM_KIND = "library-item"
ATTRIBUTION_KIND = "attribution"
LOCK_KIND = "lock"
CACHE_KIND = "library-cache"
ATTRIBUTION = f"{VENDOR_FOLDER}/ATTRIBUTION.md"
BOARD_LOCK = "design.lock"
"""A board's own lock, part of its payload; ``get`` merges the pin into it."""


class GetRefused(FenoliteError):
    """A refusal of ``get`` with its ``FEN-`` code (``cli_code``), hint and issues."""

    cli_code = "FEN-2001"

    def __init__(self, message: str, *, hint: str = "", issues: Sequence[Issue] = ()) -> None:
        super().__init__(message)
        self.hint = hint
        self.issues = tuple(issues)


class UsageRefused(GetRefused):
    cli_code = "FEN-2001"


class DigestRefused(GetRefused):
    cli_code = "FEN-3006"


class LicenceRefused(GetRefused):
    cli_code = "FEN-3021"


class MalformedRelease(GetRefused):
    cli_code = "FEN-3004"


class ModifiedRefused(GetRefused):
    cli_code = "FEN-7001"


@dataclass(frozen=True)
class Source:
    """One release: its ``version``, index (parsed and as bytes) and ``origin`` (``from``, ``tree``,
    ``cache`` or ``network``). ``asset`` gives the bytes of an archive at hand, or ``None`` when it must be
    downloaded first (a dry run); the planner checks them against the index."""

    version: str
    index: Mapping[str, Any]
    index_bytes: bytes
    origin: str
    asset: Callable[[str], bytes | None]

    @property
    def index_sha256(self) -> str:
        return hashlib.sha256(self.index_bytes).hexdigest()

    def rows(self) -> list[Mapping[str, Any]]:
        return cast(list[Mapping[str, Any]], self.index.get("items", []))

    def row(self, kind: str, ident: str) -> Mapping[str, Any] | None:
        return next((r for r in self.rows() if r.get("kind") == kind and r.get("id") == ident), None)

    def archive_row(self, name: str) -> Mapping[str, Any]:
        found = next(
            (
                a
                for a in cast(list[Mapping[str, Any]], self.index.get("archives", []))
                if a.get("name") == name
            ),
            None,
        )
        if found is None:
            raise MalformedRelease(f"the index of release {self.version} lists no archive {name}")
        return found


@dataclass(frozen=True)
class Project:
    """Where items go: ``folder`` (absolute) holds the script, or is the board folder; ``shown`` is that
    folder relative to the working folder (``""`` for itself); the lock file and its content."""

    cwd: Path
    folder: Path
    shown: str
    lock_file: Path
    lock: Lock | None
    design: str

    def rel(self, path: str) -> str:
        """``path`` (relative to the folder) relative to the working folder, POSIX and normalised."""
        return posixpath.normpath(f"{self.shown}/{path}" if self.shown else path)

    @property
    def entries(self) -> Mapping[str, Mapping[str, str]]:
        if self.lock is None:
            return {}
        return cast(Mapping[str, Mapping[str, str]], self.lock.sections.get("library", {}))


@dataclass(frozen=True)
class Write:
    """One planned file: ``path`` relative to the working folder (or absolute in the cache), its ``kind``,
    its bytes (``None`` until a download) with the ``size`` and ``sha256`` they must have."""

    path: str
    kind: str
    data: bytes | None
    size: int
    sha256: str


def write_of(path: str, kind: str, data: bytes) -> Write:
    return Write(path, kind, data, len(data), hashlib.sha256(data).hexdigest())


@dataclass
class GetPlan:
    """The writes, the files to remove, the result rows and the issues of one ``get``."""

    writes: list[Write] = field(default_factory=lambda: [])
    removals: list[str] = field(default_factory=lambda: [])
    items: list[dict[str, Any]] = field(default_factory=lambda: [])
    issues: list[Issue] = field(default_factory=lambda: [])
    notes: list[str] = field(default_factory=lambda: [])
    lock_entries: dict[str, Mapping[str, str]] = field(default_factory=lambda: {})


# -- helpers


def design_name(script: Path, fallback: str) -> str:
    """The name of the design that ``script`` declares, read without running it: the first string given to
    a call named ``Design`` (positional or ``name=``); ``fallback`` when none is found."""
    try:
        tree = ast.parse(script.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
        return fallback
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        if name != "Design":
            continue
        values = [*node.args[:1], *(k.value for k in node.keywords if k.arg == "name")]
        for value in values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value:
                return value.value
    return fallback


def read_project_lock(path: Path, shown: str) -> Lock | None:
    if not path.is_file():
        return None
    return read_lock(path.read_text(encoding="utf-8"), file=shown)


def row_files(row: Mapping[str, Any]) -> list[tuple[str, int, str]]:
    return [
        (str(f["path"]), int(f["bytes"]), str(f["sha256"]))
        for f in cast(list[Mapping[str, Any]], row.get("files", []))
    ]


def pinned_tree(row: Mapping[str, Any]) -> str:
    """The tree the lock pins: the item's tree, without a board's own ``design.lock``."""
    if row.get("kind") != "board":
        return str(row.get("tree"))
    return tree_digest([f for f in row_files(row) if f[0] != BOARD_LOCK])


def local_tree(folder: Path, kind: str) -> str | None:
    """The tree of a vendored copy, over the files its ``item.json`` lists and the fixed files (a board's
    ``design.lock`` left out), or ``None`` when the folder is missing."""
    if not folder.is_dir():
        return None
    try:
        listed: set[str] = set(read_item((folder / ITEM_FILE).read_bytes()).files)
    except (OSError, ItemError):
        listed = set()
    rows: list[tuple[str, int, str]] = []
    for name in sorted({*listed, *ALWAYS_ALLOWED}):
        if kind == "board" and name == BOARD_LOCK:
            continue
        path = folder / name
        if path.is_file():
            data = path.read_bytes()
            rows.append((name, len(data), hashlib.sha256(data).hexdigest()))
        elif name in listed:
            rows.append((name, -1, "missing"))
    return tree_digest(rows)


def _licence_check(row: Mapping[str, Any]) -> None:
    lists = shipped()
    key = item_key(str(row.get("kind")), str(row.get("id")))
    spdx = str(row.get("spdx", ""))
    reason = lists.deny_reason(spdx)
    if reason is not None:
        raise LicenceRefused(
            f"{key} is under {spdx!r}, which the shipped allow-list refuses ({reason}); nothing was written",
            hint="only items under an allowed licence can be got",
            issues=[issue("library.licence-denied", f"{key}: {spdx!r} is refused ({reason})", where=key)],
        )
    names = {f[0] for f in row_files(row)}
    missing = [name for name in (LICENSE_FILE, NOTICE_FILE, PROVENANCE_FILE) if name not in names]
    if missing:
        raise LicenceRefused(
            f"{key} lacks {', '.join(missing)}; nothing was written",
            hint="report the item to the library: every item carries LICENSE and NOTICE",
        )


def _archive(source: Source, name: str, memo: dict[str, dict[str, bytes] | None]) -> dict[str, bytes] | None:
    if name in memo:
        return memo[name]
    expected = source.archive_row(name)
    data = source.asset(name)
    if data is None:
        memo[name] = None
        return None
    found = hashlib.sha256(data).hexdigest()
    if len(data) != int(expected.get("bytes", -1)) or found != expected.get("sha256"):
        raise DigestRefused(
            f"{name}: expected {expected.get('bytes')} bytes with SHA-256 {expected.get('sha256')}, found "
            f"{len(data)} bytes with SHA-256 {found}; nothing was written",
            hint="get the release again, or name a good copy with --from DIR",
        )
    try:
        memo[name] = archive_members(data, name=name)
    except ValueError as exc:
        raise DigestRefused(f"{exc}; nothing was written") from exc
    return memo[name]


def item_payload(
    source: Source, row: Mapping[str, Any], memo: dict[str, dict[str, bytes] | None]
) -> dict[str, bytes] | None:
    """The files of one item from its archive, checked against the row; ``None`` before a download."""
    members = _archive(source, str(row.get("archive")), memo)
    if members is None:
        return None
    key = item_key(str(row.get("kind")), str(row.get("id")))
    prefix = f"{row.get('path')}/"
    files = {path[len(prefix) :]: data for path, data in members.items() if path.startswith(prefix)}
    wanted = {name: (size, sha) for name, size, sha in row_files(row)}
    found = {name: (len(data), hashlib.sha256(data).hexdigest()) for name, data in files.items()}
    tree = tree_digest(files)
    if found != wanted or tree != row.get("tree"):
        raise DigestRefused(
            f"{key}: the archive holds the tree {tree}, the index says {row.get('tree')}; nothing was written"
        )
    try:
        record = load_json(files[PROVENANCE_FILE], f"{key}/{PROVENANCE_FILE}")
    except ItemError as exc:
        raise LicenceRefused(f"{exc}; nothing was written") from exc
    if record.get("spdx") != row.get("spdx"):
        raise LicenceRefused(
            f"{key}: the index says {row.get('spdx')!r} and PROVENANCE.json says {record.get('spdx')!r}; "
            "nothing was written",
            issues=[
                issue(
                    "library.licence-denied",
                    f"{key}: the index and PROVENANCE.json disagree on the licence",
                    where=key,
                )
            ],
        )
    return files


def closure(
    source: Source, wanted: Sequence[tuple[str, str, str | None]]
) -> list[tuple[Mapping[str, Any], list[str]]]:
    """The rows of the requested items and of their ``depends``, each with the keys that need it."""
    order: list[str] = []
    rows: dict[str, Mapping[str, Any]] = {}
    needed: dict[str, list[str]] = {}
    pending: list[tuple[str, str, str | None, str | None]] = [(k, i, v, None) for k, i, v in wanted]
    while pending:
        kind, ident, version, by = pending.pop(0)
        key = item_key(kind, ident)
        row = source.row(kind, ident)
        if row is None:
            if by is None:
                raise UsageRefused(
                    f"release {source.version} holds no {kind} {ident}",
                    hint="search the cached index with fenolite get --search TEXT",
                )
            raise MalformedRelease(f"{by} depends on {key}, which release {source.version} does not hold")
        if version is not None and row.get("version") != version:
            if by is None:
                raise UsageRefused(
                    f"release {source.version} holds {key} at {row.get('version')}, not {version}",
                    hint=f"versions found: {row.get('version')}; name the release with --release",
                )
            raise MalformedRelease(
                f"{by} depends on {key} {version}; release {source.version} holds {row.get('version')}"
            )
        if key in rows:
            if by is not None and by not in needed[key]:
                needed[key].append(by)
            continue
        rows[key] = row
        needed[key] = [by] if by is not None else []
        order.append(key)
        for depend in cast(list[Mapping[str, str]], row.get("depends", [])):
            pending.append((depend["kind"], depend["id"], depend["version"], key))
    return [(rows[key], needed[key]) for key in order]


def obligations(spdx: str) -> tuple[str, bool, list[str]]:
    family = shipped().family_of(spdx)
    if family is None:
        return ("", False, [])
    return (family.name, family.reciprocal, list(family.obligations))


def licences_of(items: Iterable[Mapping[str, Any]], accepted: Iterable[str]) -> list[dict[str, Any]]:
    given = set(accepted)
    ids = sorted({str(item["spdx"]) for item in items})
    return [
        {"spdx": spdx, "accept_required": spdx != CC0, "accepted": spdx == CC0 or spdx in given}
        for spdx in ids
    ]


def missing_acceptance(items: Iterable[Mapping[str, Any]], accepted: Iterable[str]) -> list[str]:
    return [row["spdx"] for row in licences_of(items, accepted) if not row["accepted"]]


# -- attribution


def _disk_info(project: Project, key: str, entry: Mapping[str, str]) -> dict[str, Any]:
    folder = project.folder / entry["path"]
    info: dict[str, Any] = {
        "key": key,
        "version": entry["version"],
        "spdx": entry["spdx"],
        "path": entry["path"],
    }
    try:
        item = read_item((folder / ITEM_FILE).read_bytes())
        record = load_json((folder / PROVENANCE_FILE).read_bytes(), PROVENANCE_FILE)
    except (OSError, ItemError):
        return info
    upstream = record.get("upstream")
    info.update(
        title=item.title,
        authors=list(cast(list[str], record.get("authors") or [])),
        upstream=cast(dict[str, Any], upstream) if isinstance(upstream, dict) else None,
        notice=str(record.get("modification_notice", "")),
    )
    return info


def _row_info(row: Mapping[str, Any], path: str) -> dict[str, Any]:
    return {
        "key": item_key(str(row["kind"]), str(row["id"])),
        "version": row.get("version"),
        "spdx": row.get("spdx"),
        "path": path,
        "title": row.get("title"),
        "authors": list(cast(list[str], row.get("authors") or [])),
        "upstream": row.get("upstream"),
        "notice": row.get("notice", ""),
    }


def attribution_text(infos: Iterable[Mapping[str, Any]]) -> bytes:
    """``fenolite_library/ATTRIBUTION.md``: one section per vendored item, sorted by kind and id."""
    order = {kind: n for n, kind in enumerate(KINDS)}

    def sort_key(info: Mapping[str, Any]) -> tuple[int, str]:
        kind, _, ident = str(info["key"]).partition("/")
        return (order.get(kind, len(KINDS)), ident)

    lines = [
        "# Attribution of library items",
        "",
        "Written by `fenolite get` from the items vendored in this folder; each item folder keeps its",
        "LICENSE, NOTICE and PROVENANCE.json. Ship this file with outputs made from these items.",
    ]
    rows = sorted(infos, key=sort_key)
    if not rows:
        lines += ["", "No item is vendored."]
    for info in rows:
        kind, _, ident = str(info["key"]).partition("/")
        upstream = cast(Mapping[str, Any] | None, info.get("upstream"))
        origin = (
            f"{upstream.get('url')} at commit {upstream.get('commit')}"
            if upstream
            else "authored for fenolite-library"
        )
        authors = ", ".join(cast(list[str], info.get("authors") or [])) or "not recorded"
        lines += [
            "",
            f"## {info.get('title') or ident}",
            "",
            f"- Item: {kind} `{ident}` {info.get('version')}",
            f"- Licence: {info.get('spdx')}",
            f"- Authors: {authors}",
            f"- Upstream: {origin}",
            f"- Changes: {info.get('notice') or 'not recorded'}",
            f"- Folder: `{info.get('path')}`",
        ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _result_row(
    row: Mapping[str, Any],
    *,
    required_by: list[str],
    path: str,
    source: Source,
    action: str,
    before: str | None,
) -> dict[str, Any]:
    family, reciprocal, duties = obligations(str(row.get("spdx")))
    return {
        "kind": row.get("kind"),
        "id": row.get("id"),
        "version": row.get("version"),
        "release": source.version,
        "spdx": row.get("spdx"),
        "family": family,
        "reciprocal": reciprocal,
        "obligations": duties,
        "authors": list(cast(list[str], row.get("authors") or [])),
        "upstream": row.get("upstream"),
        "path": path,
        "tree": row.get("tree"),
        "bytes": row.get("bytes"),
        "executes": bool(row.get("executes")),
        "required_by": required_by,
        "proof": row.get("proof"),
        "evidence": row.get("evidence", "UNVERIFIED"),
        "action": action,
        "before": before,
        "after": row.get("version"),
    }


def _files_below(path: str, project: Project) -> list[str]:
    """The files of the vendored folder ``path`` (relative to the project folder), relative to the working
    folder."""
    try:
        return [project.rel(f"{path}/{name}") for name in folder_files(project.folder / path)]
    except (OSError, ItemError):
        return []


def _lock_bytes(project: Project, entries: Mapping[str, Mapping[str, str]], base: Lock | None) -> bytes:
    lock = base if base is not None else project.lock
    sections: dict[str, Mapping[str, LockValue]] = dict(lock.sections) if lock is not None else {}
    sections["library"] = MappingProxyType(dict(sorted(entries.items())))
    design = lock.design if lock is not None else project.design
    return lock_text(make_lock(design, sections)).encode("utf-8")


def _entry(row: Mapping[str, Any], source: Source, path: str) -> Mapping[str, str]:
    return MappingProxyType(
        {
            "index": f"sha256:{source.index_sha256}",
            "path": path,
            "release": source.version,
            "spdx": str(row.get("spdx")),
            "tree": pinned_tree(row),
            "version": str(row.get("version")),
        }
    )


def _modified(project: Project, key: str, entry: Mapping[str, str], kind: str) -> bool:
    found = local_tree(project.folder / entry["path"], kind)
    return found is not None and found != entry["tree"]


def _refuse_modified(keys: Sequence[str], what: str) -> ModifiedRefused:
    return ModifiedRefused(
        f"the vendored {', '.join(keys)} changed after it was got, so {what} would lose the edit; "
        "nothing was written",
        hint="keep the edit elsewhere first, or pass --allow-lossy to replace it",
        issues=[
            issue("library.item-modified", f"{key}: the folder's tree differs from its pin", where=key)
            for key in keys
        ],
    )


def plan_get(
    source: Source, wanted: Sequence[tuple[str, str, str | None]], project: Project, *, allow_lossy: bool
) -> GetPlan:
    """The plan of ``get KIND ID`` (the items of ``wanted`` and their closure) into ``project``."""
    plan = GetPlan()
    rows = closure(source, wanted)
    for row, _ in rows:
        _licence_check(row)
    entries = dict(project.entries)
    requested = {item_key(k, i) for k, i, _ in wanted}
    board = any(row.get("kind") == "board" for row, _ in rows)
    conflicts: list[Issue] = []
    modified: list[str] = []
    memo: dict[str, dict[str, bytes] | None] = {}
    payload_lock: Lock | None = None
    for row, needed in rows:
        kind, ident = str(row["kind"]), str(row["id"])
        key = item_key(kind, ident)
        path = "." if kind == "board" else item_folder(kind, ident)
        folder = project.folder / path
        entry = entries.get(key)
        before: str | None = None
        action = "added"
        if entry is not None:
            same = entry["version"] == row.get("version") and entry["tree"] == pinned_tree(row)
            if same and folder.is_dir():
                plan.items.append(
                    _result_row(
                        row,
                        required_by=needed,
                        path=project.rel(path),
                        source=source,
                        action="kept",
                        before=entry["version"],
                    )
                )
                continue
            if same:
                action = "restored"
            elif key not in requested:
                wanted_version, have = row.get("version"), entry["version"]
                conflicts.append(
                    issue(
                        "library.depends-conflict",
                        f"{', '.join(needed)} needs {key} {wanted_version}, "
                        f"but the project vendors it at {have}",
                        where=key,
                        hint=f"get {key} {wanted_version} first, or keep the version that needs {have}",
                    )
                )
                continue
            else:
                action, before = "updated", entry["version"]
                if _modified(project, key, entry, kind):
                    modified.append(key)
        plan.items.append(
            _result_row(
                row, required_by=needed, path=project.rel(path), source=source, action=action, before=before
            )
        )
        files = item_payload(source, row, memo)
        for name, size, sha in row_files(row):
            if kind == "board" and name == BOARD_LOCK:
                continue
            data = None if files is None else files[name]
            plan.writes.append(Write(project.rel(f"{path}/{name}"), ITEM_KIND, data, size, sha))
        if kind == "board" and files is not None and BOARD_LOCK in files:
            payload_lock = read_lock(files[BOARD_LOCK].decode("utf-8"), file=f"{ident}/{BOARD_LOCK}")
        if action == "updated" and kind != "board":
            keep = {name for name, _, _ in row_files(row)}
            for name in folder_files(folder) if folder.is_dir() else {}:
                if name not in keep:
                    plan.removals.append(project.rel(f"{path}/{name}"))
        entries[key] = _entry(row, source, path)
    if conflicts:
        return GetPlan(items=plan.items, issues=conflicts)
    if modified and not allow_lossy:
        raise _refuse_modified(modified, "the update")
    infos = [
        _row_info(row, "." if row["kind"] == "board" else item_folder(str(row["kind"]), str(row["id"])))
        for row, _ in rows
    ]
    plan.lock_entries = entries
    _finish(
        plan,
        project,
        entries,
        {str(i["key"]): i for i in infos},
        base=payload_lock,
        lock_known=not board or payload_lock is not None or not _board_has_lock(rows),
    )
    return plan


def _board_has_lock(rows: Sequence[tuple[Mapping[str, Any], list[str]]]) -> bool:
    return any(
        row.get("kind") == "board" and any(f[0] == BOARD_LOCK for f in row_files(row)) for row, _ in rows
    )


def _finish(
    plan: GetPlan,
    project: Project,
    entries: Mapping[str, Mapping[str, str]],
    known: Mapping[str, Mapping[str, Any]],
    *,
    base: Lock | None = None,
    lock_known: bool = True,
) -> None:
    infos = [
        dict(known[key]) if key in known else _disk_info(project, key, entry)
        for key, entry in sorted(entries.items())
    ]
    plan.writes.append(write_of(project.rel(ATTRIBUTION), ATTRIBUTION_KIND, attribution_text(infos)))
    if lock_known:
        plan.writes.append(
            write_of(project.rel(project.lock_file.name), LOCK_KIND, _lock_bytes(project, entries, base))
        )
    else:
        plan.notes.append(
            "the board's design.lock is planned once its archive is downloaded: confirm to download it"
        )


def plan_remove(kind: str, ident: str, project: Project, *, allow_lossy: bool) -> GetPlan:
    """The plan of ``get --remove KIND ID``: the folder's files, the lock entry and the attribution."""
    key = item_key(kind, ident)
    entries = dict(project.entries)
    entry = entries.get(key)
    if entry is None:
        raise UsageRefused(f"the lock pins no {key}", hint="list the pins with fenolite get --status")
    if kind == "board":
        raise UsageRefused("a board is a project of its own: delete its folder to remove it")
    for other, other_entry in sorted(entries.items()):
        if other == key:
            continue
        try:
            item = read_item((project.folder / other_entry["path"] / ITEM_FILE).read_bytes())
        except (OSError, ItemError):
            continue
        if any(d.key == key for d in item.depends):
            raise UsageRefused(
                f"{other} depends on {key}; remove {other} first",
                hint=f"fenolite get --remove {other.replace('/', ' ', 1)}",
            )
    if _modified(project, key, entry, kind) and not allow_lossy:
        raise _refuse_modified([key], "the removal")
    plan = GetPlan()
    plan.removals = _files_below(entry["path"], project)
    del entries[key]
    plan.items.append(
        {
            "kind": kind,
            "id": ident,
            "version": entry["version"],
            "path": project.rel(entry["path"]),
            "action": "removed",
            "before": entry["version"],
            "after": None,
        }
    )
    plan.lock_entries = entries
    _finish(plan, project, entries, {})
    return plan


def plan_locked(sources: Mapping[str, Source], project: Project) -> GetPlan:
    """The plan of ``get --locked``: every pinned item whose folder is missing, from its pinned release
    (``sources``: release → source), checked against the pinned index digest, version and tree."""
    plan = GetPlan()
    memo: dict[str, dict[str, dict[str, bytes] | None]] = {}
    for key, entry in sorted(project.entries.items()):
        folder = project.folder / entry["path"]
        if folder.is_dir():
            continue
        kind, _, ident = key.partition("/")
        source = sources[entry["release"]]
        if f"sha256:{source.index_sha256}" != entry["index"]:
            raise DigestRefused(
                f"the index of release {entry['release']} has SHA-256 {source.index_sha256}, the lock pins "
                f"{entry['index']}; nothing was written"
            )
        row = source.row(kind, ident)
        if row is None or row.get("version") != entry["version"] or pinned_tree(row) != entry["tree"]:
            raise DigestRefused(
                f"release {entry['release']} does not hold {key} {entry['version']} with the pinned tree"
            )
        _licence_check(row)
        files = item_payload(source, row, memo.setdefault(entry["release"], {}))
        for name, size, sha in row_files(row):
            if kind == "board" and name == BOARD_LOCK:
                continue
            plan.writes.append(
                Write(
                    project.rel(f"{entry['path']}/{name}"),
                    ITEM_KIND,
                    None if files is None else files[name],
                    size,
                    sha,
                )
            )
        plan.items.append(
            _result_row(
                row,
                required_by=[],
                path=project.rel(entry["path"]),
                source=source,
                action="restored",
                before=entry["version"],
            )
        )
    if not (project.folder / ATTRIBUTION).is_file() and project.entries:
        infos = [_disk_info(project, key, entry) for key, entry in sorted(project.entries.items())]
        for row in plan.items:
            key = item_key(str(row["kind"]), str(row["id"]))
            found = sources[str(row["release"])].row(str(row["kind"]), str(row["id"]))
            if found is not None:
                infos = [
                    _row_info(found, project.entries[key]["path"]) if i["key"] == key else i for i in infos
                ]
        plan.writes.append(write_of(project.rel(ATTRIBUTION), ATTRIBUTION_KIND, attribution_text(infos)))
    plan.lock_entries = dict(project.entries)
    return plan


def status_rows(project: Project, newest: Source | None) -> tuple[list[dict[str, Any]], list[Issue]]:
    """Per pinned item: ``present``, ``modified`` and ``newer`` (a higher version in ``newest``)."""
    script = project.rel(project.lock_file.with_suffix(".py").name)
    rows: list[dict[str, Any]] = []
    issues: list[Issue] = []
    for key, entry in sorted(project.entries.items()):
        kind, _, ident = key.partition("/")
        folder = project.folder / entry["path"]
        present = folder.is_dir()
        modified = present and _modified(project, key, entry, kind)
        newer: str | None = None
        if newest is not None:
            row = newest.row(kind, ident)
            if row is not None and version_key(str(row["version"])) > version_key(entry["version"]):
                newer = str(row["version"])
        rows.append(
            {
                "kind": kind,
                "id": ident,
                "version": entry["version"],
                "release": entry["release"],
                "spdx": entry["spdx"],
                "path": project.rel(entry["path"]),
                "present": present,
                "modified": modified,
                "newer": newer,
            }
        )
        if not present:
            issues.append(
                issue(
                    "library.item-missing",
                    f"{key} is pinned by the lock but {project.rel(entry['path'])} is missing",
                    where=key,
                    hint=f"fenolite get --locked {script} --dry-run",
                )
            )
    return rows, issues


def list_rows(
    source: Source,
    *,
    kind: str | None = None,
    text: str | None = None,
    licence: str | None = None,
) -> list[dict[str, Any]]:
    """The rows of ``--list`` and ``--search``: kind, id, version, title, SPDX, family, authors and gallery
    page, sorted by kind and id. ``text`` matches id, title, summary and tags (case-folded); ``licence`` is
    an SPDX id or a family name."""
    order = {k: n for n, k in enumerate(KINDS)}
    needle = text.casefold() if text else None
    found: list[dict[str, Any]] = []
    for row in source.rows():
        if kind is not None and row.get("kind") != kind:
            continue
        if licence is not None and licence.casefold() not in (
            str(row.get("spdx")).casefold(),
            str(row.get("family")).casefold(),
        ):
            continue
        if needle is not None:
            hay = " ".join(
                [
                    str(row.get("id")),
                    str(row.get("title")),
                    str(row.get("summary")),
                    *cast(list[str], row.get("tags") or []),
                ]
            ).casefold()
            if needle not in hay:
                continue
        found.append(
            {
                key: row.get(key)
                for key in ("kind", "id", "version", "title", "spdx", "family", "authors", "gallery")
            }
        )
    return sorted(found, key=lambda r: (order.get(str(r["kind"]), len(KINDS)), str(r["id"])))


__all__ = [
    "ATTRIBUTION",
    "ATTRIBUTION_KIND",
    "BOARD_LOCK",
    "CACHE_KIND",
    "FOLDERS",
    "ITEM_KIND",
    "LOCK_KIND",
    "DigestRefused",
    "GetPlan",
    "GetRefused",
    "LicenceRefused",
    "MalformedRelease",
    "ModifiedRefused",
    "Project",
    "Source",
    "UsageRefused",
    "Write",
    "attribution_text",
    "closure",
    "design_name",
    "item_payload",
    "licences_of",
    "list_rows",
    "local_tree",
    "missing_acceptance",
    "pinned_tree",
    "plan_get",
    "plan_locked",
    "plan_remove",
    "read_project_lock",
    "status_rows",
    "write_of",
]
