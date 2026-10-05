# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""RT2 for schematics over the corpus (capability kicad-oracle, "Schematic RT2 over the corpus";
``H-K-ERC-REPEAT`` and ``H-K-ERC-RT2``; change c0062).

For every corpus project the running major loads, KiCad's ERC runs twice on the project as it is and once
on a copy in which every sheet Fenolite reads is its re-dump. RT2 holds when the re-dump gives the
violations of the original. A project whose two runs of the original differ is not judged, and never
failed; a difference of the re-dump fails only when two further attempts give it again. Each project is
rebuilt in ``tmp_path`` from the cached rows; ids and counts only go to the JSON file named by
``FENOLITE_CENSUS_OUT``.
"""

from __future__ import annotations

import time
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
RETRIES = 2
"""Further attempts for a project whose re-dump differs once, before the difference is believed."""


def first_difference(before: ErcReport, after: ErcReport) -> str:
    """The first entry that only one of the two reports holds, as text."""
    ours, theirs = list(before.entries()), list(after.entries())
    for entry in sorted(set(ours) ^ set(theirs)):
        side = "original" if entry in ours else "re-dump"
        return f"only the {side} reports {entry[1]} ({entry[2]}) on {entry[0]}: {entry[4]}"
    return "the same entries in other numbers"


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
    first, second = outcome.before[0], outcome.before[1]
    judged = first.entries() == second.entries()
    holds = outcome.after.entries() == first.entries()
    for _ in range(RETRIES if judged and not holds else 0):
        # KiCad's ERC is not repeatable on every project (H-K-ERC-REPEAT): a difference counts only
        # when it comes back on each further attempt, and one attempt that holds settles it.
        again = KicadOracle(runner()).rt2_erc(project)
        if len(again.before) < 2 or again.after is None:
            judged = False
            break
        judged = again.before[0].entries() == again.before[1].entries() == first.entries()
        holds = judged and again.after.entries() == first.entries()
        if holds or not judged:
            break
    record["seconds"] = round(time.perf_counter() - started, 1)
    verdict = ("holds" if holds else "differs") if judged else "not-judged"
    census(
        SECTION,
        row.id,
        {
            **record,
            "verdict": verdict,
            "judged": judged,
            "violations": len(first.violations),
            "violations_redump": len(outcome.after.violations),
            "report_sheets": len(first.sheets),
        },
    )
    if judged:
        assert holds, f"{row.id}: RT2 differs: {first_difference(first, outcome.after)}"
    assert judged or not accepted, f"{row.id}: on the acceptance list and not judged (two runs differ)"
