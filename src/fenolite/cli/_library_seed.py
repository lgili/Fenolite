# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Plan-only adapter for the independent LibrePCB seed converter (c0266)."""

from __future__ import annotations

import argparse
import json
import os
import re
import tomllib
from pathlib import Path
from typing import cast

import fenolite
from fenolite.catalog.records import Origin, parse_record, record_text
from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.library.device_items import source_ids
from fenolite.library.items import FOLDERS, Item, canonical_json, id_path, tree_digest
from fenolite.library.licences import normalised_digest
from fenolite.library.seed import convert

EVIDENCE = Evidence(Level.UNVERIFIED, hypotheses=("H-G-LIBREPCB-SEED",))
SCHEMA = "fenolite.library-seed.v0"


def register(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("LibrePCB library seed")
    group.add_argument("--from-librepcb", metavar="DIR", help="seed: local CC0-1.0 library checkout")
    group.add_argument("--commit", metavar="SHA", help="seed: required full upstream commit")
    group.add_argument("--namespace", metavar="NS", help="seed: item namespace (default FenoliteDevices)")


def only_seed(args: argparse.Namespace, action: str) -> None:
    for name in ("from_librepcb", "commit", "namespace"):
        if getattr(args, name, None):
            raise CliError("FEN-2001", f"--{name.replace('_', '-')} belongs to library seed, not {action}")


def _existing(folder: Path) -> tuple[str, bool]:
    records = tuple(folder.glob("*.toml"))
    if len(records) != 1:
        raise CliError(
            "FEN-7001", f"{folder.name}: cannot replace an item without exactly one readable record"
        )
    try:
        record = parse_record(records[0].read_text(encoding="utf-8"), allow_stale_reviews=True)
    except (FormatError, OSError, UnicodeError) as exc:
        raise CliError(
            "FEN-7001", f"{folder.name}: existing record cannot be safely replaced: {exc}"
        ) from None
    if not isinstance(record.header.origin, Origin):
        raise CliError("FEN-7001", f"{folder.name}: existing item is not a seeded record")
    try:
        provenance = json.loads((folder / "PROVENANCE.json").read_text(encoding="utf-8"))
        if not isinstance(provenance, dict) or cast(dict[str, object], provenance).get("origin") != "seeded":
            raise ValueError("origin is not seeded")
    except (ValueError, OSError, UnicodeError) as exc:
        raise CliError("FEN-7001", f"{folder.name}: seeded provenance is required: {exc}") from None
    return record.header.origin.element, bool(record.header.reviewed_by)


class _Ids:
    def __init__(self, into: Path, namespace: str) -> None:
        self.into, self.namespace = into, namespace
        self.seen: dict[tuple[str, str], str] = {}
        self.issues: list[Issue] = []

    def __call__(self, kind: str, name: str, element: str) -> str:
        clean = re.sub(r"[^A-Za-z0-9_.+-]", "_", name) or "unnamed"
        if clean in {".", ".."}:
            clean = "unnamed_" + element.replace("-", "")[:8]
        while ".." in clean:
            clean = clean.replace("..", "_")
        candidate = f"{self.namespace}:{clean}"
        folder = self.into / FOLDERS[kind] / "cc0" / id_path(candidate)
        collision = (kind, candidate) in self.seen and self.seen[(kind, candidate)] != element
        if folder.exists():
            # Authored/unreadable existing items are collisions, not overwrite candidates.
            try:
                collision = collision or _existing(folder)[0] != element
            except CliError:
                collision = True
        if collision:
            candidate += "_" + element.replace("-", "")[:8]
            folder = self.into / FOLDERS[kind] / "cc0" / id_path(candidate)
            if (kind, candidate) in self.seen and self.seen[(kind, candidate)] != element:
                raise ValueError("UUID prefix collision after deterministic rename")
        if folder.exists():
            old_element, reviewed = _existing(folder)
            if old_element != element or reviewed:
                raise CliError(
                    "FEN-7001",
                    f"{candidate}: a reviewed or different-origin item cannot be overwritten, "
                    "even with --allow-lossy",
                )
        self.seen[(kind, candidate)] = element
        if clean != name or collision:
            self.issues.append(
                Issue(
                    "library.seed-renamed", "info", f"{element}: {name!r} becomes {candidate}", where=element
                )
            )
        return candidate


def _register_source(into: Path, library: str, commit: str, date: str) -> tuple[str, str]:
    source_ids(into)
    path = into / "sources.toml"
    text = path.read_text(encoding="utf-8") if path.is_file() else 'schema = "fenolite.library-sources.v0"\n'
    raw = tomllib.loads(text).get("sources", {})
    rows = cast(dict[str, dict[str, object]], raw)
    for source_id, row in rows.items():
        if row.get("title") == library and commit in str(row.get("used", "")):
            return source_id, text
    number = next(number for number in range(1, 10_000) if f"D-{number:04d}" not in rows)
    return f"D-{number:04d}", text


def run(args: argparse.Namespace, ctx: Context) -> Result:
    if len(args.path) != 1 or not all((args.from_librepcb, args.commit, args.library, args.into)):
        raise CliError(
            "FEN-2001", "library seed requires --from-librepcb DIR --commit SHA --library NAME --into DIR"
        )
    for name in (
        "out",
        "diff",
        "symbol",
        "footprint",
        "package",
        "device_id",
        "manufacturer",
        "mpn",
        "datasheet",
        "ref_prefix",
        "prefer",
        "pin",
        "no_crosscheck",
        "all",
        "count",
        "no_step",
        "no_pcblib",
        "item",
        "base",
        "proof",
        "release_version",
        "upstream",
        "keep",
        "with_current",
        "release",
        "rules",
        "sheet",
        "compare",
        "strict",
        "who",
        "accept",
        "evidence",
    ):
        if getattr(args, name, None):
            raise CliError("FEN-2001", f"--{name.replace('_', '-')} is not a seed option")
    source = (ctx.cwd / args.from_librepcb).resolve()
    into = (ctx.cwd / args.into).resolve()
    if source == into or source.is_relative_to(into) or into.is_relative_to(source):
        raise CliError("FEN-2001", "seed source and output folders must be separate")
    namespace = args.namespace or "FenoliteDevices"
    date = ctx.timestamp.date().isoformat()
    source_id, register_text = _register_source(into, args.library, args.commit, date)
    ids = _Ids(into, namespace)
    made = convert(
        source,
        library_name=args.library,
        commit=args.commit,
        namespace=namespace,
        source_id=source_id,
        allocate=ids,
    )
    registered = cast(dict[str, dict[str, object]], tomllib.loads(register_text).get("sources", {}))
    if source_id in registered and registered[source_id].get("url") != made.upstream:
        raise FormatError(f"{source_id}: the registered source URL disagrees with library.lp")
    if source_id not in registered:
        row = {
            "id": source_id,
            "title": args.library,
            "url": made.upstream,
            "licence": "CC0-1.0",
            "retrieved": date,
            "used": f"Seed library elements at commit {args.commit}; conversion remains UNVERIFIED",
        }
        register_text += (
            f"\n[sources.{source_id}]\n"
            + "\n".join(f"{key} = {json.dumps(value)}" for key, value in row.items())
            + "\n"
        )
    files: dict[Path, bytes] = {}
    rows: list[dict[str, object]] = []
    for seeded in made.items:
        record = seeded.record
        item = Item(
            seeded.kind,
            record.header.id,
            record.header.version,
            record.header.name,
            record.header.summary,
            "CC0-1.0",
            (),
            ("record.toml",),
            seeded.depends,
            False,
        )
        folder = into / FOLDERS[item.kind] / "cc0" / id_path(item.id)
        payload = record_text(record).encode("utf-8")
        notice = (
            f"{date}: converted from {args.library} at {args.commit} by Fenolite "
            f"{fenolite.__version__}; format change only; UNVERIFIED"
        )
        provenance = {
            "schema": "fenolite.provenance.v0",
            "kind": item.kind,
            "id": item.id,
            "version": item.version,
            "spdx": item.spdx,
            "origin": "seeded",
            "authors": [args.library],
            "copyright": [],
            "sources": [source_id],
            "evidence": "UNVERIFIED",
            "licence_text_sha256": normalised_digest(made.licence),
            "modification_notice": notice,
            "upstream": {"url": made.upstream, "commit": args.commit, "spdx_expression": "CC0-1.0"},
            "conversion": {
                "tools": [{"name": "fenolite", "version": fenolite.__version__}],
                "steps": [
                    {
                        "tool": "fenolite",
                        "argv": [
                            "library",
                            "seed",
                            "--from-librepcb",
                            "upstream",
                            "--commit",
                            args.commit,
                            "--library",
                            args.library,
                            "--into",
                            "output",
                            "--namespace",
                            namespace,
                            "--confirm",
                        ],
                    }
                ],
                "outputs_tree": tree_digest({"record.toml": payload}),
            },
        }
        for name, data in {
            "record.toml": payload,
            "item.json": canonical_json(item.as_json()),
            "LICENSE": made.licence,
            "NOTICE": (notice + "\n").encode(),
            "PROVENANCE.json": canonical_json(provenance),
        }.items():
            files[folder / name] = data
        rows.append({"kind": item.kind, "id": item.id, "version": item.version, "element": seeded.element})
    if made.items:
        files[into / "sources.toml"] = register_text.encode("utf-8")
    writes = tuple(
        PlannedWrite(Path(os.path.relpath(path, ctx.cwd)).as_posix(), data, "library-seed")
        for path, data in sorted(files.items())
        if not path.is_file() or path.read_bytes() != data
    )
    existing = tuple(sorted(p for p in into.rglob("*") if p.is_file())) if into.is_dir() else ()
    return Result(
        result={
            "schema": SCHEMA,
            "items": rows,
            "source": source_id,
            "unchanged": not writes,
            "evidence": "UNVERIFIED",
        },
        issues=(*made.issues, *ids.issues),
        evidence=EVIDENCE,
        writes=writes,
        depends=depends_on(ctx.cwd, *made.inputs, *existing),
    )
