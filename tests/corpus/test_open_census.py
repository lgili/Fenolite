# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Census of the open connections of the corpus boards against KiCad's DRC (change c0108; capability
kicad-oracle, "Open connections agree with unconnected items", "Census"; ``H-K-CONN-PARITY``).

Per readable board: the total of ``analysis.connectivity``, the total of ``kicad-cli pcb drc`` and the
number of nets whose counts differ. A board whose KiCad total reaches the report's cap is compared as "at
least". The tests never fail on a count: the census is the record (``FENOLITE_CENSUS_OUT``;
``docs/evidence/routing.md``). Items are named by their manifest id only, and nets by their number.
"""

from __future__ import annotations

import re
from collections import Counter
from functools import cache
from pathlib import Path

import pytest
from _boardcorpus import READABLE_ITEMS, read
from _boards import census
from _corpus import CorpusItem, require
from _resources import kicad_cli

from fenolite.analysis.connectivity import connectivity
from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.sexpr import load, walk

pytestmark = [pytest.mark.needs_corpus, pytest.mark.needs_kicad]
CAP = 499
"""Where ``kicad-cli`` stops its list of unconnected items."""
DRAWINGS = ("gr_rect", "gr_poly", "gr_line", "gr_circle", "gr_arc", "gr_curve")
_NET = re.compile(r"\[([^\]]*)\]")
SECTION = "open-connections"


@cache
def drc_report(path: Path) -> DrcReport | None:
    cli = kicad_cli()
    assert cli is not None  # the needs_kicad marker skips before this is reached
    return KicadCli(Path(cli), timeout=900).drc(path).report


def kicad_counts(report: DrcReport) -> Counter[str]:
    """Net name → the unconnected items of the report whose items all name that net (KiCad writes the net
    of an item in square brackets in its description)."""
    counts: Counter[str] = Counter()
    for found in report.unconnected_items:
        names: set[str] = set()
        for item in found.items:
            match = _NET.findall(item.description)
            names.add(match[-1] if match else "")
        if len(names) == 1:
            counts[names.pop()] += 1
        else:
            counts[""] += 1
    return counts


@cache
def query_counts(path: Path) -> Counter[str]:
    design, _ = read(path)
    report = connectivity(design, pads=board_pads(design))
    return Counter({net.name: len(net.open) for net in report.nets if net.open})


@cache
def copper_drawings_with_net(path: Path) -> int:
    """The drawings on a copper layer that hold a net: copper for KiCad, not for the model."""
    count = 0
    for _locator, node in walk(load(path)):
        if node.name not in DRAWINGS:
            continue
        layer, net = node.find("layer"), node.find("net")
        on_copper = layer is not None and any(atom.value.endswith(".Cu") for atom in layer.atoms())
        named = net is not None and any(atom.text not in ("0", '""') for atom in net.atoms())
        count += 1 if on_copper and named else 0
    return count


@pytest.mark.parametrize("item", READABLE_ITEMS, ids=lambda i: i.id)
def test_kicad_counts(item: CorpusItem) -> None:
    """KiCad's unconnected items per board (DRC only, no query)."""
    path = require(item)
    report = drc_report(path)
    if report is None:
        census(SECTION, f"{item.id}/kicad", {"report": False})
        pytest.skip(f"{item.id}: kicad-cli wrote no DRC report")
    counts = kicad_counts(report)
    total = len(report.unconnected_items)
    census(
        SECTION,
        f"{item.id}/kicad",
        {"version": report.kicad_version, "total": total, "nets": len(counts), "capped": total >= CAP},
    )


@pytest.mark.parametrize("item", READABLE_ITEMS, ids=lambda i: i.id)
def test_query_against_kicad(item: CorpusItem) -> None:
    """The query's counts per net against KiCad's; recorded, never failed on a count."""
    path = require(item)
    report = drc_report(path)
    if report is None:
        pytest.skip(f"{item.id}: kicad-cli wrote no DRC report")
    theirs, ours = kicad_counts(report), query_counts(path)
    kicad_total = len(report.unconnected_items)
    capped = kicad_total >= CAP
    if capped:  # KiCad's list is cut: every net must hold at least what KiCad lists
        differing = sorted(name for name in theirs if ours[name] < theirs[name])
    else:
        differing = sorted(name for name in set(theirs) | set(ours) if theirs[name] != ours[name])
    drawings = copper_drawings_with_net(path)
    census(
        SECTION,
        f"{item.id}/parity",
        {
            "query": sum(ours.values()),
            "kicad": kicad_total,
            "compared": "at least" if capped else "equal",
            "nets_differing": len(differing),
            "copper_drawings_with_net": drawings,
        },
    )
    if differing:
        why = "copper drawings that hold a net" if drawings else "not explained"
        totals = f"query {sum(ours.values())}, KiCad {kicad_total}"
        print(f"{item.id}: {len(differing)} net(s) differ ({why}): {totals}")
