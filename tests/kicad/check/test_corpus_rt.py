# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""RT0, RT1 and RT2 over the corpus (capability kicad-oracle, "Corpus round trips RT0 to RT2"; v0.1
acceptance item 2; ``H-K-RT2-STABLE-2``).

On major 10 the set is the 21 readable non-heavy demo boards and the ``pcb upgrade`` copies of the three
third-party boards; on major 9 it is exactly the rows tagged ``rt2-9``. Each board is checked in a folder
that ``demo_project`` writes into ``tmp_path``; the cache is only read. With ``FENOLITE_CENSUS_OUT`` the
verdicts and counts of each board are recorded for ``docs/evidence/kicad-rt2.md`` (ids and counts only).

RT2 never fails on a board whose own DRC report KiCad does not repeat: the stage then says that it is not
judged (``summary.judged`` false), which the record keeps per board.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest
from _boardcorpus import OLD_ITEMS, READABLE_ITEMS
from _boards import census
from _corpus import CorpusItem
from _probes import major, runner
from _projects import STEM, demo_project, upgraded_project
from _resources import corpus_cache_dir, required_resources

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.projectset import project_set
from fenolite.backends.kicad.sexpr import dumps, parse, tree_equal
from fenolite.checks import run_checks

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus, pytest.mark.slow]
RT2_9 = "rt2-9"
NOT_NORMALISED = frozenset({"third-party-pcb-02"})
"""Boards whose two ``pcb upgrade`` copies differ (``H-K-FMT-RESAVE``); the upgraded copy is still the
input."""
ITEMS = [i for i in (*READABLE_ITEMS, *OLD_ITEMS) if not i.heavy]


def _project(tmp_path: Path, item: CorpusItem) -> Path:
    """The board in a ``demo_project`` folder: as cached, or re-saved once when it is below the read
    floor."""
    running = major()
    if running < 10:
        if RT2_9 not in item.uses:
            pytest.skip(f"{item.id} is not an rt2-9 row")
        cache = corpus_cache_dir()
        present = cache.is_dir() and any(cache.iterdir())
        if not item.path.is_file() and present and "kicad" in required_resources():
            pytest.fail(f"rt2-9 row {item.id} is missing from the corpus cache", pytrace=False)
        return demo_project(tmp_path, item)
    return upgraded_project(tmp_path, item, runner()) if item in OLD_ITEMS else demo_project(tmp_path, item)


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i.id)
def test_rt2(item: CorpusItem, tmp_path: Path) -> None:
    root = _project(tmp_path, item)
    cached = hashlib.sha256(item.path.read_bytes()).hexdigest()
    text = (root / f"{STEM}.kicad_pcb").read_text(encoding="utf-8")
    tree = parse(text)
    rt0 = tree_equal(parse(dumps(tree)), tree)
    oracle = KicadOracle(runner(), rt2_normalise=item.id not in NOT_NORMALISED)
    started = time.monotonic()
    report = run_checks(
        project=project_set(root),
        stages=("roundtrip", "roundtrip.rt2"),
        model=None,
        built=False,
        validator=KicadBackend(),
        oracle=oracle,
    )
    seconds = round(time.monotonic() - started, 1)
    rt1, rt2 = report.stages
    census(
        "rt2",
        f"{major()}:{item.id}",
        {
            "origin": item.origin,
            "rt0": rt0,
            "rt1": rt1.status,
            "rt2": rt2.status,
            "opaque_count": rt1.summary.get("opaque_count"),
            "normalised": rt2.summary.get("normalised"),
            "before": rt2.summary.get("before"),
            "after": rt2.summary.get("after"),
            "judged": rt2.summary.get("judged"),
            "runs": rt2.summary.get("runs"),
            "unstable": rt2.summary.get("unstable"),
            "differences": rt2.summary.get("differences"),
            "seconds": seconds,
        },
    )
    assert hashlib.sha256(item.path.read_bytes()).hexdigest() == cached  # the cache is only read
    assert rt0, f"{item.id}: RT0 failed"
    assert rt1.status == "ok" and rt1.summary["opaque_equal"] is True, (item.id, rt1.issues)
    assert rt2.status == "ok", (item.id, [i.message for i in rt2.issues if i.severity == "error"][:5])
    # RT2 holds, or KiCad did not repeat its own report here and the stage says it is not judged
    assert rt2.summary["holds"] is True or (rt2.summary["judged"] is False and rt2.summary["unstable"] > 0)
    assert rt2.summary["normalised"] is (major() >= 10 and item.id not in NOT_NORMALISED)
