# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``blocks test`` adapter; tests and goldens live in ``fenolite.testing`` (c0270)."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import os
from pathlib import Path

from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.blocksrc import CatalogEntry, duplicate_issues, find_blocks
from fenolite.cli.errors import CliError
from fenolite.core.evidence import Evidence, Level
from fenolite.testing.blocks import KINDS, convention_of_entry, run_block_tests

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-BLOCK-GOLDEN",))


def register_test(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--golden", action="store_true", help="test: plan regenerated circuit/rules goldens")
    parser.add_argument("--only", choices=KINDS, help="test: run usage, golden comparison or test functions")


def project_files(cwd: Path) -> tuple[str, ...]:
    """Project modules following the convention; ordinary design scripts are never auto-imported."""
    return tuple(
        path.name
        for path in sorted(cwd.glob("*.py"))
        if (cwd / "usage" / f"{path.stem}.py").is_file() or (cwd / "tests" / f"test_{path.stem}.py").is_file()
    )


def _selected(args: argparse.Namespace, entries: tuple[CatalogEntry, ...]) -> tuple[CatalogEntry, ...]:
    known = sorted({entry.id for entry in entries})
    for given in args.target:
        wanted = str(given)
        if wanted not in known:
            close = difflib.get_close_matches(wanted, known, n=3, cutoff=0)
            raise CliError(
                "FEN-2001",
                f"no block has the id {wanted}",
                where=wanted,
                hint=f"the closest ids are: {', '.join(close)}"
                if close
                else "fenolite blocks list shows the ids",
            )
    return tuple(
        entry
        for entry in entries
        if (not args.target or entry.id in args.target)
        and (
            args.category is None
            or (entry.record.header is not None and entry.record.header.category == args.category)
        )
    )


def run_test(args: argparse.Namespace, ctx: Context, entries: tuple[CatalogEntry, ...]) -> Result:
    if args.golden and args.only not in (None, "golden"):
        raise CliError("FEN-2001", "--golden combines with --only golden only", where="--only")
    if args.golden and args.confirm and args.plan is None:
        raise CliError(
            "FEN-2001",
            "review golden bytes with --dry-run, then use --confirm --plan ID",
            where="--golden",
        )
    if not args.files:
        local = project_files(ctx.cwd)
        if local:
            discovered = find_blocks(files=local, cwd=ctx.cwd)
            entries = (*entries, *(entry for entry in discovered if entry.source == "file"))
    chosen = _selected(args, entries)
    duplicates = tuple(duplicate_issues(chosen))
    if duplicates:
        return Result(result={"blocks": []}, issues=duplicates, evidence=EVIDENCE)
    found = run_block_tests(chosen, kinds=(args.only,) if args.only else KINDS, golden_plan=args.golden)
    writes = tuple(
        PlannedWrite(os.path.relpath(write.path, ctx.cwd).replace(os.sep, "/"), write.data, "block-golden")
        for write in found.writes
    )
    result = {"blocks": list(found.blocks)}
    if args.golden:
        result["golden_plan"] = [
            {
                "path": write.path,
                "old_sha256": hashlib.sha256((ctx.cwd / write.path).read_bytes()).hexdigest()
                if (ctx.cwd / write.path).is_file()
                else None,
                "new_sha256": hashlib.sha256(write.data).hexdigest(),
            }
            for write in writes
        ]
    inputs = set(found.depends)
    for entry in chosen:
        paths = convention_of_entry(entry)
        roots = (
            (paths.project / "fenolite_library", paths.project / "devices")
            if paths.project is not None
            else (paths.root,)
        )
        for root in roots:
            if root:
                inputs.update(
                    path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts
                )
    return Result(
        result=result,
        issues=found.issues,
        evidence=EVIDENCE,
        writes=writes,
        depends=depends_on(ctx.cwd, *inputs),
        fail_on_warning=True,
    )
