# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""RT-A0 and RT-A1 on every public Altium row (capability altium-verification, "Round trips over the corpus
and the samples"; change c0044; ``H-A-VER-RTA0``, ``-WRITER``, ``-RTA1``, ``-BYTES``).

Every row with the use ``rta`` is copied through the compound reader and writer (RT-A0) and encoded from
its records and read again (RT-A1). The census holds row ids, kinds, sizes, stream counts and record counts
only: no name and no value of a file.
"""

from __future__ import annotations

import time
import tomllib
from typing import Any
from urllib.parse import urlparse

import pytest
from _boards import census
from _corpus import MANIFEST, CorpusItem, corpus_items, manifest_items, require

from fenolite.backends.altium.docset import kind_of
from fenolite.backends.altium.read import cfb
from fenolite.backends.altium.roundtrip import COMPOUND_KINDS, rt_a0, rt_a1
from fenolite.core.errors import FormatError

pytestmark = pytest.mark.needs_corpus
ROWS = manifest_items("rta")
UNJUDGED = ("too-large", "writer-refused", "not-a-container")
READER_REFUSED: dict[str, str] = {}
"""Row id → the reader's hypothesis that the row refutes, for a row that the reader refuses; each such row
is listed in ``docs/evidence/altium-roundtrip.md``. Empty: every row reads."""


def _repository(url: str) -> tuple[str, ...]:
    parts = [part for part in urlparse(url).path.split("/") if part and part != "media"]
    return tuple(parts[:2])


def _repositories() -> dict[str, tuple[str, ...]]:
    rows = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    return {row["id"]: _repository(row["url"]) for row in rows if "rta" in row["uses"]}


def judge(item: CorpusItem) -> dict[str, Any]:
    """The census entry of one row: its kind, its size and the verdict of each level."""
    path = require(item)
    data = path.read_bytes()
    kind = kind_of(path)
    a0 = rt_a0(data, kind=kind, file=item.id)
    started = time.perf_counter()
    a1 = rt_a1(data, kind=kind, file=item.id)
    elapsed = int((time.perf_counter() - started) * 1000)
    entry: dict[str, Any] = {
        "kind": kind,
        "bytes": len(data),
        "license": item.license,
        "rt_a0": {"judged": a0.judged, "passed": a0.passed, "streams": a0.streams, "reason": a0.reason},
        "rt_a1": {
            "judged": a1.judged,
            "passed": a1.passed,
            "streams": a1.streams,
            "records": a1.records,
            "bytes_equal": a1.bytes_equal,
            "opaque_count": a1.opaque_count,
            "reason": a1.reason,
            "different": list(a1.different),
            "read_ms": elapsed,
        },
    }
    if kind in COMPOUND_KINDS:
        header = cfb.open_compound(data, file=item.id).header
        entry["fat_sectors"], entry["difat_sectors"] = header.fat_sectors, header.difat_sectors
    assert a0.difference == "" and a0.different == (), f"{item.id}: RT-A0 lost {a0.different}"
    return entry


def test_rta_rows_exist() -> None:
    kinds = {item.id.rsplit("-", 2)[1] for item in ROWS}
    assert len(ROWS) >= 60 and kinds == {"schdoc", "schlib", "pcbdoc", "pcblib", "prjpcb"}


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_row_holds_both_levels(item: CorpusItem) -> None:
    """Scenario "Corpus round trips": every judged verdict passes; an unjudged one names its reason."""
    if item.id in READER_REFUSED:
        with pytest.raises(FormatError):
            judge(item)
        return
    entry = judge(item)
    a0, a1 = entry["rt_a0"], entry["rt_a1"]
    assert a0["passed"] is a0["judged"], f"{item.id}: RT-A0 failed"
    if not a0["judged"]:
        assert a0["reason"] in UNJUDGED, item.id
        assert (a0["reason"] == "not-a-container") is (entry["kind"] not in COMPOUND_KINDS), item.id
        if a0["reason"] == "too-large":  # the writer writes no DIFAT sector
            assert entry["difat_sectors"] > 0 and entry["fat_sectors"] > 109, item.id
    elif entry["kind"] in COMPOUND_KINDS:
        assert entry["difat_sectors"] == 0, item.id
    assert a1["judged"] and a1["passed"], f"{item.id}: RT-A1 differs in {a1['different']}"
    assert a1["streams"] >= 1 and a1["records"] >= 1, item.id
    census("altium-roundtrip", item.id, entry)
    # H-A-VER-WRITER and H-A-VER-BYTES: stated as assertions, so that a new row that refutes one fails here.
    assert a0["reason"] != "writer-refused", f"{item.id}: the writer refuses this tree (H-A-VER-WRITER)"
    assert a1["bytes_equal"] == a1["streams"], f"{item.id}: encoded bytes differ (H-A-VER-BYTES)"


SHORT_OF_THREE = {"pcblib": 2}
"""Compound kind → the number of repositories its judged rows come from, where it is below three. While
this is not empty, ``H-A-VER-RTA0`` and ``H-A-VER-RTA1`` stay ``INFERRED``: their criterion asks for three
repositories per compound kind."""


def test_repositories_per_compound_kind() -> None:
    """The criterion of ``H-A-VER-RTA0`` and ``H-A-VER-RTA1``: at least three repositories judged per
    compound kind that the corpus holds. The PCB libraries come from two, which is pinned here so that a
    third repository fails this test and the levels are then raised."""
    cached = corpus_items("rta")
    if len(cached) < len([item for item in ROWS if not item.heavy]):
        pytest.skip("not every rta row is cached")
    repositories = _repositories()
    judged: dict[str, set[tuple[str, ...]]] = {}
    for item in cached:
        data = item.path.read_bytes()
        kind = kind_of(item.path)
        if kind in COMPOUND_KINDS and rt_a0(data, kind=kind).judged:
            judged.setdefault(item.id.rsplit("-", 2)[1], set()).add(repositories[item.id])
    assert set(judged) == {"schdoc", "schlib", "pcbdoc", "pcblib"}
    counts = {kind: len(found) for kind, found in judged.items()}
    census("altium-roundtrip-repositories", "judged", counts)
    assert {kind: count for kind, count in counts.items() if count < 3} == SHORT_OF_THREE, counts
