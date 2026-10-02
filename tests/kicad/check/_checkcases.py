# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0013 (capability kicad-oracle, "Subcommand matrix from help text", "Check project
copy set" and "Check canary injection"): the ``check-*`` rows of ``_probes.PROBES``.

Each probe runs once per session through ``_probes.run``; ``tests/kicad/test_probe_results.py`` pins the
outcomes per ``kicad-cli`` version.
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
from collections import Counter
from collections.abc import Callable
from functools import cache
from pathlib import Path

from _projects import STEM, authored_project, native_project

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.canary import (
    append_rule,
    canary_fired,
    canary_rule_text,
    inject_board,
    strip_canary,
)
from fenolite.backends.kicad.cli import DrcRun, KicadCli
from fenolite.backends.kicad.helpmatrix import MATRIX, CommandMatrix, command_matrix, probe_id, row_key
from fenolite.backends.kicad.projectset import project_set

UNMIRRORED = Path(__file__).resolve().parents[2] / "data" / "kicad" / "sexpr" / "unmirrored"

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


@cache
def matrix() -> CommandMatrix:
    """The command matrix of the running ``kicad-cli``, read once per session."""
    return command_matrix(runner())


def help_row(command: tuple[str, ...], option: str = "") -> str:
    """``present`` or ``absent`` for a matrix row; ``inconclusive`` when its page did not parse."""
    found = matrix().rows.get(row_key(command, option))
    if found is None:
        return "inconclusive"
    return "present" if found else "absent"


def help_probes() -> Probes:
    probes: Probes = {}
    for entry in MATRIX:
        probes[probe_id(entry.command)] = (lambda c=entry.command: help_row(c), (9, 10))
        for option in entry.options:
            probes[probe_id(entry.command, option)] = (
                lambda c=entry.command, o=option: help_row(c, o),
                (9, 10),
            )
    return probes


def violations(report: DrcReport) -> Counter[tuple[str, str, bool, tuple[str, ...]]]:
    """The multiset of (type, severity, excluded, sorted item uuids) over violations and unconnected items."""
    return Counter(
        (v.type, v.severity, v.excluded, tuple(sorted(i.uuid for i in v.items)))
        for v in (*report.violations, *report.unconnected_items)
    )


def workdir(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"fenolite-{prefix}-"))


@cache
def copyset() -> str:
    """``H-K-CHECK-COPYSET``: DRC on the copy set equals DRC on a copy of the whole project folder, for
    the authored built project with a KiCad-written ``.kicad_prl``, a ``sym-lib-table`` and ``notes.txt``."""
    cli = runner()
    root = authored_project(workdir("copyset"), major=cli.major(), built=True, cli=cli)
    project = project_set(root)
    board = root / project.board
    planned = cli.drc(board, files={k: v for k, v in project.files.items() if k != project.board})
    folder = {p.name: p for p in sorted(root.iterdir()) if p.name != board.name}
    return compare(planned.report, lambda: cli.drc(board, files=folder).report)


def compare(subject: DrcReport | None, reference: Callable[[], DrcReport | None]) -> str:
    """``equal`` or ``different`` for ``subject`` against a reference run that KiCad repeats identically.

    The reference runs twice. KiCad can report a violation in some runs only (observed on 10.0.6 for a
    track clearance next to a pad short), so when the two reference runs differ the outcome is
    ``inconclusive``, never a false ``different``.
    """
    first, second = reference(), reference()
    if subject is None or first is None or second is None or violations(first) != violations(second):
        return "inconclusive"
    return "equal" if violations(subject) == violations(first) else "different"


def plain_drc(root: Path) -> DrcRun:
    """DRC on the copy set of ``root``, without the canary."""
    project = project_set(root)
    board = root / project.board
    return runner().drc(board, files={k: v for k, v in project.files.items() if k != project.board})


