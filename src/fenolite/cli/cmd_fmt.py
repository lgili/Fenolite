# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite fmt PATH [--check]``: Fenolite's canonical print of a KiCad S-expression file (capability
cli-contract, "Fmt command"; ``docs/cli-contract.md``, "fmt"), and the rewrite of a ``fenolite.device.v0``
record as ``fenolite.device.v1`` (change c0259, capability library-records, "Device records rewritten as
v1").

The canonical print is ``dumps(parse(text))``: the tree does not change, only the layout. It is meant for
diffs under version control and is not KiCad's own formatter: KiCad may lay the file out again when it
saves it. A device record keeps its device: ``records.upgraded_device`` adds the common header, and a
``v1`` record is left as it is.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import tomllib
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fenolite.backends.kicad import versions
from fenolite.backends.kicad.sexpr import dumps, first_line_difference, parse_bytes
from fenolite.catalog import records
from fenolite.catalog.devices import SCHEMA as DEVICE_V0
from fenolite.catalog.devices import DeviceFormatError
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level

HELP = (
    "give a KiCad S-expression file Fenolite's canonical print, or rewrite a v0 device record as v1; "
    "--check only reports"
)
KINDS = frozenset(
    {
        versions.FileKind.BOARD,
        versions.FileKind.FOOTPRINT,
        versions.FileKind.SCHEMATIC,
        versions.FileKind.SYMBOL_LIB,
        versions.FileKind.WORKSHEET,
    }
)
EVIDENCE = Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-K-FMT-IDEMPOTENT",))
"""The fixed point of the canonical print, measured over the corpus (``test_fmt_idempotent.py``)."""
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType({"fmt.would-change": "error"})
READS = (
    "fmt formats .kicad_pcb, .kicad_mod, .kicad_sch, .kicad_sym and .kicad_wks, and rewrites "
    "fenolite.device.v0 records (.toml) as fenolite.device.v1"
)
DEVICE = "device"
DEVICE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-LIBRARY-RECORDS",))
"""A device rewrite is Fenolite's own format; the round trip v0 → v1 → load is tested (``test_fmt_cmd``)."""
NO_LICENCE = "NOASSERTION"
"""The licence of a rewritten record whose file has no leading ``# SPDX-License-Identifier:`` line."""
SPDX_LINE = re.compile(r"#\s*SPDX-License-Identifier:\s*(\S.*?)\s*")
PROJECT_HINT = "project files are JSON and are kept byte for byte; " + READS
EXAMPLE_COPY = "fenolite-fmt-example.kicad_pcb"
"""The file of ``mutation_example_args``: a copy of an authored board that is not canonical, which the
test suites write into their empty folder (``tests/_cliexamples.py``)."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'fmt'."
    parser.add_argument(
        "path", metavar="PATH", help="a board, footprint, schematic, symbol library, sheet or device record"
    )
    parser.add_argument("--check", action="store_true", help="report whether the file would change")


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given = Path(args.path)
    path = given if given.is_absolute() else ctx.cwd / given
    if not path.is_file():
        raise CliError("FEN-3001", f"{path.name} is not a file", where=path.name)
    if path.suffix == ".toml":
        return _run_device(args, ctx, path)
    kind = versions.kind_for_suffix(path.name)
    if kind not in KINDS:
        hint = PROJECT_HINT if path.suffix == ".kicad_pro" else READS
        raise CliError("FEN-2001", f"fmt does not format {path.name}", hint=hint, where=path.name)
    assert kind is not None
    data = path.read_bytes()
    root = parse_bytes(data, file=path.name)
    try:
        canonical = dumps(root)
    except ValueError as exc:  # comments below the root: printing would drop or move them
        raise CliError(
            "FEN-7001", f"{path.name} cannot be printed: {exc}", hint="remove the comments below the root",
            where=path.name,
        ) from exc  # fmt: skip
    text = data.decode("utf-8")
    formatted = canonical.encode("utf-8") == data
    first = first_line_difference(text, canonical)
    result: dict[str, Any] = {
        "kind": kind.value,
        "formatted": formatted,
        "lines": len(text.splitlines()),
        "first_difference": first,
    }
    issues: tuple[Issue, ...] = ()
    writes: tuple[PlannedWrite, ...] = ()
    if not formatted and args.check:
        issues = (
            Issue(
                code="fmt.would-change",
                severity="error",
                message=f"{path.name} is not in its canonical print",
                where=f"{path.name}:{first}",
                hint="run 'fenolite fmt' on it with --confirm",
            ),
        )
    elif not formatted:
        target = Path(os.path.relpath(path, ctx.cwd)).as_posix()
        writes = (PlannedWrite(path=target, data=canonical.encode("utf-8"), kind=kind.value),)
    return Result(
        result=result,
        issues=issues,
        evidence=EVIDENCE,
        input=InputRef(
            path=path.name, sha256=hashlib.sha256(data).hexdigest(), kind=kind.value, format_version=None
        ),
        writes=writes,
        depends=depends_on(ctx.cwd, path),
    )


def _comments(text: str) -> tuple[list[str], int | None]:
    """The leading comment block of a TOML ``text`` (its comment and blank lines before the first other line,
    without the blank lines that end it) and the number of the first line after it that holds a comment, or
    ``None``. Strings are skipped, so a ``#`` inside one is no comment."""
    lines = text.split("\n")
    lead = 0
    while lead < len(lines) and (not lines[lead].strip() or lines[lead].lstrip().startswith("#")):
        lead += 1
    leading = [line.strip() for line in lines[:lead]]
    while leading and not leading[-1].strip():
        leading.pop()
    quote = ""
    for number, line in enumerate(lines[lead:], start=lead + 1):
        index = 0
        while index < len(line):
            if quote:
                if quote[0] == '"' and line[index] == "\\":  # escapes exist in basic strings only
                    index += 2
                    continue
                if line.startswith(quote, index):
                    index += len(quote)
                    quote = ""
                    continue
                index += 1
                continue
            char = line[index]
            if char == "#":
                return leading, number
            if char in "\"'":
                quote = char * 3 if line.startswith(char * 3, index) else char
                index += len(quote)
                continue
            index += 1
        if len(quote) == 1:  # a one-line string ends with its line
            quote = ""
    return leading, None


def _run_device(args: argparse.Namespace, ctx: Context, path: Path) -> Result:
    data = path.read_bytes()
    text = data.decode("utf-8")
    try:
        schema = tomllib.loads(text).get("schema")
    except tomllib.TOMLDecodeError:
        schema = DEVICE_V0  # not TOML: parse_record names the error
    if not (isinstance(schema, str) and schema.startswith("fenolite.device.")):
        what = f"a {schema} record" if isinstance(schema, str) else "not a device record"
        raise CliError("FEN-2001", f"fmt does not format {path.name}: {what}", hint=READS, where=path.name)
    record = records.parse_record(text, file=path.name)
    if not isinstance(record, records.DeviceRecord):  # pragma: no cover - the schema says device
        raise CliError("FEN-2001", f"fmt does not format {path.name}", hint=READS, where=path.name)
    schema = record.header.schema
    canonical = text
    if schema == DEVICE_V0:
        leading, comment = _comments(text)
        if comment is not None:
            raise CliError(
                "FEN-7001",
                f"{path.name} cannot be rewritten: the comment on line {comment} would be lost",
                hint="move the comments to the top of the file, before the first key, or remove them",
                where=f"{path.name}:{comment}",
            )
        spdx = [m.group(1) for m in (SPDX_LINE.fullmatch(line.strip()) for line in leading) if m]
        upgraded = records.upgraded_device(record, licence=spdx[0] if spdx else NO_LICENCE)
        canonical = "".join(line + "\n" for line in leading) + records.record_text(upgraded)
        try:
            again = records.parse_record(canonical, file=path.name)
        except DeviceFormatError as error:
            raise CliError(
                "FEN-3004",
                f"{path.name} cannot be rewritten as {records.SCHEMA_OF['device']}: {error.message}",
                hint="name the licence in a leading '# SPDX-License-Identifier:' line (CC0-1.0 for a "
                "Fenolite: id)",
                where=path.name,
            ) from None
        assert isinstance(again, records.DeviceRecord) and again.device == record.device
    formatted = canonical == text
    first = first_line_difference(text, canonical)
    result: dict[str, Any] = {
        "kind": DEVICE,
        "formatted": formatted,
        "lines": len(text.splitlines()),
        "first_difference": first,
        "schema": schema,
    }
    issues: tuple[Issue, ...] = ()
    writes: tuple[PlannedWrite, ...] = ()
    if not formatted and args.check:
        issues = (
            Issue(
                code="fmt.would-change",
                severity="error",
                message=f"{path.name} is a {schema} record; fmt rewrites it as {records.SCHEMA_OF['device']}",
                where=f"{path.name}:{first}",
                hint="run 'fenolite fmt' on it with --confirm",
            ),
        )
    elif not formatted:
        target = Path(os.path.relpath(path, ctx.cwd)).as_posix()
        writes = (PlannedWrite(path=target, data=canonical.encode("utf-8"), kind=DEVICE),)
    return Result(
        result=result,
        issues=issues,
        evidence=DEVICE_EVIDENCE,
        input=InputRef(
            path=path.name, sha256=hashlib.sha256(data).hexdigest(), kind=DEVICE, format_version=None
        ),
        writes=writes,
        depends=depends_on(ctx.cwd, path),
    )


COMMAND = Command(
    name="fmt",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD, "--check"),
    mutation_example_args=(EXAMPLE_COPY,),
)
