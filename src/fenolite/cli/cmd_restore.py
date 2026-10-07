# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite restore RECEIPT``: put back the backups of one confirmed write (capability cli-contract,
"Restore command"; ``docs/cli-contract.md``, "restore").

The receipt that the write returned is the undo token: it names the files written, their hashes and the
backups kept. Nothing is restored unless every written file is still as that write left it, and no file
is ever deleted: a file the write created stays. The restore is itself a confirmed write, so the content
it replaces becomes the new backup and its own receipt undoes it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, cast

from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import WrittenFile, receipt_id
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.io import sha256_bytes

HELP = "put back the backups of one confirmed write, described by its receipt (deletes nothing)"
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "restore.changed-since": "error",
        "restore.backup-missing": "error",
        "restore.nothing": "error",
        "restore.kept": "info",
    }
)
BACKUP_SUFFIX = ".bak"
EXAMPLE_RECEIPT = "fenolite-restore-example.json"
"""The receipt of ``example_args``: the test suites write it, the file it names and that file's backup
into their folder first (``tests/_cliexamples.py``)."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'restore'."
    parser.add_argument(
        "receipt", metavar="RECEIPT", help="a file holding the envelope of a write, or - for stdin"
    )
    parser.add_argument(
        "--in", dest="folder", metavar="DIR", help="the working directory of that write (default: this one)"
    )


def _bad(message: str, file: str) -> FormatError:
    return FormatError(message, file=file)


def _relative(value: object, file: str) -> str:
    """A path of the receipt, which must stay inside the folder it is restored in."""
    if not isinstance(value, str) or not value:
        raise _bad("a path of the receipt is not a non-empty string", file)
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise _bad(f"the receipt names {value!r}, which is not a path inside the folder", file)
    return path.as_posix()


def _receipt(text: str, file: str) -> tuple[list[WrittenFile], list[str], str]:
    """``(written, backup, id)`` of an envelope or of a bare receipt object."""
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FormatError(f"invalid JSON: {exc.msg}", file=file, offset=exc.pos) from exc
    if isinstance(data, dict) and "receipt" in data:
        data = cast(dict[str, object], data)["receipt"]
        if data is None:
            raise _bad("the envelope has no receipt: that command wrote nothing", file)
    if not isinstance(data, dict):
        raise _bad("expected the envelope of a confirmed write, or its receipt object", file)
    body = cast(dict[str, Any], data)
    written_raw, backup_raw = body.get("written"), body.get("backup")
    if not isinstance(written_raw, list) or not isinstance(backup_raw, list):
        raise _bad("the receipt needs the lists 'written' and 'backup'", file)
    written: list[WrittenFile] = []
    for entry in cast(list[object], written_raw):
        digest = cast(dict[str, object], entry).get("sha256") if isinstance(entry, dict) else None
        if not isinstance(entry, dict) or not isinstance(digest, str):
            raise _bad("an entry of 'written' is not {path, sha256}", file)
        written.append(WrittenFile(_relative(cast(dict[str, object], entry).get("path"), file), digest))
    backup = [_relative(item, file) for item in cast(list[object], backup_raw)]
    names = {w.path for w in written}
    for item in backup:
        if not item.endswith(BACKUP_SUFFIX) or item[: -len(BACKUP_SUFFIX)] not in names:
            raise _bad(f"the backup {item!r} belongs to no written file of the receipt", file)
    ident = body.get("id")
    return written, backup, ident if isinstance(ident, str) and ident else receipt_id(written, backup)


def _issue(code: str, message: str, where: str, hint: str = "") -> Issue:
    return Issue(code=code, severity=ISSUE_CODES[code], message=message, where=where, hint=hint)


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given: Path | None = None
    if args.receipt == "-":
        text, name = sys.stdin.read(), "<stdin>"
    else:
        source = Path(args.receipt)
        source = source if source.is_absolute() else ctx.cwd / source
        if not source.is_file():
            raise CliError("FEN-3001", f"{source.name} is not a file", where=source.name)
        text, name = source.read_text(encoding="utf-8"), source.name
        given = source
    written, backup, ident = _receipt(text, name)
    folder = ctx.cwd if args.folder is None else (ctx.cwd / args.folder)
    if not folder.is_dir():
        raise CliError("FEN-3001", f"--in {args.folder} is not a folder", where="--in")

    backed = {item[: -len(BACKUP_SUFFIX)] for item in backup}
    kept = [w.path for w in written if w.path not in backed]
    issues: list[Issue] = []
    changed: list[str] = []
    for entry in written:
        target = folder / entry.path
        if not target.is_file() or sha256_bytes(target.read_bytes()) != entry.sha256:
            changed.append(entry.path)
            what = "is missing" if not target.is_file() else "changed since the write"
            issues.append(
                _issue("restore.changed-since", f"{entry.path} {what}; nothing is restored", entry.path,
                       "restore the file by hand from its .bak, or undo the later change first")
            )  # fmt: skip
    missing = [item for item in backup if not (folder / item).is_file()]
    issues += [
        _issue("restore.backup-missing", f"the backup {item} does not exist; nothing is restored", item)
        for item in missing
    ]
    if not backup:
        issues.append(
            _issue("restore.nothing", "the receipt kept no backup, so there is nothing to put back", name,
                   "restore deletes no file; remove a created file by hand if it is unwanted")
        )  # fmt: skip
    result: dict[str, Any] = {"id": ident, "restored": [], "kept": kept}
    if changed:
        result["changed"] = changed
    if any(issue.severity == "error" for issue in issues):
        return Result(result=result, issues=tuple(issues))

    writes: list[PlannedWrite] = []
    for item in backup:
        path = item[: -len(BACKUP_SUFFIX)]
        target = Path(os.path.relpath(folder / path, ctx.cwd)).as_posix()
        writes.append(PlannedWrite(path=target, data=(folder / item).read_bytes(), kind="restore"))
    result["restored"] = [item[: -len(BACKUP_SUFFIX)] for item in backup]
    issues += [
        _issue("restore.kept", f"{path} has no backup and stays as it is", path, "restore deletes no file")
        for path in kept
    ]
    read = (given, *(folder / entry.path for entry in written), *(folder / item for item in backup))
    return Result(
        result=result, issues=tuple(issues), writes=tuple(writes), depends=depends_on(ctx.cwd, *read)
    )


COMMAND = Command(
    name="restore",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_RECEIPT, "--dry-run"),
    mutation_example_args=(EXAMPLE_RECEIPT,),
)
