# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite publish SRC --to DST --receipt RECEIPT``: put an edited copy back over a project, replacing
only the files nobody changed since the receipt (capability file-safety, "Publish guarded by receipts";
``docs/file-safety.md``; ``docs/cli-contract.md``, "publish").

``RECEIPT`` is the ``snapshot.json`` of the copy (paths relative to the project folder), or the envelope or
receipt of an earlier confirmed write of Fenolite (paths relative to ``--in``). A file of ``DST`` is replaced
only when its SHA-256 is the one the receipt recorded. A file the owner saved since, or that the receipt
does not name, is a conflict: the command then writes nothing (``safety.changed-since-receipt``, exit 5),
or with ``--skip-changed`` leaves those files and writes the others (``safety.skipped``). A file new to
``DST`` is added; a file equal on both sides is not written; nothing is deleted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.cmd_restore import read_receipt
from fenolite.cli.cmd_snapshot import MANIFEST, SCHEMA, refuse_online, shown
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.io import sha256_bytes, sha256_of
from fenolite.safety.codes import ISSUE_CODES as SAFETY_CODES
from fenolite.safety.files import SKIPPED_SUFFIXES

HELP = "put an edited copy back over a project, replacing only the files unchanged since the receipt"
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-SNAPSHOT-STABLE",))
EXAMPLE_SOURCE = "publish-example-src"
EXAMPLE_TARGET = "publish-example-dst"
"""The folders of the examples: the suites write a copy, a project and its ``snapshot.json`` first."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source", metavar="SRC", help="the folder of the edited copy")
    parser.add_argument("--to", required=True, metavar="DST", help="the project folder to update")
    parser.add_argument(
        "--receipt",
        required=True,
        metavar="RECEIPT",
        help="the snapshot.json of the copy, or the envelope of Fenolite's last write into DST",
    )
    parser.add_argument(
        "--in",
        dest="receipt_in",
        default=None,
        metavar="DIR",
        help="the working directory of the write that RECEIPT records (default: the current one)",
    )
    parser.add_argument(
        "--skip-changed",
        action="store_true",
        help="leave the files changed since the receipt and write the others (warnings, not errors)",
    )


def _folder(text: str, cwd: Path, option: str) -> Path:
    path = Path(text) if Path(text).is_absolute() else cwd / text
    if not path.is_dir():
        raise CliError("FEN-3001", f"{option} {text} is not a folder", where=option)
    return path


def _expected(receipt: Path, target: Path, base: Path) -> dict[str, str]:
    """The hash the receipt records for each file, by its path relative to ``target``."""
    try:
        text = receipt.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise CliError("FEN-3001", f"cannot read {receipt.name}: {error}", where=receipt.name) from None
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as error:
        raise CliError("FEN-3004", f"{receipt.name}: invalid JSON: {error.msg}", where=receipt.name) from None
    if isinstance(data, dict) and cast(dict[str, Any], data).get("schema") == SCHEMA:
        files = cast(dict[str, Any], data).get("files")
        if not isinstance(files, list):
            raise CliError(
                "FEN-3004", f"{receipt.name}: a snapshot needs the list 'files'", where=receipt.name
            )
        found: dict[str, str] = {}
        for entry in cast(list[object], files):
            row = cast(dict[str, object], entry) if isinstance(entry, dict) else {}
            path, digest = row.get("path"), row.get("sha256")
            if not isinstance(path, str) or not isinstance(digest, str):
                raise CliError(
                    "FEN-3004", f"{receipt.name}: a file entry is not {{path, sha256}}", where=receipt.name
                )
            found[path] = digest
        return found
    try:
        written, _, _ = read_receipt(text, receipt.name)
    except FormatError as error:
        raise CliError("FEN-3004", str(error), where=receipt.name) from None
    found = {}
    for entry in written:
        full = (base / entry.path).resolve()
        if full.is_relative_to(target.resolve()):
            found[full.relative_to(target.resolve()).as_posix()] = entry.sha256
    return found


def _source_files(source: Path) -> list[Path]:
    """Every file of the copy but its manifest, backups, lock files and hidden folders."""
    found: list[Path] = []
    for item in source.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(source)
        if (
            rel.as_posix() == MANIFEST
            or rel.name.startswith(("~", "."))
            or rel.name.endswith(SKIPPED_SUFFIXES)
        ):
            continue
        if any(part.startswith(".") or part == "__pycache__" for part in rel.parts[:-1]):
            continue
        found.append(rel)
    return sorted(found, key=lambda rel: rel.as_posix())


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    source = _folder(args.source, ctx.cwd, "SRC")
    target = _folder(args.to, ctx.cwd, "--to")
    receipt = Path(args.receipt) if Path(args.receipt).is_absolute() else ctx.cwd / args.receipt
    base = ctx.cwd if args.receipt_in is None else _folder(args.receipt_in, ctx.cwd, "--in")
    expected = _expected(receipt, target, base)
    files = _source_files(source)
    refuse_online(source, files)
    refuse_online(target, [rel for rel in files if (target / rel).is_file()])
    code = "safety.skipped" if args.skip_changed else "safety.changed-since-receipt"
    writes: list[PlannedWrite] = []
    issues: list[Issue] = []
    added: list[str] = []
    replaced: list[str] = []
    changed: list[str] = []
    unchanged = 0
    for rel in files:
        name = rel.as_posix()
        data = (source / rel).read_bytes()
        destination = target / rel
        if not destination.exists():
            added.append(name)
        else:
            current = sha256_of(destination)
            if current == sha256_bytes(data):
                unchanged += 1
                continue
            recorded = expected.get(name)
            if recorded != current:
                changed.append(name)
                why = "the receipt does not name it" if recorded is None else "it changed since the receipt"
                issues.append(
                    Issue(
                        code,
                        SAFETY_CODES[code],
                        f"{name} is left as it is in {args.to}: {why}",
                        where=name,
                        hint="merge that file by hand, or take a new snapshot and edit again",
                    )
                )
                continue
            replaced.append(name)
        writes.append(PlannedWrite(shown(destination, ctx.cwd), data, "published_file"))
    result: dict[str, object] = {
        "source": shown(source, ctx.cwd),
        "to": shown(target, ctx.cwd),
        "added": added,
        "replaced": replaced,
        "changed": changed,
        "unchanged": unchanged,
    }
    return Result(
        result=result,
        issues=tuple(issues),
        writes=tuple(writes),
        evidence=EVIDENCE,
        depends=depends_on(ctx.cwd, receipt, *(source / rel for rel in files)),
    )


COMMAND = Command(
    name="publish",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(
        EXAMPLE_SOURCE,
        "--to",
        EXAMPLE_TARGET,
        "--receipt",
        f"{EXAMPLE_SOURCE}/{MANIFEST}",
        "--dry-run",
    ),
    mutation_example_args=(
        EXAMPLE_SOURCE,
        "--to",
        EXAMPLE_TARGET,
        "--receipt",
        f"{EXAMPLE_SOURCE}/{MANIFEST}",
    ),
)

__all__ = ["COMMAND", "EXAMPLE_SOURCE", "EXAMPLE_TARGET"]
