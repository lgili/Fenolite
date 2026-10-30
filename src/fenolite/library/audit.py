# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library audit ROOT``: the rules of a ``fenolite-library`` checkout (change c0279,
``docs/library-repo.md``, "Audit").

The audit walks ``<kind folder>/<family>/<id path>/`` for every kind, reads each ``item.json`` and
``PROVENANCE.json``, and reports one ``library.*`` issue per broken rule: layout and family, manifest and
provenance schemas, licence lists, licence text and notice, ids, files and dependencies; with a base tree,
the version rules. It reads files and writes nothing. ``scan`` is shared with ``library release``.
"""

from __future__ import annotations

import io
import subprocess
import tarfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from fenolite.core.errors import Issue
from fenolite.library.codes import issue
from fenolite.library.items import (
    ALWAYS_ALLOWED,
    EXECUTING,
    FOLDERS,
    ITEM_FILE,
    KIND_OF_FOLDER,
    LICENSE_FILE,
    NOTICE_FILE,
    PROVENANCE_FILE,
    Item,
    ItemError,
    folder_files,
    id_path,
    load_json,
    read_item,
    tree_digest,
    version_key,
)
from fenolite.library.licences import Licences, for_root, normalised_digest
from fenolite.library.proof import FAIL, derive, recorded_result
from fenolite.library.provenance import provenance_problems, upstream_host, vendor_bundled

README = "README.md"
README_STATEMENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("each directory keeps its upstream licence", ("upstream licence", "upstream license")),
    ("the repository's own licence does not cover the items", ("does not cover",)),
    ("items are test and benchmark inputs", ("benchmark",)),
    ("no item is used to train a machine-learning model", ("machine-learning", "machine learning")),
)
"""The statements the library's README makes (decision 13), each with the words that show it."""


@dataclass(frozen=True)
class Found:
    """One item folder of a checkout: where it is, its kind and family folders, its manifest and provenance
    (``None`` when unreadable) and its files."""

    path: str
    kind: str
    family: str
    item: Item | None
    provenance: Mapping[str, Any] | None
    files: Mapping[str, bytes]
    problems: tuple[str, ...] = ()

    @property
    def tree(self) -> str:
        return tree_digest(self.files)


@dataclass(frozen=True)
class AuditReport:
    """The items found and the issues of the audit, in the order of the folders."""

    items: tuple[Found, ...]
    issues: tuple[Issue, ...]
    rows: tuple[dict[str, object], ...] = field(default=())


def _item_folders(root: Path) -> list[tuple[str, str, Path]]:
    """``(kind, family, folder)`` of every folder holding ``item.json`` below a kind folder."""
    found: list[tuple[str, str, Path]] = []
    for folder_name, kind in sorted(KIND_OF_FOLDER.items()):
        top = root / folder_name
        if not top.is_dir():
            continue
        for marker in sorted(top.rglob(ITEM_FILE)):
            folder = marker.parent
            parts = folder.relative_to(top).parts
            family = parts[0] if len(parts) > 1 else ""
            found.append((kind, family, folder))
    return found


def read_found(root: Path, kind: str, family: str, folder: Path) -> Found:
    path = folder.relative_to(root).as_posix()
    problems: list[str] = []
    try:
        files = folder_files(folder)
    except (ItemError, OSError) as exc:
        return Found(path, kind, family, None, None, {}, (str(exc),))
    item: Item | None = None
    provenance: Mapping[str, Any] | None = None
    try:
        item = read_item(files[ITEM_FILE], f"{path}/{ITEM_FILE}")
    except ItemError as exc:
        problems.append(str(exc))
    if PROVENANCE_FILE in files:
        try:
            provenance = load_json(files[PROVENANCE_FILE], f"{path}/{PROVENANCE_FILE}")
        except ItemError as exc:
            problems.append(str(exc))
    else:
        problems.append(f"{path}: {PROVENANCE_FILE} is missing")
    return Found(path, kind, family, item, provenance, files, tuple(problems))


def scan(root: Path) -> list[Found]:
    """Every item folder of the checkout at ``root``."""
    return [read_found(root, kind, family, folder) for kind, family, folder in _item_folders(root)]


def _readme_issues(root: Path) -> list[Issue]:
    path = root / README
    if not path.is_file():
        return [
            issue(
                "library.provenance-invalid",
                "README.md is missing; it states the use and licence rules",
                where=README,
            )
        ]
    text = " ".join(path.read_text(encoding="utf-8").lower().split())
    return [
        issue(
            "library.provenance-invalid",
            f"README.md does not state that {statement}",
            where=README,
            hint="write the use statement of docs/library-repo.md into README.md",
        )
        for statement, words in README_STATEMENTS
        if not any(word in text for word in words)
    ]


