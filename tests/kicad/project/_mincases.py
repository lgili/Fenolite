# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board-setup minimum runs (c0026 Decision 10): each run builds the bench with ``write_triad``, sets the
keys the run names, runs ``pcb drc`` once per session through ``KicadCli`` on a temporary copy, and is
judged by ``_minimum_bench``. The ``pro-min-*`` probes of ``_probes.PROBES`` record the outcomes."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _minimum_bench as mb

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import CliRun, KicadCli
from fenolite.model.design import Design

BOARD = f"{mb.NAME}.kicad_pcb"


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


@dataclass(frozen=True)
class Run:
    design: Design
    report: DrcReport | None
    run: CliRun


@cache
def run(name: str, target: int) -> Run:
    """``pcb drc`` on the bench files of run ``name`` for ``target`` (once per session)."""
    design = mb.bench_design(target=target, board_wide=name.startswith("rules"))
    files = mb.run_files(name, target)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for file, text in files.items():
            (folder / file).write_text(text, encoding="utf-8")
        extra = {n: folder / n for n in files if n != BOARD}
        result = runner().drc(folder / BOARD, files=extra)
    return Run(design, result.report, result.run)


def item(name: str, kind: str, target: int) -> str:
    result = run(name, target)
    return mb.judge_item(result.report, kind=kind, design=result.design)


def hv(name: str, target: int) -> str:
    result = run(name, target)
    return mb.judge_class(result.report, design=result.design)


def min_probes() -> dict[str, tuple[object, tuple[int, ...]]]:
    """``probe id → (function, majors)``: target-10 runs on major 10, target-9 runs on both."""
    probes: dict[str, tuple[object, tuple[int, ...]]] = {}
    for target, majors in ((10, (10,)), (9, (9, 10))):
        for name in mb.RUNS:
            for kind in mb.KINDS:
                probes[f"pro-min-{name}-{kind}-t{target}"] = (
                    lambda name=name, kind=kind, target=target: item(name, kind, target),
                    majors,
                )
        probes[f"pro-min-class-t{target}"] = (lambda target=target: hv("rules-lowered", target), majors)
        probes[f"pro-min-class-control-t{target}"] = (
            lambda target=target: hv("keys-template", target),
            majors,
        )
    return probes


__all__ = ["Run", "hv", "item", "min_probes", "run"]
