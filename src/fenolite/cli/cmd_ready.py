# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite ready PATH``: whether a KiCad project is electrically ready for fabrication, in one read-only
reply (capability cli-contract, "Ready command" to "Ready example and documentation"; change c0098;
``docs/cli-contract.md``, "ready").

Nothing here is computed twice. The open connections are those of ``analysis.connectivity`` on the board
that ``fenolite net`` reads; ERC and DRC are the ``erc.kicad`` and ``drc.kicad`` stages of ``check``, run
through ``cmd_check.run_stages`` with its pre-flight; a missing footprint is the rule of ``model.validate``.
``checks.readiness`` adds three rules: unconnected pins, power nets without a declared width or a zone,
parts without a value. Exit 0 means no finding of severity ``error``; ``check`` stays the judge of a change.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from fenolite.analysis import connectivity as conn
from fenolite.backends import registry
from fenolite.backends.base import DesignRulesSource
from fenolite.backends.kicad.netlist import NO_CONNECT_SUFFIX
from fenolite.backends.kicad.projectset import project_set, resolve_board
from fenolite.checks import readiness
from fenolite.checks.codes import issue as check_issue
from fenolite.checks.readiness import ORACLE_CHECKS, OpenNet
from fenolite.checks.stages import StageResult
from fenolite.cli._boardview import BoardView, load_board
from fenolite.cli._documents import built_cache, find_documents
from fenolite.cli._examples import EXAMPLE_READY
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.cmd_check import run_stages
from fenolite.cli.errors import CliError
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design

HELP = (
    "say whether a KiCad project is electrically ready for fabrication: open nets, KiCad ERC and DRC, "
    "unconnected pins, power nets without a width or a zone, parts without a footprint or a value (read-only)"
)
NO_TOOL_HINT = (
    "install KiCad 9 or 10, set FENOLITE_KICAD_CLI or pass --kicad-cli, or pass --no-kicad to report ERC "
    "and DRC as skipped"
)
SEVERITIES = ("error", "warning", "info")


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'ready'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument(
        "--no-kicad",
        dest="no_kicad",
        action="store_true",
        help="run no kicad-cli: ERC and DRC are reported as skipped",
    )
    parser.add_argument("--kicad-cli", dest="kicad_cli", metavar="PATH", help="the kicad-cli to run")
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS", help="kicad-cli timeout (300)"
    )


def _open_check(view: BoardView) -> StageResult:
    """``nets.open`` from the open connections of the board."""
    report = conn.connectivity(view.design, pads=view.pads)
    rows: list[OpenNet] = []
    for net in report.nets:
        if not net.open:
            continue
        shortest = min(net.open, key=lambda link: link.length)
        rows.append(OpenNet(net.name, len(net.open), shortest.length, shortest.a.where, shortest.b.where))
    evidence = Evidence.combine(view.evidence, report.evidence)
    return readiness.open_stage(rows, evidence=evidence, issues=(*view.issues, *report.issues))


def _kicad_checks(
    args: argparse.Namespace, board: Path, ctx: Context
) -> tuple[list[StageResult], list[Issue]]:
    """``erc.kicad`` and ``drc.kicad`` as ``check`` runs them, a skip turned into ``ready.check-skipped``,
    and the issues of the run that belong to no stage (a read refusal, an unreadable ``.fenolite/``)."""
    if args.no_kicad:
        return [readiness.skipped_check(name, "no-kicad") for name in ORACLE_CHECKS], []
    checked = run_stages(
        board, ORACLE_CHECKS, kicad_cli=args.kicad_cli, timeout=args.timeout, hint=NO_TOOL_HINT,
        progress=ctx.progress,
    )  # fmt: skip
    stages = {stage.name: stage for stage in checked.report.stages}
    found: list[StageResult] = []
    for name in ORACLE_CHECKS:
        stage = stages[name]
        found.append(readiness.skipped_check(name, stage.reason) if stage.status == "skipped" else stage)
    own = {i for stage in checked.report.stages for i in stage.issues}
    return found, [i for i in checked.report.issues if i not in own]


def _flagged(design: Design) -> frozenset[tuple[str, str]]:
    """The pins whose board pad KiCad marks with a no-connect flag (a ``pintype`` ending in
    ``+no_connect``, kept in the pin's ``ext`` by the board reader)."""
    return frozenset(
        (component.id, pin.number)
        for component in design.circuit.components
        for pin in component.pins
        if "kicad" in pin.ext
        and any(k == "pintype" and v.endswith(NO_CONNECT_SUFFIX) for k, v in pin.ext["kicad"].payload)
    )


def _intent(view: BoardView, board: Path, issues: list[Issue]) -> tuple[Design, bool]:
    """The design the three rules judge, and whether it is the ``.fenolite/`` model of a built project:
    that model, else the board as read with the classes and rules of the project's files."""
    built, model, cache_error = built_cache(board.parent)
    if cache_error:
        issues.append(check_issue("check.cache-unreadable", f".fenolite/ cannot be loaded: {cache_error}"))
    if built and model is not None:
        return model, True
    backend = registry.for_path(board)
    if isinstance(backend, DesignRulesSource):
        return backend.design_rules(view.design, project_set(board), issues=issues).design, built
    return view.design, built


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given = Path(args.path)
    path = given if given.is_absolute() else ctx.cwd / given
    if find_documents(path) is not None:
        raise CliError(
            "FEN-2001", f"fenolite ready reads a KiCad project, not {path.name}",
            hint="run fenolite check on Altium input", where=path.name,
        )  # fmt: skip
    board = resolve_board(path)
    view = load_board(str(path), ctx)
    opened = _open_check(view)
    (erc, drc), extra = _kicad_checks(args, board, ctx)
    intent, built = _intent(view, board, extra)
    checks = [
        opened,
        erc,
        drc,
        readiness.pins_stage(intent, flagged=_flagged(intent)),
        readiness.power_stage(intent, board=view.design),
        readiness.parts_stage(intent),
    ]
    issues = tuple(dict.fromkeys((*extra, *(i for check in checks for i in check.issues))))
    ran = [check.evidence for check in checks if check.status != "skipped"]
    result: dict[str, Any] = {
        "project": {"board": board.name, "built": built},
        "ready": not any(i.severity == "error" for i in issues),
        "complete": all(check.status != "skipped" for check in checks),
        "checks": [check.to_json() for check in checks],
        "counts": {severity: sum(1 for i in issues if i.severity == severity) for severity in SEVERITIES},
    }
    return Result(result=result, issues=issues, evidence=Evidence.combine(*ran), input=view.input)


COMMAND = Command(
    name="ready",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    paged="issues",
    example_args=(EXAMPLE_READY, "--no-kicad"),
)
