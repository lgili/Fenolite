# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite explain CODE``: what an error code or an issue code means and what to do about it (capability
cli-contract, "Explain command"; ``docs/cli-contract.md``, "explain"). Reads only packaged data."""

from __future__ import annotations

import argparse
import difflib

from fenolite.cli import explain
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import REGISTRY, CliError

HELP = "say what an error code or an issue code means and what to do about it"
NO_MATCH_HINT = "codes are FEN-NNNN or dotted names such as check.rt1-failed; see 'fenolite capabilities'"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'explain'."
    parser.add_argument("code", metavar="CODE", help="FEN-NNNN, or an issue code such as kicad.drc.clearance")


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    code = str(args.code)
    found = explain.explain(code)
    if found is None:
        close = difflib.get_close_matches(code, sorted(explain.all_codes()), n=3, cutoff=0.5)
        hint = f"did you mean: {', '.join(close)}" if close else NO_MATCH_HINT
        raise CliError("FEN-2001", f"unknown code {code!r}", hint=hint, where=code)
    severities = explain.all_codes().get(found.family or code, ())
    return Result(
        result={
            "code": found.code,
            "kind": found.kind,
            "exit_code": int(REGISTRY[code].exit_code) if code in REGISTRY else None,
            "severities": list(severities),
            "meaning": found.meaning,
            "fix": found.fix,
            "see": found.see,
            "family": found.family or None,
        }
    )


COMMAND = Command(
    name="explain",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=("FEN-4001",),
)
