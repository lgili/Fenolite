# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite get KIND ID``: copy a ``fenolite-library`` item and its dependencies into the project, with
their LICENSE, NOTICE and PROVENANCE.json, regenerate ``fenolite_library/ATTRIBUTION.md`` and pin them in
the design lock (capability cli-contract, "Get command" and following; change c0279; ADR-0008;
``docs/library-repo.md``).

The other forms: ``--list`` and ``--search TEXT`` read a cached index; ``--status`` reports the pins;
``--locked SCRIPT`` restores missing pinned folders; ``--remove KIND ID`` plans a removal; ``--refresh``
caches one release index. A release comes from ``--from SRC`` (a release folder, a library checkout or a
``file://`` git URL), from the offline cache, or from the network: one ``https`` request per missing asset,
only under ``--confirm`` and never with ``--offline``. Every index, archive and item is checked against its
pinned digest before anything is planned. ``get`` never imports, runs or builds a payload.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import subprocess
import tempfile
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any, cast

from fenolite.cli import fetch
from fenolite.cli._examples import EXAMPLE_LIBRARY
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.evidence import Evidence, Level
from fenolite.library import cache as library_cache
from fenolite.library.audit import audit
from fenolite.library.get import (
    ATTRIBUTION,
    CACHE_KIND,
    GetPlan,
    Project,
    Source,
    Write,
    design_name,
    licences_of,
    list_rows,
    missing_acceptance,
    plan_get,
    plan_locked,
    plan_remove,
    read_project_lock,
    status_rows,
    write_of,
)
from fenolite.library.items import KINDS, SHA256, VERSION, id_problem, load_json, version_key
from fenolite.library.licences import for_root
from fenolite.library.release import INDEX, build_release, library_meta

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-LIBRARY-GET",))
RELEASES = "library.toml"
MAX_INDEX = 64 * 1024 * 1024
"""The most bytes read for an index whose size no table row gives."""
HELP = (
    "copy a fenolite-library item and its dependencies into the project with their licence files, "
    "and pin them in the design lock"
)


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/library-repo.md and docs/cli-contract.md, 'get'."
    parser.add_argument("kind", nargs="?", metavar="KIND", help=f"the item kind: {', '.join(KINDS)}")
    parser.add_argument(
        "id", nargs="?", metavar="ID", help="the item id: <Namespace>:<name>, or <source>/<name> for a board"
    )
    parser.add_argument(
        "--version", dest="item_version", metavar="V", help="the item version (default: the release's)"
    )
    parser.add_argument("--release", metavar="R", help="the library release to read")
    parser.add_argument(
        "--script", metavar="FILE", help="the design script whose folder receives items (default design.py)"
    )
    parser.add_argument(
        "--into", metavar="DIR", help="board: the folder to create (default ./<name>), missing or empty"
    )
    parser.add_argument(
        "--from",
        dest="from_",
        metavar="SRC",
        help="a release folder, a fenolite-library checkout, or a file:// git URL (#ref)",
    )
    parser.add_argument(
        "--offline", action="store_true", help="open no connection; use the cache or --from only"
    )
    parser.add_argument(
        "--index-sha256", metavar="HEX", help="the SHA-256 of a release index this version does not list"
    )
    parser.add_argument(
        "--accept-licence",
        action="append",
        default=[],
        metavar="SPDX[,SPDX...]",
        help="accept these licences of the planned items (needed for any id but CC0-1.0)",
    )
    forms = parser.add_argument_group("other forms (exclusive with KIND ID)")
    forms.add_argument("--list", action="store_true", help="list the items of a cached index")
    forms.add_argument(
        "--search", metavar="TEXT", help="search ids, titles, summaries and tags of a cached index"
    )
    forms.add_argument(
        "--status", action="store_true", help="report the pinned items: present, modified, newer"
    )
    forms.add_argument("--locked", metavar="SCRIPT", help="restore every pinned item whose folder is missing")
    forms.add_argument(
        "--remove", action="store_true", help="with KIND ID: remove a vendored item and its pin"
    )
    forms.add_argument("--refresh", action="store_true", help="download one release index into the cache")
    forms.add_argument("--kind", dest="filter_kind", metavar="K", help="--list, --search: only this kind")
    forms.add_argument("--licence", metavar="ID|FAMILY", help="--list, --search: only this SPDX id or family")
    forms.add_argument("--frozen", action="store_true", help="refused: get changes the lock (exit 2)")


# -- the table of known releases


@dataclass(frozen=True)
class KnownRelease:
    version: str
    index_bytes: int
    index_sha256: str


@cache
def _table() -> tuple[str, tuple[KnownRelease, ...]]:
    text = resources.files("fenolite.cli").joinpath("data", RELEASES).read_text(encoding="utf-8")
    data = tomllib.loads(text)
    rows = tuple(
        KnownRelease(str(r["version"]), int(r["index_bytes"]), str(r["index_sha256"]))
        for r in cast(list[dict[str, Any]], data.get("release", []))
    )
    return str(data["url_template"]), tuple(sorted(rows, key=lambda r: version_key(r.version)))


def known_releases() -> tuple[KnownRelease, ...]:
    return _table()[1]


def asset_url(version: str, asset: str) -> str:
    return _table()[0].format(version=version, asset=asset)


# -- sources


def _never() -> bytes:
    raise RuntimeError("a planned download runs only under --confirm")


def _deferred(write: Write) -> PlannedWrite:
    if write.data is not None:
        return PlannedWrite(write.path, write.data, write.kind)
    return PlannedWrite(write.path, b"", write.kind, source=_never, size=write.size, sha256=write.sha256)


def _unstaged(writes: list[PlannedWrite]) -> list[PlannedWrite]:
    """``writes`` with the first one deferred, so that the plan is not staged and ``--confirm --plan`` runs
    the command again (its licence check and its removals)."""
    if not writes or writes[0].deferred:
        return writes
    first = writes[0]
    data = first.data
    return [
        PlannedWrite(
            first.path,
            b"",
            first.kind,
            source=lambda: data,
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        ),
        *writes[1:],
    ]


@dataclass
class Fetching:
    """What a run may do to get assets: ``confirm`` allows requests unless ``offline``; the cache writes
    and downloads it planned."""

    confirm: bool
    offline: bool
    writes: list[Write] = field(default_factory=lambda: [])
    downloads: list[dict[str, Any]] = field(default_factory=lambda: [])
    stamps: dict[str, dict[str, str]] = field(default_factory=lambda: {})

    def cache(
        self, version: str, asset: str, path: Path, data: bytes | None, size: int, sha: str, origin: str
    ) -> None:
        self.writes.append(Write(str(path), CACHE_KIND, data, size, sha))
        self.stamps.setdefault(version, dict(library_cache.read_stamp(version)))[asset] = sha
        self.downloads.append(
            {
                "asset": asset,
                "release": version,
                "bytes": size,
                "sha256": sha,
                "origin": origin,
                "path": str(path),
            }
        )

    def stamp_writes(self) -> list[Write]:
        return [
            write_of(str(library_cache.stamp_path(v)), CACHE_KIND, library_cache.stamp_text(v, d))
            for v, d in sorted(self.stamps.items())
        ]


def _download(url: str, size: int) -> bytes:
    try:
        return fetch.download_url(url, size)
    except (OSError, ValueError, http.client.HTTPException) as exc:
        raise CliError("FEN-6003", f"download of {url} failed: {exc}", where=url) from exc


def _parse_index(data: bytes, where: str) -> dict[str, Any]:
    try:
        index = load_json(data, where)
    except ValueError as exc:
        raise CliError("FEN-3004", str(exc), where=where) from exc
    if index.get("schema") != "fenolite.library-index.v0" or not isinstance(index.get("items"), list):
        raise CliError("FEN-3004", f"{where} is not a fenolite.library-index.v0 index", where=where)
    return index


def _check_index(data: bytes, expected: str | None, where: str) -> None:
    found = hashlib.sha256(data).hexdigest()
    if expected is not None and found != expected:
        raise CliError(
            "FEN-3006",
            f"{where}: expected SHA-256 {expected}, found {found}; nothing was written",
            where=where,
            hint="check --index-sha256 against the release page, or get the release again",
        )


def _expected_index(version: str, given: str | None, pinned: str | None) -> tuple[str | None, int | None]:
    """The digest an index must have (``--index-sha256``, a lock pin, or the table) and its size if known."""
    row = next((r for r in known_releases() if r.version == version), None)
    digest = (
        given or (pinned.removeprefix("sha256:") if pinned else None) or (row.index_sha256 if row else None)
    )
    if given and row and given != row.index_sha256:
        raise CliError(
            "FEN-3006",
            f"--index-sha256 differs from the digest this version lists for release {version}",
            where="--index-sha256",
        )
    size = row.index_bytes if row and row.index_sha256 == digest else None
    return digest, size


def _git_checkout(url: str, into: Path) -> Path:
    address, _, ref = url.partition("#")
    if not address.startswith("file://"):
        raise CliError(
            "FEN-2001",
            f"--from {address}: only file:// git URLs are cloned",
            hint="clone the repository yourself and pass its folder to --from",
        )
    target = into / "checkout"
    try:
        subprocess.run(
            ["git", "clone", "-q", "--no-hardlinks", address, str(target)],
            check=True,
            capture_output=True,
            timeout=600,
        )
        if ref:
            subprocess.run(
                ["git", "-C", str(target), "checkout", "-q", ref],
                check=True,
                capture_output=True,
                timeout=600,
            )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CliError(
            "FEN-3001", f"--from {url}: git could not check it out ({exc})", where="--from"
        ) from exc
    return target


def _from_source(args: argparse.Namespace, ctx: Context, fetching: Fetching, scratch: Path) -> Source:
    given = str(args.from_)
    folder = (
        _git_checkout(given, scratch)
        if "://" in given
        else Path(given)
        if Path(given).is_absolute()
        else ctx.cwd / given
    )
    if not folder.is_dir():
        raise CliError("FEN-3001", f"--from {given} is not a folder", where="--from")
    if (folder / INDEX).is_file():
        data = (folder / INDEX).read_bytes()
        index = _parse_index(data, f"{given}/{INDEX}")
        version = str(index.get("version"))
        if not VERSION.fullmatch(version):
            raise CliError(
                "FEN-3004", f"{given}/{INDEX}: version {version!r} is not semantic", where="--from"
            )
        if args.release and args.release != version:
            raise CliError(
                "FEN-2001", f"--from holds release {version}, not {args.release}", where="--release"
            )
        expected, _ = _expected_index(version, args.index_sha256, None)
        _check_index(data, expected, f"{given}/{INDEX}")
        cached = library_cache.read_verified(
            library_cache.index_path(version), hashlib.sha256(data).hexdigest()
        )
        if cached is None:
            fetching.cache(
                version,
                INDEX,
                library_cache.index_path(version),
                data,
                len(data),
                hashlib.sha256(data).hexdigest(),
                "from",
            )

        def asset(name: str) -> bytes | None:
            path = folder / name
            if not path.is_file():
                raise CliError("FEN-3001", f"--from {given} lacks the asset {name}", where=name)
            found = path.read_bytes()
            row = next(
                (
                    a
                    for a in cast(list[Mapping[str, Any]], index.get("archives", []))
                    if a.get("name") == name
                ),
                None,
            )
            target = library_cache.asset_path(version, name)
            if row is not None and hashlib.sha256(found).hexdigest() == row.get("sha256"):
                if library_cache.read_verified(target, str(row["sha256"]), int(row["bytes"])) is None:
                    fetching.cache(version, name, target, found, len(found), str(row["sha256"]), "from")
            return found

        return Source(version, index, data, "from", asset)
    report = audit(folder)
    errors = [i for i in report.issues if i.severity == "error" and i.where != "README.md"]
    if errors:
        raise CliError(
            "FEN-3004",
            f"--from {given}: the library checkout fails its audit ({errors[0].message})",
            where="--from",
            hint=f"run fenolite library audit {given} --json",
        )
    meta = library_meta(folder)
    version = str(meta.get("version") or "0.0.0")
    release = build_release(folder, report.items, version, for_root(folder))
    assets = release.assets
    return Source(version, release.index, assets[INDEX], "tree", lambda name: assets.get(name))


def _network_source(
    version: str, args: argparse.Namespace, fetching: Fetching, *, pinned: str | None = None
) -> Source | None:
    """The release ``version`` from the cache or the network; ``None`` when its index must be downloaded
    first and this run may not (a dry run: the download is then planned)."""
    expected, size = _expected_index(version, args.index_sha256, pinned)
    data = library_cache.read_verified(library_cache.index_path(version), expected)
    if data is None:
        if fetching.offline:
            raise CliError(
                "FEN-6006",
                f"the index of release {version} is not in the offline cache",
                where=version,
                hint="run the command without --offline, or name a release folder with --from DIR",
            )
        if expected is None:
            raise CliError(
                "FEN-2001",
                f"this version does not list release {version}: name its index digest",
                where="--release",
                hint="pass --index-sha256 HEX from the library's release page",
            )
        if not fetching.confirm:
            path = library_cache.index_path(version)
            fetching.downloads.append(
                {
                    "asset": INDEX,
                    "release": version,
                    "bytes": size,
                    "sha256": expected,
                    "origin": "network",
                    "path": str(path),
                    "url": asset_url(version, INDEX),
                }
            )
            if size is not None:
                fetching.cache(version, INDEX, path, None, size, expected, "network")
                fetching.downloads.pop()
            return None
        data = _download(asset_url(version, INDEX), size if size is not None else MAX_INDEX)
        if size is not None and len(data) != size:
            raise CliError(
                "FEN-3006",
                f"the index of release {version} has {len(data)} bytes, expected {size}",
                where=INDEX,
            )
        _check_index(data, expected, INDEX)
        fetching.cache(
            version, INDEX, library_cache.index_path(version), data, len(data), expected, "network"
        )
    index = _parse_index(data, f"{version}/{INDEX}")
    archives = {str(a.get("name")): a for a in cast(list[Mapping[str, Any]], index.get("archives", []))}

    def asset(name: str) -> bytes | None:
        row = archives.get(name)
        if row is None:
            return None
        sha, length = str(row["sha256"]), int(row["bytes"])
        target = library_cache.asset_path(version, name)
        found = library_cache.read_verified(target, sha, length)
        if found is not None:
            return found
        if fetching.offline:
            raise CliError(
                "FEN-6006",
                f"the asset {name} of release {version} is not in the offline cache",
                where=name,
                hint="run the command without --offline, or name a release folder with --from DIR",
            )
        if not fetching.confirm:
            fetching.cache(version, name, target, None, length, sha, "network")
            return None
        found = _download(asset_url(version, name), length)
        fetching.cache(version, name, target, found, length, sha, "network")
        return found

    return Source(version, index, data, "cache" if fetching.writes == [] else "network", asset)


def _newest_cached() -> str | None:
    found = library_cache.cached_versions()
    return found[-1] if found else None


def _release_for(args: argparse.Namespace) -> str:
    if args.release:
        if not VERSION.fullmatch(args.release):
            raise CliError(
                "FEN-2001", f"--release {args.release!r} is not a semantic version", where="--release"
            )
        return str(args.release)
    candidates = [r.version for r in known_releases()]
    newest = _newest_cached()
    if newest is not None:
        candidates.append(newest)
    if not candidates:
        raise CliError(
            "FEN-6006",
            "no library release is known or cached",
            where="--release",
            hint="fenolite get --refresh --release R --index-sha256 HEX --dry-run, or pass --from DIR",
        )
    return max(candidates, key=version_key)


def _cached_source(args: argparse.Namespace, ctx: Context, scratch: Path) -> Source:
    """The index of ``--list``, ``--search`` and ``--status``: ``--from``, or a cached one, never the
    network."""
    fetching = Fetching(confirm=False, offline=True)
    if args.from_:
        return _from_source(args, ctx, fetching, scratch)
    version = args.release or _newest_cached()
    if version is None:
        raise CliError(
            "FEN-6006",
            "no library index is in the cache",
            where="--list",
            hint="fenolite get --refresh --dry-run (then confirm), or pass --from DIR",
        )
    data = library_cache.read_verified(library_cache.index_path(version), None)
    if data is None:
        raise CliError(
            "FEN-6006",
            f"the index of release {version} is not in the cache",
            where="--release",
            hint="fenolite get --refresh --dry-run (then confirm), or pass --from DIR",
        )
    return Source(version, _parse_index(data, f"{version}/{INDEX}"), data, "cache", lambda name: None)


# -- the project


def _script_project(given: str | None, ctx: Context) -> tuple[Project, Path]:
    name = given or "design.py"
    script = Path(name) if Path(name).is_absolute() else ctx.cwd / name
    if not script.is_file():
        raise CliError(
            "FEN-2001",
            f"no design script {name}",
            where="--script",
            hint="name the design script with --script",
        )
    folder = script.parent.resolve()
    try:
        shown = folder.relative_to(ctx.cwd.resolve()).as_posix()
    except ValueError:
        shown = folder.as_posix()
    shown = "" if shown == "." else shown
    lock_file = script.with_suffix(".lock")
    try:
        lock = read_project_lock(lock_file, lock_file.name)
    except ValueError as exc:
        raise CliError("FEN-3004", str(exc), where=lock_file.name) from exc
    design = lock.design if lock is not None else design_name(script, script.stem)
    return Project(ctx.cwd, folder, shown, lock_file, lock, design), script


def _board_project(args: argparse.Namespace, ctx: Context, ident: str) -> Project:
    name = args.into or f"./{ident.split('/', 1)[1]}"
    folder = Path(name) if Path(name).is_absolute() else ctx.cwd / name
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        raise CliError("FEN-2001", f"--into {name} must be missing or empty", where="--into")
    shown = Path(name).as_posix().removeprefix("./").rstrip("/")
    return Project(ctx.cwd, folder, shown, folder / "design.lock", None, Path(name).name)


# -- the forms


def _accepted(args: argparse.Namespace) -> list[str]:
    return sorted(
        {part.strip() for given in args.accept_licence for part in given.split(",") if part.strip()}
    )


def _forms(args: argparse.Namespace) -> str:
    chosen = [name for name in ("list", "search", "status", "locked", "refresh") if getattr(args, name)]
    if args.remove:
        chosen.append("remove")
    if len(chosen) > 1:
        raise CliError("FEN-2001", f"--{chosen[0]} and --{chosen[1]} are exclusive", where=f"--{chosen[1]}")
    form = chosen[0] if chosen else "get"
    takes_item = form in ("get", "remove")
    if takes_item and (args.kind is None or args.id is None):
        raise CliError(
            "FEN-2001", "name the item: fenolite get KIND ID", hint=f"the kinds are {', '.join(KINDS)}"
        )
    if not takes_item and (args.kind is not None or args.id is not None):
        raise CliError("FEN-2001", f"--{form} takes no KIND ID", where="KIND")
    if takes_item:
        problem = id_problem(str(args.kind), args.id)
        if problem is not None:
            raise CliError("FEN-2001", problem, where="ID" if args.kind in KINDS else "KIND")
    if args.index_sha256 is not None and not SHA256.fullmatch(args.index_sha256):
        raise CliError("FEN-2001", "--index-sha256 is 64 lower-case hex digits", where="--index-sha256")
    return form


def _result(
    plan: GetPlan,
    source: Source | None,
    fetching: Fetching,
    project: Project,
    args: argparse.Namespace,
    ctx: Context,
    *,
    check_licences: bool,
) -> Result:
    accepted = _accepted(args)
    written = [item for item in plan.items if item.get("action") not in ("kept", "removed")]
    body: dict[str, Any] = {
        "release": source.version if source else None,
        "origin": source.origin if source else None,
        "index_sha256": source.index_sha256 if source else None,
        "items": plan.items,
        "licences": licences_of(written, accepted),
        "accepted": accepted,
        "removes": plan.removals,
        "lock": project.rel(project.lock_file.name),
        "attribution": project.rel(ATTRIBUTION),
        "downloads": fetching.downloads,
        "notes": plan.notes,
    }
    if plan.issues:
        return Result(result=body, issues=tuple(plan.issues), evidence=EVIDENCE)
    missing = missing_acceptance(written, accepted) if check_licences else []
    if missing and bool(getattr(args, "confirm", False)):
        raise CliError(
            "FEN-4003",
            f"the licences {', '.join(missing)} must be accepted by name; nothing was written",
            where="--accept-licence",
            hint=f"read result.licences, then confirm with --accept-licence {','.join(missing)}",
        )
    writes = [_deferred(w) for w in [*fetching.writes, *fetching.stamp_writes(), *plan.writes]]
    if missing or plan.removals:
        writes = _unstaged(writes)
    removals = list(plan.removals)

    def remove() -> None:
        for path in removals:
            target = ctx.cwd / path
            target.unlink(missing_ok=True)
            parent = target.parent
            while parent != project.folder and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent

    return Result(
        result=body,
        evidence=EVIDENCE,
        writes=tuple(writes),
        depends=depends_on(ctx.cwd, *(ctx.cwd / p for p in removals)),
        written=remove if removals else None,
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.frozen:
        raise CliError("FEN-2001", "get changes the lock; it takes no --frozen", where="--frozen")
    form = _forms(args)
    confirm = bool(getattr(args, "confirm", False))
    with tempfile.TemporaryDirectory(prefix="fenolite-get-") as temp:
        scratch = Path(temp)
        if form in ("list", "search"):
            source = _cached_source(args, ctx, scratch)
            if args.filter_kind is not None and args.filter_kind not in KINDS:
                raise CliError("FEN-2001", f"--kind is one of {', '.join(KINDS)}", where="--kind")
            rows = list_rows(source, kind=args.filter_kind, text=args.search, licence=args.licence)
            return Result(
                result={"release": source.version, "rows": rows, "total": len(rows)}, evidence=EVIDENCE
            )
        fetching = Fetching(confirm=confirm, offline=bool(args.offline))
        if form == "status":
            project, _ = _script_project(args.script, ctx)
            newest: Source | None = None
            try:
                newest = _cached_source(args, ctx, scratch)
            except CliError:
                newest = None
            rows, issues = status_rows(project, newest)
            return Result(
                result={"rows": rows, "lock": project.rel(project.lock_file.name)},
                issues=tuple(issues),
                evidence=EVIDENCE,
            )
        if form == "refresh":
            if args.from_:
                found = _from_source(args, ctx, fetching, scratch)
                version, source = found.version, cast(Source | None, found)
            else:
                version = _release_for(args)
                source = _network_source(version, args, fetching)
            body = {
                "release": version,
                "downloads": fetching.downloads,
                "cached": source is not None and not fetching.writes,
            }
            writes = [_deferred(w) for w in [*fetching.writes, *fetching.stamp_writes()]]
            return Result(result=body, evidence=EVIDENCE, writes=tuple(writes))
        if form == "locked":
            project, _ = _script_project(args.locked, ctx)
            sources: dict[str, Source] = {}
            for key, entry in sorted(project.entries.items()):
                if (project.folder / entry["path"]).is_dir() or entry["release"] in sources:
                    continue
                found = (
                    _from_source(args, ctx, fetching, scratch)
                    if args.from_
                    else _network_source(entry["release"], args, fetching, pinned=entry["index"])
                )
                if found is None:
                    return _pending(fetching, key)
                sources[entry["release"]] = found
            plan = plan_locked(sources, project)
            return _result(plan, None, fetching, project, args, ctx, check_licences=False)
        if form == "remove":
            project, _ = _script_project(args.script, ctx)
            plan = plan_remove(args.kind, args.id, project, allow_lossy=ctx.allow_lossy)
            return _result(plan, None, fetching, project, args, ctx, check_licences=False)
        project = (
            _board_project(args, ctx, args.id)
            if args.kind == "board"
            else _script_project(args.script, ctx)[0]
        )
        source = (
            _from_source(args, ctx, fetching, scratch)
            if args.from_
            else _network_source(_release_for(args), args, fetching)
        )
        if source is None:
            return _pending(fetching, f"{args.kind}/{args.id}")
        plan = plan_get(
            source, [(args.kind, args.id, args.item_version)], project, allow_lossy=ctx.allow_lossy
        )
        return _result(plan, source, fetching, project, args, ctx, check_licences=True)


def _pending(fetching: Fetching, key: str) -> Result:
    """A dry run whose release index is not cached: the plan holds its download; the items are planned once
    it is cached (``--confirm`` downloads it and plans everything in one run)."""
    body = {
        "stage": "index",
        "item": key,
        "downloads": fetching.downloads,
        "notes": [
            "the release index is not cached: --confirm downloads it, then plans the items in the same run"
        ],
    }
    writes = [_deferred(w) for w in [*fetching.writes, *fetching.stamp_writes()]]
    return Result(result=body, evidence=EVIDENCE, writes=tuple(writes))


COMMAND = Command(
    name="get",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="rows",
    example_args=("--list", "--from", EXAMPLE_LIBRARY),
    mutation_example_args=(
        "board",
        "demo-src/blink",
        "--from",
        EXAMPLE_LIBRARY,
        "--into",
        "blink",
        "--accept-licence",
        "CERN-OHL-S-2.0",
    ),
)

__all__ = ["COMMAND", "EVIDENCE", "KnownRelease", "asset_url", "known_releases"]
