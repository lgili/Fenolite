# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check PATH``: the read-only check of a KiCad project, with evidence per stage (capability
verification-loop; ``docs/cli-contract.md``, "check").

The board is found from ``PATH``, its copy set planned, and the stages of ``fenolite.checks`` run with the
backend as ``Validator`` and ``kicad-cli`` as ``Oracle``. Nothing is written: ``kicad-cli`` only sees copies.

Document input (change c0044) is looked for first: a file or a project folder of a backend whose project is
a set of documents (an Altium document, library, project file or project folder). It is checked by
``checks.documents.run_document_checks`` without any external tool.
"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.backends import registry
from fenolite.backends.base import DocumentSet, DocumentValidator, ProjectSet, Validator
from fenolite.backends.kicad import versions
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.projectset import project_set, resolve_board
from fenolite.checks import DEFAULT_STAGES, ORACLE_STAGES, STAGE_ORDER, run_checks
from fenolite.checks.documents import DOCUMENT_STAGES, run_document_checks
from fenolite.checks.stages import CheckReport, relative_file
from fenolite.cli._documents import built_cache, find_documents, input_ref, project_result
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, preflight
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.model.design import Design

HELP = (
    "check a KiCad project (model, KiCad ERC and DRC findings, pad nets, round trips) or an Altium "
    "project or document (model, ERC lite, pad nets, round trips RT-A0 to RT-A2), read-only"
)
NO_TOOL_HINT = (
    "install KiCad 9 or 10, set FENOLITE_KICAD_CLI or pass --kicad-cli, or run "
    "--stages model.validate,roundtrip"
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
    parser.add_argument(
        "path",
        metavar="PATH",
        help="a .kicad_pcb, a .kicad_pro or a project folder; an Altium document, .PrjPcb or project folder",
    )
    parser.add_argument(
        "--stages",
        metavar="A,B",
        help=f"stages to run, of {','.join(STAGE_ORDER)} (default: {','.join(DEFAULT_STAGES)}); "
        f"for Altium input, of {','.join(DOCUMENT_STAGES)} (default: all)",
    )
    parser.add_argument(
        "--kicad-cli", dest="kicad_cli", metavar="PATH", help="the kicad-cli to run (unused for Altium input)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help="kicad-cli timeout (300; unused for Altium input)",
    )


def parse_stages(text: str | None) -> tuple[str, ...]:
    """The stages that ``--stages`` names, or the default ones; ``FEN-2001`` for an unknown name."""
    if text is None:
        return DEFAULT_STAGES
    names = [name.strip() for name in text.split(",")]
    bad = [name for name in names if name not in STAGE_ORDER]
    if not names or bad:
        shown = ", ".join(repr(n) for n in bad) if any(bad) else "an empty stage name"
        raise CliError("FEN-2001", f"unknown stage {shown}", hint=f"stages: {','.join(STAGE_ORDER)}")
    return tuple(names)


def _document_stages(text: str | None) -> tuple[str, ...]:
    if text is None:
        return DOCUMENT_STAGES
    names = [name.strip() for name in text.split(",")]
    bad = [name for name in names if name not in DOCUMENT_STAGES]
    if not names or bad:
        shown = ", ".join(repr(n) for n in bad) if any(bad) else "an empty stage name"
        raise CliError(
            "FEN-2001",
            f"unknown stage {shown} for document input",
            hint=f"stages: {','.join(DOCUMENT_STAGES)}",
        )
    return tuple(names)


def _cache(root: Path) -> tuple[bool, Design | None, str]:
    """``(built, model, cache_error)`` from ``<root>/.fenolite/``."""
    return built_cache(root)


def _run_documents(
    args: argparse.Namespace, path: Path, backend: DocumentValidator, documents: DocumentSet
) -> Result:
    """The check of document input (capability altium-verification, "Check on Altium inputs"): no oracle is
    built and no subprocess runs; ``--kicad-cli`` and ``--timeout`` are accepted and ignored."""
    stages = _document_stages(args.stages)
    built, model, cache_error = built_cache(documents.root)
    report = run_document_checks(
        documents=documents,
        stages=stages,
        model=model,
        built=built,
        validator=backend,
        cache_error=cache_error,
    )
    error = report.read_error
    if isinstance(error, FormatError):
        raise ReadRefusedError(error, report.issues, file=documents.documents[0].name)
    result: dict[str, Any] = {
        "project": project_result(backend, documents, built=built),
        "stages": [stage.to_json() for stage in report.stages],
    }
    return Result(
        result=result, issues=report.issues, evidence=report.evidence, input=input_ref(path, documents)
    )


@dataclass(frozen=True, slots=True)
class Checked:
    """One run of the stages on a project: its copy set, whether Fenolite built it, the report, and the
    version of the ``kicad-cli`` that ran (``None`` when no stage needed it)."""

    project: ProjectSet
    built: bool
    report: CheckReport
    tool_version: str | None


def run_stages(
    board: Path, stages: tuple[str, ...], *, kicad_cli: str | None, timeout: float, hint: str = NO_TOOL_HINT
) -> Checked:
    """Run ``stages`` on the project of ``board`` as ``fenolite check`` does: the pre-flight of the
    ``ORACLE_STAGES`` (a supported ``kicad-cli`` that reads this board's format, else ``FEN-6001`` or
    ``FEN-6002`` with ``hint``), the ``.fenolite/`` model of a built project, and the refusal of a board
    that Fenolite cannot read when no DRC report exists. ``fenolite manifest`` reads its states from it."""
    root = board.parent
    project = project_set(board)
    backend = registry.for_path(board)
    if not isinstance(backend, Validator):
        raise CliError("FEN-2001", f"no backend validates {board.name}", hint="pass a KiCad .kicad_pcb")
    built, model, cache_error = _cache(root)
    oracle = None
    if set(ORACLE_STAGES) & set(stages):
        oracle = KicadOracle(preflight(kicad_cli, timeout, board, hint=hint))
    report = run_checks(project=project, stages=stages, model=model, built=built, validator=backend,
                        oracle=oracle, cache_error=cache_error,
                        plotter=oracle if "render" in stages else None,
                        fill_oracle=oracle if "zone.fill" in stages else None)  # fmt: skip
    error = report.read_error
    if isinstance(error, FormatError) and not report.drc_reported:
        old = isinstance(error, versions.UnsupportedFormatError)
        refusal = UnsupportedReadRefusedError if old else ReadRefusedError
        raise refusal(error, report.issues, file=relative_file(error.file, root))
    return Checked(project, built, report, None if oracle is None else oracle.version())


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given = Path(args.path)
    path = given if given.is_absolute() else ctx.cwd / given
    found = find_documents(path)
    if found is not None:
        return _run_documents(args, path, *found)
    stages = parse_stages(args.stages)
    board = resolve_board(path)
    checked = run_stages(board, stages, kicad_cli=args.kicad_cli, timeout=args.timeout)
    project, built, report = checked.project, checked.built, checked.report
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
    paged="issues",
    example_args=(EXAMPLE_BOARD, "--stages", "model.validate,roundtrip"),
)
