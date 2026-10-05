# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""RT2 for schematics over the corpus (capability kicad-oracle, "Schematic RT2 over the corpus";
``H-K-ERC-REPEAT-2`` and ``H-K-ERC-RT2-2``; change c0062).

For every corpus project the running major loads, KiCad's ERC runs twice on the project as it is and once
on a copy in which every sheet Fenolite reads is its re-dump. KiCad does not repeat its report item by
item: for one violation it can name another of the pins or labels involved in each run. The runs are
therefore compared by ``ErcReport.kinds()``, the sheet, type, severity and exclusion of every violation.
A project is judged when its two runs of the original have equal kinds, and RT2 holds when the re-dump
has the kinds of the first run; a project that is not judged never fails. ``exact`` records whether the
items agreed too, as information. Each project is rebuilt in ``tmp_path`` from the cached rows; ids and
counts only go to the JSON file named by ``FENOLITE_CENSUS_OUT``.
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path, PurePosixPath

import _schcorpus
import _schprojects
import pytest
from _boards import census
from _corpus import manifest_items, require
from _probes import major, runner

from fenolite.backends.base import ErcReport
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.projectset import project_set

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus, pytest.mark.slow]
ROOTS = tuple(sorted({r.id: r for m in (9, 10) for r in _schprojects.roots(m)}.values(), key=lambda r: r.id))
"""Every root row of either tag; a test skips the rows that are no project of the running major."""
SECTION = "schematic_rt2"


def first_difference(before: ErcReport, after: ErcReport) -> str:
    """The first kind of violation that the two reports hold in other numbers, as text."""
    ours, theirs = Counter(before.kinds()), Counter(after.kinds())
    for kind in sorted(set(ours) | set(theirs)):
        if ours[kind] != theirs[kind]:
            return (
                f"{kind[1]} ({kind[2]}) on {kind[0]}: {ours[kind]} in the original, "
                f"{theirs[kind]} in the re-dump"
            )
    return "no difference of kinds"


@pytest.mark.parametrize("row", ROOTS, ids=lambda r: r.id)
def test_rt2(row: _schcorpus.SchRow, tmp_path: Path) -> None:
    running = major()
    if row.id not in {r.id for r in _schprojects.roots(running)}:
        pytest.skip(f"no project at tag {_schprojects.MAJOR_TAGS[running]}")
    require(next(i for i in manifest_items("sch") if i.id == row.id))
    if not _schprojects.loadable(row, running):
        pytest.skip(f"a sheet of the project is newer than KiCad {running} reads")
    root = _schprojects.project_folder(tmp_path, row, running)
    assert root is not None
    stem = PurePosixPath(row.path).stem
    project = project_set(root / f"{stem}.kicad_pcb")
    accepted = _schprojects.acceptance(row)
    started = time.perf_counter()
    outcome = KicadOracle(runner()).rt2_erc(project)
    record: dict[str, object] = {
        "major": running,
        "acceptance": accepted,
        "sheets": sum(1 for name in project.files if name.endswith(".kicad_sch")),
        "redumped": outcome.redumped,
        "kept": outcome.kept,
        "seconds": round(time.perf_counter() - started, 1),
    }
    if len(outcome.before) < 2 or outcome.after is None:
        census(SECTION, row.id, {**record, "verdict": "no-report", "judged": False})
        assert not accepted, f"{row.id}: no ERC report ({outcome.message})"
        pytest.skip(f"kicad-cli wrote no ERC report: {outcome.message}")
    first, second, after = outcome.before[0], outcome.before[1], outcome.after
    judged = first.kinds() == second.kinds()
    holds = judged and after.kinds() == first.kinds()
    exact = first.entries() == second.entries() == after.entries()
    verdict = ("holds" if holds else "differs") if judged else "not-judged"
    census(
        SECTION,
        row.id,
        {
            **record,
            "verdict": verdict,
            "judged": judged,
            "exact": exact,
            "violations": len(first.violations),
            "violations_redump": len(after.violations),
            "report_sheets": len(first.sheets),
        },
    )
    if judged:
        assert holds, f"{row.id}: RT2 differs: {first_difference(first, after)}"
    assert judged or not accepted, (
        f"{row.id}: on the acceptance list and not judged (the kinds of two runs differ)"
    )
