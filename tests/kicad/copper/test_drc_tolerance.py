# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's DRC tolerance on a copper clearance (``H-K-COPPER-EPSILON``; capability copper-check, "Clearance
tolerance of the tool", scenario "Measured against KiCad"; change c0281).

The authored parity benches of ``_copperparity`` are rebuilt here with rows at ``c − 500 nm`` and
``c − 501 nm`` instead of their usual ``c ± 10 µm``, under a custom rule, a class, a board minimum and the
class pair gap of a differential pair. KiCad must be clean on the first row and report ``clearance`` on the
second, and the copper check with the KiCad rules source's tolerance must agree on every row.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import _copperparity as cp
import pytest

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.copperrules import KICAD_DRC_EPSILON_NM, design_rules_from_texts
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.copper import check_copper

pytestmark = pytest.mark.needs_kicad

DELTAS = {"at-tolerance": -KICAD_DRC_EPSILON_NM, "past-tolerance": -KICAD_DRC_EPSILON_NM - 1}
EXPECTED = {-KICAD_DRC_EPSILON_NM: "clean", -KICAD_DRC_EPSILON_NM - 1: "clearance"}


@contextmanager
def tolerance_rows() -> Iterator[None]:
    """The bench builders with rows at the two deltas only (restored afterwards, so the cached parity
    benches of the other tests are untouched)."""
    saved_gaps, saved_boundary = cp.GAPS, cp.BOUNDARY
    cp.GAPS, cp.BOUNDARY = dict(DELTAS), {}
    try:
        yield
    finally:
        cp.GAPS, cp.BOUNDARY = saved_gaps, saved_boundary


BENCHES: dict[str, Callable[[int], cp.ParityBench]] = {
    "rule": lambda target: cp._rule_bench(target),  # pyright: ignore[reportPrivateUsage]
    "class": lambda target: cp._class_bench(target),  # pyright: ignore[reportPrivateUsage]
    "floor": lambda target: cp._floor_bench(target),  # pyright: ignore[reportPrivateUsage]
    "pair-class": lambda target: cp._pair_bench("class", target),  # pyright: ignore[reportPrivateUsage]
}


def fenolite_verdicts(bench: cp.ParityBench) -> dict[str, str]:
    design = read_board(bench.files[cp.BOARD], file=cp.BOARD)
    rules = design_rules_from_texts(
        design, project_text=bench.files[cp.PROJECT], rules_text=bench.files.get(cp.RULES),
        major=bench.target, file_stem=cp.NAME,
    )  # fmt: skip
    assert rules.clearance_tolerance == KICAD_DRC_EPSILON_NM
    report = check_copper(
        rules.design, pads=KicadBackend().board_pads(rules.design), min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes, floor_over_rules=rules.floor_over_rules,
        tolerance=rules.clearance_tolerance,
    )  # fmt: skip
    board = rules.design.board
    assert board is not None
    entities = [*board.tracks, *board.arcs, *board.vias]
    entities += [pad for footprint in board.footprints for pad in footprint.pads]
    uuid_of = {e.id: e.native_ids["kicad"] for e in entities if "kicad" in e.native_ids}
    verdicts: dict[str, str] = {}
    for row in bench.rows:
        a, b = (set(uuids) for uuids in bench.uuids(row))
        verdicts[row.label] = "clean"
        for finding in report.findings:
            first, second = (uuid_of.get(item.entity_id) for item in finding.items)
            if (first in a and second in b) or (first in b and second in a):
                verdicts[row.label] = cp.VERDICT.get(finding.code, "overlap")
    return verdicts


@pytest.mark.parametrize("source", sorted(BENCHES))
def test_kicad_tolerance(source: str) -> None:
    target = cp.running_target()
    with tolerance_rows():
        bench = BENCHES[source](target)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name, text in bench.files.items():
            (folder / name).write_text(text, encoding="utf-8")
        extra = {name: folder / name for name in bench.files if name != cp.BOARD}
        report = cp.runner().drc(folder / cp.BOARD, files=extra).report
    ours = fenolite_verdicts(bench)
    checked = 0
    for row in bench.rows:
        if row.group not in (*cp.KINDS, cp.pair_group("class")) or row.group == "arc-track":
            continue
        base = cp.CLEARANCE.get(source) if source in cp.CLEARANCE else cp.PAIR_CASES["class"]
        delta = row.gap - base
        if delta not in EXPECTED:
            continue
        kicad = cp.kicad_verdict(report, bench, row)
        print(f"{source} {row.group} c{delta:+d} nm: KiCad {kicad}, Fenolite {ours[row.label]}")
        assert kicad == EXPECTED[delta], (source, row.group, delta)
        assert ours[row.label] == kicad, (source, row.group, delta)
        checked += 1
    assert checked >= 2
