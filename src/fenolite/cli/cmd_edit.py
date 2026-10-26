# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite edit PATH (--content-file FILE | --edits-file FILE)``: write a text file of a design through the
write protocol (capability cli-contract, "Edit command" and "Edit checks without running"; change c0196;
``docs/cli-contract.md``, "edit").

The files are those a design is written in: a design script (``*.py``), a TOML file (``*.toml``) and the
library tables (``fp-lib-table``, ``sym-lib-table``), UTF-8 text of at most 1 MB. ``--content-file`` gives the
whole new text; ``--edits-file`` a JSON list of ``{"old", "new"}`` pairs, applied in order to the text as it
stands, each ``old`` found exactly once. The result must parse (``ast.parse`` for a script, ``tomllib`` for
TOML) before it is planned; the script is never imported or run. The plan carries a unified diff; the file
keeps its line ends.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import os
import tomllib
from pathlib import Path
from typing import Any, cast

from fenolite.cli._examples import EXAMPLE_SCRIPT
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef

HELP = "write a design script, a TOML file or a library table from a new text or exact edits, through a plan"
LIMIT = 1_000_000
"""The largest file, before and after the edit, in bytes."""
DIFF_LINES = 400
TABLES = frozenset({"fp-lib-table", "sym-lib-table"})
EXAMPLE_COPY = "fenolite-edit-example.py"
EXAMPLE_CONTENT = "fenolite-edit-example.new"
"""The files of ``mutation_example_args``, which the test suites write into their empty folder
(``tests/_cliexamples.py``)."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'edit'."
    parser.add_argument("path", metavar="PATH", help="a *.py, a *.toml, an fp-lib-table or a sym-lib-table")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--content-file", metavar="FILE", help="a file holding the whole new text")
    source.add_argument("--edits-file", metavar="FILE", help='a JSON list of {"old": ..., "new": ...} pairs')


def _kind(path: Path) -> str:
    if path.suffix == ".py":
        return "design-script"
    if path.suffix == ".toml":
        return "toml"
    if path.name in TABLES:
        return "library-table"
    raise CliError(
        "FEN-2001", f"edit does not write {path.name}", where=path.name,
        hint="edit writes *.py, *.toml, fp-lib-table and sym-lib-table; other files have their own commands",
    )  # fmt: skip


def _text(path: Path, what: str) -> str:
    data = path.read_bytes()
    if len(data) > LIMIT:
        raise CliError("FEN-3004", f"{what} {path.name} is larger than {LIMIT} bytes", where=path.name)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CliError("FEN-3004", f"{what} {path.name} is not UTF-8 text: {exc}", where=path.name) from exc


def _given(ctx: Context, value: str, flag: str) -> Path:
    path = Path(value) if Path(value).is_absolute() else ctx.cwd / value
    if not path.is_file():
        raise CliError("FEN-3001", f"{flag}: {value} is not a file", where=flag)
    return path


def _pairs(path: Path) -> list[tuple[str, str]]:
    try:
        raw = json.loads(_text(path, "the edits file"))
    except ValueError as exc:
        raise CliError("FEN-3004", f"--edits-file is not JSON: {exc}", where="--edits-file") from exc
    pairs: list[tuple[str, str]] = []
    items = cast("list[Any]", raw) if isinstance(raw, list) else None
    if items is None:
        raise CliError(
            "FEN-3004", '--edits-file must hold a list of {"old", "new"} pairs', where="--edits-file"
        )
    for number, item in enumerate(items, start=1):
        pair = cast("dict[str, Any]", item) if isinstance(item, dict) else {}
        old, new = pair.get("old"), pair.get("new")
        if set(pair) != {"old", "new"} or not isinstance(old, str) or not isinstance(new, str) or not old:
            message = f"edit {number}: a pair is an object with a non-empty string old and a string new"
            raise CliError("FEN-3004", message, where=f"--edits-file:{number}")
        pairs.append((old, new))
    return pairs


def _apply(text: str, pairs: list[tuple[str, str]], name: str) -> str:
    for number, (old, new) in enumerate(pairs, start=1):
        found = text.count(old)
        if found != 1:
            message = (
                f"edit {number} of {len(pairs)}: its old text is found {found} times in {name}, not once"
            )
            hint = "give more of the surrounding text, so that it is found once"
            raise CliError("FEN-3004", message, where=f"--edits-file:{number}", hint=hint)
        text = text.replace(old, new, 1)
    return text


def _parses(text: str, kind: str, name: str) -> None:
    """Parse the new text without running it; ``FEN-3004`` with the line when it does not."""
    try:
        if kind == "design-script":
            ast.parse(text, filename=name)
        elif kind == "toml":
            tomllib.loads(text)
    except SyntaxError as exc:
        raise CliError(
            "FEN-3004", f"{name}:{exc.lineno}: the edited script does not parse: {exc.msg}",
            where=f"{name}:{exc.lineno}",
        ) from exc  # fmt: skip
    except tomllib.TOMLDecodeError as exc:
        raise CliError("FEN-3004", f"{name}: the edited TOML does not parse: {exc}", where=name) from exc


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given = Path(str(args.path))
    path = given if given.is_absolute() else ctx.cwd / given
    kind = _kind(path)
    created = not path.exists()
    if not created and not path.is_file():
        raise CliError("FEN-3001", f"{path.name} is not a file", where=path.name)
    old = "" if created else _text(path, "the file")
    newline = "\r\n" if "\r\n" in old else "\n"
    if args.content_file is not None:
        source = _given(ctx, str(args.content_file), "--content-file")
        new = _text(source, "the content file").replace("\r\n", "\n")
    else:
        source = _given(ctx, str(args.edits_file), "--edits-file")
        if created:
            raise CliError(
                "FEN-3001", f"{path.name} does not exist: create it with --content-file", where=path.name
            )
        new = _apply(old.replace("\r\n", "\n"), _pairs(source), path.name)
    _parses(new, kind, path.name)
    new = new.replace("\n", newline)
    data = new.encode("utf-8")
    if len(data) > LIMIT:
        raise CliError("FEN-3004", f"the edited {path.name} is larger than {LIMIT} bytes", where=path.name)
    target = Path(os.path.relpath(path, ctx.cwd)).as_posix()
    diff = list(
        difflib.unified_diff(
            old.splitlines(), new.splitlines(), f"a/{target}", f"b/{target}", n=3, lineterm=""
        )
    )
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    result: dict[str, Any] = {
        "path": target,
        "kind": kind,
        "created": created,
        "changed": new != old,
        "lines_added": added,
        "lines_removed": removed,
        "diff": "\n".join(diff[:DIFF_LINES]),
        "diff_truncated": len(diff) > DIFF_LINES,
    }
    writes = (PlannedWrite(path=target, data=data, kind=kind),) if new != old else ()
    inputs = (path, source) if not created else (source,)
    return Result(
        result=result,
        input=InputRef(
            path=path.name,
            sha256=hashlib.sha256(old.encode("utf-8")).hexdigest(),
            kind=kind,
            format_version=None,
        )
        if not created
        else None,
        writes=writes,
        depends=depends_on(ctx.cwd, *inputs),
    )


COMMAND = Command(
    name="edit",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_SCRIPT, "--content-file", EXAMPLE_SCRIPT),
    mutation_example_args=(EXAMPLE_COPY, "--content-file", EXAMPLE_CONTENT),
)
