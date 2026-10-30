# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library gallery ROOT --release DIR --out DIR``: plan the static gallery of a release (change
c0279; ``fenolite.library.gallery``). ``DIR`` of ``--release`` holds the release assets of ``library
release`` (its ``index.json``), and a ``bench.json`` (the benchmark table) when one was made."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

import fenolite
from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.evidence import Evidence, Level
from fenolite.library.gallery import site
from fenolite.library.items import PROVENANCE_FILE, ItemError, load_json

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-LIBRARY-GET",))
KIND = "library-gallery"
BENCH = "bench.json"


def _path(given: str, ctx: Context) -> Path:
    return Path(given) if Path(given).is_absolute() else ctx.cwd / given


def gallery_command(args: argparse.Namespace, ctx: Context) -> Result:
    if len(args.path) != 2 or not args.release or not args.out:
        raise CliError(
            "FEN-2001",
            "library gallery takes ROOT, --release DIR and --out DIR",
            hint="fenolite library gallery . --release dist --out site --dry-run",
        )
    root, release = _path(args.path[1], ctx), _path(args.release, ctx)
    index_file = release / "index.json"
    try:
        index = load_json(index_file.read_bytes(), "index.json")
    except OSError as exc:
        raise CliError(
            "FEN-3001", f"--release {args.release} holds no index.json", where="--release"
        ) from exc
    except ItemError as exc:
        raise CliError("FEN-3004", str(exc), where="index.json") from exc
    records: dict[str, dict[str, Any]] = {}
    read: list[Path] = [index_file]
    for row in cast(list[dict[str, Any]], index.get("items", [])):
        path = root / str(row.get("path")) / PROVENANCE_FILE
        try:
            records[str(row.get("path"))] = load_json(path.read_bytes(), PROVENANCE_FILE)
            read.append(path)
        except (OSError, ItemError) as exc:
            raise CliError(
                "FEN-3001", f"{row.get('path')}/{PROVENANCE_FILE}: {exc}", where=str(row.get("path"))
            ) from exc
    bench: list[dict[str, Any]] = []
    if (release / BENCH).is_file():
        bench = cast(list[dict[str, Any]], json.loads((release / BENCH).read_text(encoding="utf-8")))
        read.append(release / BENCH)
    files = site(index, records, fenolite_version=fenolite.__version__, bench=bench)
    out = Path(args.out).as_posix().rstrip("/")
    cards = [name for name in files if name not in ("index.html", "bench.html")]
    return Result(
        result={
            "release": index.get("version"),
            "out": out,
            "cards": cards,
            "hidden": sorted(
                str(r.get("id"))
                for r in cast(list[dict[str, Any]], index.get("items", []))
                if not r.get("gallery")
            ),
        },
        evidence=EVIDENCE,
        writes=tuple(PlannedWrite(f"{out}/{name}", data, KIND) for name, data in files.items()),
        depends=depends_on(ctx.cwd, *read),
    )


__all__ = ["gallery_command"]
