# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""RT-A3 on the public PCB documents and project sets (capability altium-verification, "Round-trip level
RT-A3"; change c0090; ``H-A-VER-RTA3``, ``H-A-VER-RTA3-PRJ``).

Every PCB document with the use ``rta`` is read, its model is written as new Altium documents under
pytest's temporary directory, and those are read again; the two models must be equal inside the written
scope. Every project set of c0043 goes the same way through its project file. The census and the printed
lines hold row ids, kinds and counts only: no name and no value of a file. The results are recorded in
``docs/evidence/altium-roundtrip.md``.
"""

from __future__ import annotations

import io
import json
import sys
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from _altium_sets import SETS, lay_out
from _boards import census
from _corpus import MANIFEST, CorpusItem, heavy_enabled, manifest_items, require

import fenolite.cli.main as cli_main
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.lower import write_design
from fenolite.backends.base import ModelRoundTrip
from fenolite.checks.rta3 import compare

pytestmark = pytest.mark.needs_corpus
ROWS = [item for item in manifest_items("rta") if "-pcbdoc-" in item.id]
MINIMUM_REPOSITORIES = 3
"""``H-A-VER-RTA3`` asks for equal documents from at least three repositories, as ``H-A-VER-RTA0`` does."""
NOT_EQUAL: dict[str, tuple[str, str]] = {
    "altium-third-party-pcbdoc-08": (
        "arc",
        "7 of its 517 written arcs come back with a point moved by 3 nm or more: an arc record holds a "
        "centre, a radius and two angles, the model holds three points, and the centre and the radius "
        "that the writer derives from the points are each rounded to a unit of 2.54 nm",
    ),
}
"""Row id → the one kind that differs and the cause, for a document whose two models differ inside the
scope for a reason that is listed in ``docs/evidence/altium-roundtrip.md``. Such a row must differ in
that kind only. The one row is the heavy one, which runs with ``FENOLITE_HEAVY=1``."""
UNCOVERED = ("netlist.uncovered", "info")
UNJUDGED_SETS: dict[str, str] = {
    "altium-set:01": "a comment starts with '=', which Altium reads as a reference to another parameter",
    "altium-set:02": "the import puts one pin on two nets, and the schematic writer refuses that circuit",
    "altium-set:04": "a comment holds characters outside Windows-1252, which no form of the schematic holds",
}
"""Set → why its rewrite holds no project to read: the PCB document is written, and the schematic that is
generated from the circuit is not. Each is a row of the evidence page; a set that starts to pass fails
this test, so that the page is corrected."""


def _repository(url: str) -> tuple[str, ...]:
    parts = [part for part in urlparse(url).path.split("/") if part and part != "media"]
    return tuple(parts[:2])


def _repositories() -> dict[str, tuple[str, ...]]:
    rows = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    return {row["id"]: _repository(row["url"]) for row in rows}


def entry_of(trip: ModelRoundTrip) -> dict[str, Any]:
    """The census entry of one trip: the verdict and counts, no name and no value."""
    kinds = Counter(change.path.split("/")[1] for change in trip.differences)
    return {
        "judged": trip.judged,
        "equal": trip.equal,
        "reason": trip.reason,
        "differences": dict(sorted(kinds.items())),
        "first_difference": trip.differences[0].path if trip.differences else "",
        "written": dict(sorted(trip.written.items())),
        "unwritten": dict(sorted(trip.unwritten.items())),
        "files": sorted(Path(name).suffix for name in trip.files),
    }


def _line(name: str, entry: dict[str, Any]) -> str:
    state = "equal" if entry["equal"] else (entry["first_difference"] or f"not judged ({entry['reason']})")
    return f"{name}: {state}; written {entry['written']}; unwritten {entry['unwritten']}"


def test_rows_exist() -> None:
    repositories = _repositories()
    assert len(ROWS) >= 7 and len({repositories[item.id] for item in ROWS}) >= MINIMUM_REPOSITORIES


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_document_holds_rta3(item: CorpusItem, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "Corpus documents": the document is equal inside the scope, and its unwritten counts are
    printed and recorded."""
    path = require(item)
    trip = AltiumBackend().model_roundtrip(path, compare=compare)
    entry = entry_of(trip)
    census("altium-rta3", item.id, entry)
    with capsys.disabled():
        print("\n" + _line(item.id, entry))
    assert trip.judged, f"{item.id}: not judged ({trip.reason})"
    assert trip.written["footprint"] > 0 and trip.written["pad"] > 0, item.id
    if item.id in NOT_EQUAL:
        kind, _cause = NOT_EQUAL[item.id]
        assert not trip.equal, f"{item.id} is equal now: remove it from NOT_EQUAL and from the page"
        assert set(entry["differences"]) == {kind}, f"{item.id}: differs outside {kind}"
        return
    assert trip.equal, f"{item.id}: {len(trip.differences)} difference(s), first {entry['first_difference']}"


