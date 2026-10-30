# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library release ROOT --version V``: the release assets of a ``fenolite-library`` checkout
(change c0279, ``docs/library-repo.md``, "Releases").

The assets are ``index.json`` (schema ``fenolite.library-index.v0``), one shard archive per kind and family
(``devices-cc0.tar.gz``) for symbols, footprints, devices and blocks, one archive per board
(``board-<source>-<name>-<version>.tar.gz``), and ``SHA256SUMS``. Archives are byte-reproducible: one
top-level folder, members sorted by path, mtime 0, uid and gid 0, mode 0644, no link, gzip with mtime 0
and no name. :func:`archive_members` is the reverse used by ``fenolite get``.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import subprocess
import tarfile
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from fenolite.library.audit import Found
from fenolite.library.items import FOLDERS, VERSION, canonical_json, safe_relative
from fenolite.library.licences import Licences
from fenolite.library.proof import recorded_result

INDEX_SCHEMA = "fenolite.library-index.v0"
INDEX = "index.json"
SUMS = "SHA256SUMS"
LIBRARY_TOML = "library.toml"
SHARDED: tuple[str, ...] = ("symbol", "footprint", "device", "block")
MAX_MEMBER = 256 * 1024 * 1024
"""The largest member an archive may hold when it is read back."""


@dataclass(frozen=True)
class Release:
    """The assets of one release (name → bytes, ``index.json`` and ``SHA256SUMS`` included) and its
    index."""

    assets: Mapping[str, bytes]
    index: Mapping[str, Any]


def library_meta(root: Path) -> dict[str, Any]:
    """``library.toml`` of the checkout (``name``, ``version``, ``requires``), or defaults."""
    path = root / LIBRARY_TOML
    if not path.is_file():
        return {"name": "fenolite-library", "requires": {}}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return {
        "name": str(data.get("name", "fenolite-library")),
        "version": data.get("version"),
        "requires": dict(cast(Mapping[str, Any], data.get("requires", {}))),
    }


def head_commit(root: Path) -> str | None:
    """The commit checked out at ``root`` when it is a git work tree, else ``None``."""
    if not (root / ".git").exists():
        return None
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            timeout=60,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() or None


def archive_name(found: Found) -> str:
    item = found.item
    assert item is not None
    if item.kind == "board":
        source, name = item.id.split("/", 1)
        return f"board-{source}-{name}-{item.version}.tar.gz"
    return f"{FOLDERS[item.kind]}-{found.family}.tar.gz"


def build_archive(top: str, files: Mapping[str, bytes]) -> bytes:
    """A deterministic ``.tar.gz`` of ``files`` (relative POSIX path → bytes) under the folder ``top``."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(files, key=lambda p: p.encode("utf-8")):
            data = files[path]
            info = tarfile.TarInfo(f"{top}/{path}")
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    packed = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=packed, mtime=0, compresslevel=9) as stream:
        stream.write(raw.getvalue())
    return packed.getvalue()


def archive_members(data: bytes, *, name: str) -> dict[str, bytes]:
    """The files of an archive, relative to its top folder; ``ValueError`` for a link, a special member,
    an unsafe path or a member over ``MAX_MEMBER`` bytes. Nothing is written to disk."""
    found: dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member in tar:
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError(f"{name}: {member.name} is not a regular file")
                top, _, rest = member.name.partition("/")
                if not top or not safe_relative(rest):
                    raise ValueError(f"{name}: unsafe member path {member.name!r}")
                if member.size > MAX_MEMBER:
                    raise ValueError(f"{name}: {member.name} is larger than {MAX_MEMBER} bytes")
                handle = tar.extractfile(member)
                assert handle is not None
                found[rest] = handle.read()
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise ValueError(f"{name}: not a readable .tar.gz archive: {exc}") from exc
    return found


def _upstream(record: Mapping[str, Any]) -> dict[str, Any] | None:
    upstream = record.get("upstream")
    if not isinstance(upstream, dict):
        return None
    table = cast(dict[str, Any], upstream)
    return {"url": table.get("url"), "commit": table.get("commit")}


def gallery_page(kind: str, ident: str) -> str:
    return f"{FOLDERS[kind]}/{ident.replace(':', '/')}/index.html"


def item_row(found: Found, licences: Licences) -> dict[str, Any]:
    """The index row of one item (without ``archive``)."""
    item = found.item
    assert item is not None
    record = found.provenance or {}
    family = licences.family_of(item.spdx)
    trademarks = record.get("trademarks")
    restricted = isinstance(trademarks, dict) and cast(dict[str, Any], trademarks).get("restricted") is True
    fidelity = record.get("fidelity")
    return {
        "kind": item.kind,
        "id": item.id,
        "version": item.version,
        "title": item.title,
        "summary": item.summary,
        "spdx": item.spdx,
        "family": found.family,
        "reciprocal": bool(family and family.reciprocal),
        "tags": list(item.tags),
        "authors": list(cast(list[str], record.get("authors") or [])),
        "upstream": _upstream(record),
        "notice": str(record.get("modification_notice", "")),
        "path": found.path,
        "tree": found.tree,
        "bytes": sum(len(data) for data in found.files.values()),
        "files": [
            {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for path, data in sorted(found.files.items(), key=lambda kv: kv[0].encode("utf-8"))
        ],
        "depends": [depend.as_json() for depend in item.depends],
        "executes": item.executes,
        "evidence": str(record.get("evidence", "UNVERIFIED")),
        "proof": recorded_result(cast(Mapping[str, Any], fidelity)) if isinstance(fidelity, dict) else None,
        "gallery": None if restricted else gallery_page(item.kind, item.id),
    }


def build_release(
    root: Path, items: Sequence[Found], version: str, licences: Licences, *, commit: str | None = None
) -> Release:
    """The assets of release ``version`` of the checkout at ``root`` whose audited items are ``items``."""
    if not VERSION.fullmatch(version):
        raise ValueError(f"--version {version!r} is not a semantic version")
    meta = library_meta(root)
    groups: dict[str, dict[str, bytes]] = {}
    rows: list[dict[str, Any]] = []
    for found in sorted(items, key=lambda f: f.path):
        if found.item is None:
            continue
        name = archive_name(found)
        members = groups.setdefault(name, {})
        for path, data in found.files.items():
            members[f"{found.path}/{path}"] = data
        rows.append({**item_row(found, licences), "archive": name})
    assets: dict[str, bytes] = {}
    for name, members in sorted(groups.items()):
        assets[name] = build_archive(name.removesuffix(".tar.gz"), members)
    order = {kind: n for n, kind in enumerate(("symbol", "footprint", "device", "block", "board"))}
    index: dict[str, Any] = {
        "schema": INDEX_SCHEMA,
        "name": meta["name"],
        "version": version,
        "commit": commit if commit is not None else head_commit(root),
        "requires": meta["requires"],
        "items": sorted(rows, key=lambda r: (order[r["kind"]], r["id"])),
        "archives": [
            {"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(assets.items())
        ],
    }
    assets[INDEX] = canonical_json(index)
    sums = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(assets.items()))
    assets[SUMS] = sums.encode("ascii")
    return Release(dict(sorted(assets.items())), index)


__all__ = [
    "INDEX",
    "INDEX_SCHEMA",
    "SHARDED",
    "SUMS",
    "Release",
    "archive_members",
    "archive_name",
    "build_archive",
    "build_release",
    "gallery_page",
    "head_commit",
    "item_row",
    "library_meta",
]
