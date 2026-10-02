# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check PATH``: the read-only check of a KiCad project, with evidence per stage (capability
verification-loop; ``docs/cli-contract.md``, "check").

The board is found from ``PATH``, its copy set planned, and the stages of ``fenolite.checks`` run with the
backend as ``Validator`` and ``kicad-cli`` as ``Oracle``. Nothing is written: ``kicad-cli`` only sees copies.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from fenolite.backends import registry
from fenolite.backends.base import Validator
from fenolite.backends.kicad import versions
from fenolite.backends.kicad.cli import KicadCli, KicadCliError, find_kicad_cli
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.projectset import project_set, resolve_board
from fenolite.backends.kicad.sexpr import parse_bytes
from fenolite.checks import STAGE_ORDER, run_checks
from fenolite.checks.stages import relative_file
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FenoliteError, FormatError, Issue
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design

HELP = "check a KiCad project read-only: model, ERC lite, KiCad DRC with a rules canary, round trip"
DEFAULT_TIMEOUT = 300.0
BUILT_MARKERS = ("meta.json", "build.json")
NO_TOOL_HINT = (
    "install KiCad 9 or 10, set FENOLITE_KICAD_CLI or pass --kicad-cli, or run "
    "--stages model.validate,erc.lite,roundtrip"
)


class ReadRefusedError(FormatError):
    """Fenolite cannot read the board and no DRC report exists; carries the check's issues."""

    def __init__(self, error: FormatError, issues: tuple[Issue, ...], *, file: str = "") -> None:
        super().__init__(error.message, file=file or error.file, locator=error.locator, offset=error.offset)
        hint = getattr(error, "hint", "")
        self.hint = hint if isinstance(hint, str) else ""
        self.issues = issues


class UnsupportedReadRefusedError(ReadRefusedError):
    """``ReadRefusedError`` for a board older than the read floor."""

    cli_code = "FEN-3003"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'check'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument(
        "--stages", metavar="A,B", help=f"stages to run (default all: {','.join(STAGE_ORDER)})"
    )
    parser.add_argument("--kicad-cli", dest="kicad_cli", metavar="PATH", help="the kicad-cli to run")
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS", help="kicad-cli timeout (300)"
    )


def _stages(text: str | None) -> tuple[str, ...]:
    if text is None:
        return STAGE_ORDER
    names = [name.strip() for name in text.split(",")]
    bad = [name for name in names if name not in STAGE_ORDER]
    if not names or bad:
        shown = ", ".join(repr(n) for n in bad) if any(bad) else "an empty stage name"
        raise CliError("FEN-2001", f"unknown stage {shown}", hint=f"stages: {','.join(STAGE_ORDER)}")
    return tuple(names)


def _relative(text: str, root: Path) -> str:
    for spelling in sorted({str(root.resolve()), str(root)}, key=len, reverse=True):
        text = text.replace(spelling + "/", "").replace(spelling, ".")
    return text


def _cache(root: Path) -> tuple[bool, Design | None, str]:
    """``(built, model, cache_error)`` from ``<root>/.fenolite/``."""
    cache = root / ".fenolite"
    if not any((cache / marker).is_file() for marker in BUILT_MARKERS):
        return False, None, ""
    try:
        return True, load_dir(cache), ""
    except (OSError, ValueError, KeyError, TypeError, FenoliteError) as exc:
        return True, None, _relative(f"{type(exc).__name__}: {exc}", root)


def _oracle(args: argparse.Namespace, board: Path) -> KicadOracle:
    """The pre-flight of ``drc.kicad``: a supported ``kicad-cli`` that reads this board's format."""
    path = find_kicad_cli(args.kicad_cli)
    if path is None:
        raise CliError("FEN-6001", "kicad-cli not found", hint=NO_TOOL_HINT)
    cli = KicadCli(path, timeout=args.timeout)
    try:
        major = cli.major()
    except (KicadCliError, ValueError) as exc:
        raise CliError(
            "FEN-6001", f"{path.name} did not report a kicad-cli version", hint=NO_TOOL_HINT
        ) from exc
    if major not in versions.TARGET_MAJORS:
        raise CliError("FEN-6002", f"kicad-cli {cli.version()} is not supported",
                       hint=f"use kicad-cli {' or '.join(map(str, versions.TARGET_MAJORS))}")  # fmt: skip
    try:
        info = versions.inspect(parse_bytes(board.read_bytes(), file=board.name), file=board.name)
    except (FormatError, OSError):
        info = None  # the header check is skipped; KiCad decides
    limit = versions.FORMAT_VERSIONS[versions.FileKind.BOARD][major]
    if info is not None and (info.status is versions.VersionStatus.FUTURE or info.version > limit):
        raise CliError("FEN-6002", f"{board.name} (format {info.version}) is newer than kicad-cli "
                       f"{cli.version()} reads", hint="run a newer kicad-cli")  # fmt: skip
    return KicadOracle(cli)


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    stages = _stages(args.stages)
    given = Path(args.path)
    board = resolve_board(given if given.is_absolute() else ctx.cwd / given)
    root = board.parent
    project = project_set(board)
    backend = registry.for_path(board)
    if not isinstance(backend, Validator):
        raise CliError("FEN-2001", f"no backend validates {board.name}", hint="pass a KiCad .kicad_pcb")
    built, model, cache_error = _cache(root)
    oracle = _oracle(args, board) if "drc.kicad" in stages else None
    report = run_checks(project=project, stages=stages, model=model, built=built, validator=backend,
                        oracle=oracle, cache_error=cache_error)  # fmt: skip
    error = report.read_error
    if isinstance(error, FormatError) and not report.drc_reported:
        old = isinstance(error, versions.UnsupportedFormatError)
        refusal = UnsupportedReadRefusedError if old else ReadRefusedError
        raise refusal(error, report.issues, file=relative_file(error.file, root))
    result: dict[str, Any] = {
        "project": {
            "board": project.board,
            "built": built,
            "files": sorted(project.files),
            "skipped": [
                {"name": s.name, "reason": s.reason} for s in sorted(project.skipped, key=lambda s: s.name)
            ],
        },
        "stages": [stage.to_json() for stage in report.stages],
    }
    data = board.read_bytes()
    return Result(
        result=result,
        issues=report.issues,
        evidence=report.evidence,
        input=InputRef(
            path=board.name, sha256=hashlib.sha256(data).hexdigest(), kind="kicad_pcb", format_version=None
        ),  # fmt: skip
    )


COMMAND = Command(
    name="check",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD, "--stages", "model.validate,erc.lite,roundtrip"),
)