def _licence_issues(found: Found, item: Item, licences: Licences) -> list[Issue]:
    issues: list[Issue] = []
    where = found.path
    reason = licences.deny_reason(item.spdx)
    record = found.provenance or {}
    if reason is not None:
        issues.append(
            issue(
                "library.licence-denied",
                f"{where}: the licence {item.spdx!r} is refused ({reason})",
                where=where,
                hint="only ids of the allow-list in licences.toml enter the library",
            )
        )
    host = upstream_host(record)
    if host and licences.host_denied(host):
        issues.append(
            issue(
                "library.licence-denied",
                f"{where}: the upstream {host} is a platform-restricted origin (platform-restricted)",
                where=where,
            )
        )
    if vendor_bundled(record):
        issues.append(
            issue(
                "library.licence-denied",
                f"{where}: an example bundled with commercial CAD software is refused (vendor-bundled)",
                where=where,
            )
        )
    if reason is None:
        family = licences.family_of(item.spdx)
        if family is not None and family.name != found.family:
            issues.append(
                issue(
                    "library.family-mismatch",
                    f"{where}: {item.spdx} belongs in the family {family.name}, "
                    f"not {found.family or '(none)'}",
                    where=where,
                    hint=f"move the item to {FOLDERS[item.kind]}/{family.name}/",
                )
            )
    text = found.files.get(LICENSE_FILE)
    if text is None:
        issues.append(issue("library.licence-text", f"{where}: LICENSE is missing", where=where))
    else:
        digest = normalised_digest(text)
        known = licences.texts.get(licences.canonical(item.spdx), ())
        if digest not in known and not isinstance(record.get("licence_review"), dict):
            issues.append(
                issue(
                    "library.licence-text",
                    f"{where}: LICENSE (normalised SHA-256 {digest}) is no text listed for {item.spdx}",
                    where=where,
                    hint="use the listed text, or record licence_review approved by a CODEOWNER",
                )
            )
        recorded = record.get("licence_text_sha256")
        if isinstance(recorded, str) and recorded != digest:
            issues.append(
                issue(
                    "library.provenance-invalid",
                    f"{where}: licence_text_sha256 says {recorded} and LICENSE gives {digest}",
                    where=where,
                )
            )
    notice = found.files.get(NOTICE_FILE)
    first = notice.decode("utf-8", errors="replace").lstrip() if notice is not None else ""
    wanted = record.get("modification_notice")
    if notice is None or not isinstance(wanted, str) or not first.startswith(wanted):
        said = "is missing" if notice is None else "does not start with the dated modification notice"
        issues.append(
            issue(
                "library.notice-missing",
                f"{where}: NOTICE {said} of PROVENANCE.json",
                where=where,
                hint="head NOTICE with modification_notice, then the upstream notices verbatim",
            )
        )
    return issues


def _item_issues(found: Found, licences: Licences) -> list[Issue]:
    where = found.path
    issues = [issue("library.provenance-invalid", text, where=where) for text in found.problems]
    item = found.item
    if item is None:
        return issues
    if item.kind != found.kind:
        issues.append(
            issue(
                "library.provenance-invalid",
                f"{where}: item.json says the kind {item.kind} in the folder {FOLDERS[found.kind]}",
                where=where,
            )
        )
    expected = f"{FOLDERS[item.kind]}/{found.family}/{id_path(item.id)}"
    if where != expected:
        issues.append(
            issue(
                "library.provenance-invalid",
                f"{where}: the folder of {item.kind} {item.id} is {expected}",
                where=where,
            )
        )
    if (item.kind in EXECUTING) != item.executes:
        said = (
            "block and board items execute"
            if item.kind in EXECUTING
            else f"a {item.kind} item does not execute"
        )
        issues.append(
            issue(
                "library.provenance-invalid",
                f"{where}: executes is {str(item.executes).lower()}; {said}",
                where=where,
            )
        )
    listed = set(item.files)
    for name in sorted(found.files):
        if name not in listed and name not in ALWAYS_ALLOWED:
            issues.append(
                issue(
                    "library.item-extra-file",
                    f"{where}: {name} is not listed in files",
                    where=f"{where}/{name}",
                    hint="list it in item.json files, or remove it",
                )
            )
    for name in item.files:
        if name not in found.files:
            issues.append(
                issue(
                    "library.provenance-invalid",
                    f"{where}: files lists {name}, which is missing",
                    where=where,
                )
            )
    if found.provenance is not None:
        issues += [
            issue("library.provenance-invalid", f"{where}: {text}", where=where)
            for text in provenance_problems(found.provenance, item)
        ]
    issues += _licence_issues(found, item, licences)
    fidelity = (found.provenance or {}).get("fidelity")
    if item.kind == "board" and isinstance(fidelity, dict):
        levels = cast(dict[str, Any], fidelity).get("proof")
        if isinstance(levels, dict) and recorded_result(cast(dict[str, Any], fidelity)) == FAIL:
            gate = derive(
                {
                    str(k): str(v)
                    for k, v in cast(dict[str, Any], cast(dict[str, Any], levels).get("levels") or {}).items()
                },
                {
                    str(k): str(v)
                    for k, v in cast(
                        dict[str, Any], cast(dict[str, Any], levels).get("skipped") or {}
                    ).items()
                },
                f"{where}: ",
            )
            issues += [i for i in gate.issues]
    return issues