def canary_drc(root: Path) -> DrcRun:
    """DRC on the copy set of ``root`` with the canary injected into staged copies of board and rules."""
    cli = runner()
    project = project_set(root)
    text = canary_rule_text(cli.major())
    assert text is not None, "the net selector is unproven on this major"
    stage = workdir("canary-stage")
    board = stage / project.board
    board.write_bytes(inject_board((root / project.board).read_bytes()))
    files = {k: v for k, v in project.files.items() if k != project.board}
    rules = f"{Path(project.board).stem}.kicad_dru"
    (stage / rules).write_bytes(append_rule((root / rules).read_bytes(), text, major=cli.major()))
    files[rules] = stage / rules
    return cli.drc(board, files=files)


@cache
def projects() -> tuple[Path, ...]:
    """The authored built project of the running major and the native ``two_layer`` project."""
    folder = workdir("canary")
    return authored_project(folder, major=runner().major(), built=True), native_project(folder)


@cache
def canary_fires() -> str:
    """``present`` when every project's canary run holds exactly one canary ``clearance`` violation."""
    outcomes: list[str] = []
    for root in projects():
        report = canary_drc(root).report
        if report is None:
            return "inconclusive"
        pairs = [v for v in report.violations if canary_fired(dataclasses.replace(report, violations=(v,)))]
        outcomes.append("present" if len(pairs) == 1 else "absent")
    return "present" if set(outcomes) == {"present"} else "absent"


@cache
def canary_neutral() -> str:
    """``equal`` when every project's stripped canary run reports what a run without the canary reports."""
    outcomes: set[str] = set()
    for root in projects():
        staged = canary_drc(root).report
        stripped = None if staged is None else strip_canary(staged)[0]
        outcomes.add(compare(stripped, lambda root=root: plain_drc(root).report))
    for outcome in ("inconclusive", "different"):
        if outcome in outcomes:
            return outcome
    return "equal"


def _fired_on(root: Path) -> str:
    report = canary_drc(root).report
    if report is None:
        return "inconclusive"
    return "present" if canary_fired(report) else "absent"


@cache
def canary_broken() -> str:
    """The canary of a project whose rules file KiCad drops (``broken.kicad_dru``, ``H-K-DRU-QUOTE``)."""
    return _fired_on(authored_project(workdir("canary-broken"), major=runner().major(), rules="broken"))


@cache
def canary_ignored() -> str:
    """The canary of a project that sets the ``clearance`` severity to ``ignore``."""
    root = authored_project(workdir("canary-ignored"), major=runner().major(), built=True)
    path = root / f"{STEM}.kicad_pro"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rule_severities", {})
    data["board"]["design_settings"]["rule_severities"]["clearance"] = "ignore"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return _fired_on(root)


def refused_board(name: str, major: int) -> bytes:
    """An ``unmirrored`` board that Fenolite refuses, its header rewritten to ``20241229`` for 9.0."""
    data = (UNMIRRORED / name).read_bytes()
    return data.replace(b"(version 20260206)", b"(version 20241229)", 1) if major < 10 else data


@cache
def unparsed_drc() -> str:
    """Whether KiCad reports on ``trailing-content.kicad_pcb`` (supporting data for ``H-K-SEXPR-STRICT``)."""
    root = workdir("unparsed")
    board = root / f"{STEM}.kicad_pcb"
    board.write_bytes(refused_board("trailing-content.kicad_pcb", runner().major()))
    return "present" if runner().drc(board).report is not None else "absent"


def check_probes() -> Probes:
    both = (9, 10)
    return {
        **help_probes(),
        "check-copyset": (copyset, both),
        "check-canary-fired": (canary_fires, both),
        "check-canary-neutral": (canary_neutral, both),
        "check-canary-broken": (canary_broken, both),
        "check-canary-ignored": (canary_ignored, both),
        "check-unparsed-drc": (unparsed_drc, both),
    }


__all__ = [
    "canary_drc",
    "check_probes",
    "copyset",
    "help_row",
    "matrix",
    "plain_drc",
    "projects",
    "refused_board",
    "violations",
    "workdir",
]
