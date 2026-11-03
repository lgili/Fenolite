# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite migrate DIR``: review and atomically rewrite an older canonical model folder.

Change c0218, model-versions "Migrate command"; docs/model-versions.md. The command executes no CAD
tool, imports no design script and changes no native document. All six layers use the mutation protocol.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.cmd_snapshot import shown
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model import canonical
from fenolite.model.design import SCHEMA_VERSION
from fenolite.model.migrate import migrate

HELP = "migrate an older canonical model folder to the current schema (writes six layers with --confirm)"
EXAMPLE_CURRENT = "fenolite-migrate-current"
EXAMPLE_LEGACY = "fenolite-migrate-legacy"
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-MODEL-OWN",))


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/model-versions.md. Native CAD files are not migrated."
    parser.add_argument("folder", metavar="DIR", help="the model folder itself, normally OUT/.fenolite")


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given = Path(args.folder)
    path = given if given.is_absolute() else ctx.cwd / given
    raw = canonical.read_data(path)
    version: str = raw["meta.json"]["schema_version"]
    data, steps = migrate(raw, version, file=str(path / "meta.json"))
    design = canonical.from_data(data, path=path)
    writes: tuple[PlannedWrite, ...] = ()
    issues: tuple[Issue, ...] = ()
    if steps:
        writes = tuple(
            PlannedWrite(shown(path / name, ctx.cwd), text.encode("utf-8"), "fenolite")
            for name, text in canonical.dump_texts(design).items()
        )
        issues = (
            Issue(
                "model.migrated", "info", "model migration planned: " + "; ".join(steps), where=args.folder
            ),
        )
    return Result(
        result={"from": version, "to": SCHEMA_VERSION, "steps": list(steps)},
        issues=issues,
        evidence=EVIDENCE,
        input=InputRef(
            path=args.folder,
            sha256=hashlib.sha256((path / "meta.json").read_bytes()).hexdigest(),
            kind="fenolite_model",
            format_version=version,
        ),
        writes=writes,
        depends=depends_on(ctx.cwd, *(path / name for name, _, _ in canonical.LAYER_FILES)),
    )


COMMAND = Command(
    name="migrate",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_CURRENT,),
    mutation_example_args=(EXAMPLE_LEGACY,),
)