def _depends_issues(items: Sequence[Found]) -> list[Issue]:
    known = {(f.item.kind, f.item.id): f for f in items if f.item is not None}
    issues: list[Issue] = []
    graph: dict[str, list[str]] = {}
    for found in items:
        item = found.item
        if item is None:
            continue
        graph[item.key] = [d.key for d in item.depends]
        for depend in item.depends:
            target = known.get((depend.kind, depend.id))
            if target is None or target.item is None or target.item.version != depend.version:
                have = (
                    "is not in the library"
                    if target is None or target.item is None
                    else f"is at {target.item.version}"
                )
                issues.append(
                    issue(
                        "library.provenance-invalid",
                        f"{found.path}: depends on {depend.key} {depend.version}, which {have}",
                        where=found.path,
                    )
                )
    state: dict[str, int] = {}
    paths = {f.item.key: f.path for f in items if f.item is not None}

    def visit(key: str, trail: list[str]) -> None:
        state[key] = 1
        for nxt in graph.get(key, []):
            if state.get(nxt) == 1:
                cycle = [*trail[trail.index(nxt) :], nxt] if nxt in trail else [key, nxt]
                issues.append(
                    issue(
                        "library.provenance-invalid",
                        f"a depends cycle: {' -> '.join(cycle)}",
                        where=paths.get(key, key),
                    )
                )
            elif nxt in graph and state.get(nxt) is None:
                visit(nxt, [*trail, nxt])
        state[key] = 2

    for key in sorted(graph):
        if state.get(key) is None:
            visit(key, [key])
    return issues


def _duplicates(items: Sequence[Found]) -> list[Issue]:
    seen: dict[tuple[str, str], str] = {}
    issues: list[Issue] = []
    for found in items:
        if found.item is None:
            continue
        key = (found.item.kind, found.item.id)
        if key in seen:
            issues.append(
                issue(
                    "library.duplicate-id",
                    f"{found.item.kind} {found.item.id} is in two folders: {seen[key]} and {found.path}",
                    where=found.path,
                )
            )
        else:
            seen[key] = found.path
    return issues


def base_items(root: Path, base: str) -> list[Found]:
    """The items of the base tree: a folder, or a git ref of the checkout at ``root``."""
    folder = Path(base)
    if folder.is_dir():
        return scan(folder)
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "archive", "--format=tar", base],
            capture_output=True,
            check=True,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"--base {base!r} is neither a folder nor a git ref of {root.name}: {exc}") from exc
    import tempfile

    with tempfile.TemporaryDirectory(prefix="fenolite-base-") as temp:
        with tarfile.open(fileobj=io.BytesIO(done.stdout)) as archive:
            archive.extractall(temp, filter="data")
        return scan(Path(temp))


def _version_issues(items: Sequence[Found], base: Sequence[Found]) -> list[Issue]:
    before = {(f.item.kind, f.item.id): f for f in base if f.item is not None}
    issues: list[Issue] = []
    for found in items:
        item = found.item
        if item is None:
            continue
        old = before.get((item.kind, item.id))
        if old is None or old.item is None or old.tree == found.tree:
            continue
        try:
            newer = version_key(item.version) > version_key(old.item.version)
        except ValueError:
            continue
        if not newer:
            issues.append(
                issue(
                    "library.version-rule",
                    f"{found.path}: the item changed but its version {item.version} "
                    f"is not above {old.item.version}",
                    where=found.path,
                    hint="raise MINOR for a regeneration, MAJOR for a new upstream commit",
                )
            )
    return issues


def audit(root: Path, *, item: str | None = None, base: str | None = None) -> AuditReport:
    """The audit of the checkout at ``root``; ``item`` limits the item rules to one folder (relative to
    ``root``); ``base`` adds the version rules against a base tree."""
    licences = for_root(root)
    found = scan(root)
    issues: list[Issue] = [] if item is not None else _readme_issues(root)
    chosen = [f for f in found if item is None or f.path == item.strip("/")]
    if item is not None and not chosen:
        raise ValueError(f"no item folder {item} below {root.name}")
    for one in chosen:
        issues += _item_issues(one, licences)
    issues += _duplicates(found)
    issues += [i for i in _depends_issues(found) if item is None or i.where == item.strip("/")]
    if base is not None:
        issues += _version_issues(chosen, base_items(root, base))
    rows: tuple[dict[str, object], ...] = tuple(
        {
            "path": f.path,
            "kind": f.kind,
            "family": f.family,
            "id": f.item.id if f.item else None,
            "version": f.item.version if f.item else None,
            "spdx": f.item.spdx if f.item else None,
            "tree": f.tree,
            "errors": sum(1 for i in issues if i.where == f.path or i.where.startswith(f.path + "/")),
        }
        for f in chosen
    )
    return AuditReport(tuple(found), tuple(issues), rows)


__all__ = ["README_STATEMENTS", "AuditReport", "Found", "audit", "base_items", "read_found", "scan"]