def test_equal_documents_come_from_three_repositories() -> None:
    """The criterion of ``H-A-VER-RTA3``: the rows that are not listed as different come from at least
    three repositories (the heavy row counts only where it runs)."""
    repositories = _repositories()
    judged = [item for item in ROWS if item.id not in NOT_EQUAL and (not item.heavy or heavy_enabled())]
    assert len({repositories[item.id] for item in judged}) >= MINIMUM_REPOSITORIES


def _assignment(folder: Path, monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], int]:
    """The findings of ``netlist.assignment_compare`` on a project folder: (code, severity) → count."""
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", err)
        cli_main.main(["check", str(folder), "--stages", "netlist.assignment_compare", "--json"])
    assert out.getvalue(), err.getvalue()
    issues = json.loads(out.getvalue())["issues"]
    found = [(i["code"], i["severity"]) for i in issues if i["code"].startswith("netlist.")]
    return dict(sorted(Counter(found).items()))


@pytest.mark.parametrize("name", list(SETS))
def test_sets(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``H-A-VER-RTA3-PRJ``: a project set read through its project file, written and read again as a
    project gives an equal circuit and board inside the scope, and ``netlist.assignment_compare`` reports
    on the rewrite what it reported on the original. A set of ``UNJUDGED_SETS`` gives no project to read."""
    items = SETS[name]
    if any(item.heavy for item in items) and not heavy_enabled():
        pytest.skip(f"{name} holds a heavy corpus item: set FENOLITE_HEAVY=1 to include it")
    folder = lay_out(items, tmp_path / "set")
    (project,) = sorted(path for path in folder.iterdir() if path.suffix.lower() == ".prjpcb")
    trip = AltiumBackend().model_roundtrip(project, compare=compare)
    entry = entry_of(trip)
    census("altium-rta3", name, entry)
    with capsys.disabled():
        print("\n" + _line(name, entry))
    if name in UNJUDGED_SETS:
        assert not trip.judged and trip.reason == "no-document", f"{name} is judged now: correct the page"
        assert ".PcbDoc" in entry["files"] and ".SchDoc" not in entry["files"]
        return
    assert trip.judged and trip.equal, f"{name}: first difference {entry['first_difference']}"
    rewrite = tmp_path / "rewrite"
    rewrite.mkdir()
    written = write_design(AltiumBackend().read(project).design, allow_lossy=True)
    for file_name, data in written.files.items():
        (rewrite / file_name).write_bytes(data)
    before, after = _assignment(folder, monkeypatch), _assignment(rewrite, monkeypatch)
    census("altium-rta3", f"{name}:assignment", {"original": list(before), "rewrite": list(after)})
    # A pad that the write left out is a pin without a pad on the rewrite: one ``netlist.uncovered`` info
    # says so. Nothing else may differ, and no difference of an assignment may appear.
    if entry["unwritten"].get("pad"):
        after.pop(UNCOVERED, None)
        before.pop(UNCOVERED, None)
    assert after == before, name
