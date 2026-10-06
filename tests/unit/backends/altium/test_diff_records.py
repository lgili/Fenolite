# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The records view of two Altium files (capability altium-verification, "Records view of two Altium
files"; change c0044): streams matched by path, records aligned by their longest common subsequence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from _altium_sch_build import SHEET, schdoc

from fenolite.backends.altium import roundtrip
from fenolite.backends.altium.docset import SUFFIX_KINDS, kind_of
from fenolite.backends.altium.roundtrip import READER_EVIDENCE, diff_records, record_fields
from fenolite.backends.base import DiffReport
from fenolite.core.errors import FormatError

DATA = Path(__file__).resolve().parents[4] / "tests" / "data" / "altium"
OWN = sorted(p for p in DATA.rglob("*") if p.is_file() and p.suffix.lower() in SUFFIX_KINDS)
KIND = "altium_schdoc_binary"
WIRE = "|RECORD=27|LOCATIONCOUNT=2|X1=10|Y1=20|X2=30|Y2=20"
RECORDS = [SHEET, WIRE, "|RECORD=25|TEXT=VIN|LOCATION.X=10|LOCATION.Y=20", "|RECORD=17|TEXT=GND|STYLE=4"]


def _paths(report: DiffReport) -> list[tuple[str, str]]:
    return [(change.path, change.change) for change in report.changes]


@pytest.mark.parametrize("path", OWN, ids=lambda p: p.relative_to(DATA).as_posix())
def test_a_file_against_itself(path: Path) -> None:
    data = path.read_bytes()
    report = diff_records(data, data, kind=kind_of(path))
    assert report.equal and report.changes == () and report.summary == {}


def test_one_key_changed() -> None:
    a = schdoc(RECORDS)
    b = schdoc([*RECORDS[:2], "|RECORD=25|TEXT=VBUS|LOCATION.X=10|LOCATION.Y=20", RECORDS[3]])
    report = diff_records(a, b, kind=KIND)
    (change,) = report.changes
    assert (change.path, change.change) == ("/FileHeader#3", "changed")  # the stream header is record 0
    assert json.loads(change.a) == {"kind": "NetLabel", "fields": {"TEXT": "VIN"}}
    assert json.loads(change.b) == {"kind": "NetLabel", "fields": {"TEXT": "VBUS"}}
    assert report.summary == {"FileHeader": {"added": 0, "removed": 0, "changed": 1}} and not report.equal


def test_one_record_inserted_in_the_middle() -> None:
    more = "|RECORD=27|LOCATIONCOUNT=2|X1=50|Y1=60|X2=70|Y2=60"
    a = schdoc(RECORDS, weight=None)
    b = schdoc([*RECORDS[:2], more, *RECORDS[2:]], weight=None)
    report = diff_records(a, b, kind=KIND)
    (change,) = report.changes  # no later record is reported, although each moved by one place
    assert (change.path, change.change, change.a) == ("/FileHeader#3", "added", "")
    added = json.loads(change.b)
    assert added["kind"] == "Wire" and added["fields"]["X1"] == "50"
    (back,) = diff_records(b, a, kind=KIND).changes
    assert (back.path, back.change, back.b) == ("/FileHeader#3", "removed", "")


def test_record_kinds_decide_between_changed_and_removed_plus_added() -> None:
    a = schdoc([SHEET, WIRE, "|RECORD=25|TEXT=VIN"], weight=None)
    b = schdoc([SHEET, WIRE, "|RECORD=17|TEXT=VIN"], weight=None)
    assert _paths(diff_records(a, b, kind=KIND)) == [("/FileHeader#3", "added"), ("/FileHeader#3", "removed")]
    assert record_fields(b"raw") == ("bytes", {"bytes": b"raw"})


def test_long_and_binary_values_are_given_as_a_digest() -> None:
    long_text = "N" * 200
    a = schdoc([SHEET, "|RECORD=25|TEXT=VIN"], weight=None)
    b = schdoc([SHEET, f"|RECORD=25|TEXT={long_text}"], weight=None)
    (change,) = diff_records(a, b, kind=KIND).changes
    shown = json.loads(change.b)["fields"]["TEXT"]
    assert shown == {"bytes": 200, "sha256": hashlib.sha256(long_text.encode()).hexdigest()}
    assert long_text not in change.b and json.loads(change.a)["fields"]["TEXT"] == "VIN"
    assert roundtrip.MAX_SHOWN == 80


def test_streams_on_one_side_and_opaque_streams() -> None:
    a = schdoc(RECORDS, extra=[("Whole", b"kept"), ("OnlyA", b"x")])
    b = schdoc(RECORDS, extra=[("Whole", b"other"), ("OnlyB", b"y")])
    report = diff_records(a, b, kind=KIND)
    assert _paths(report) == [("/OnlyA", "removed"), ("/OnlyB", "added"), ("/Whole", "changed")]
    whole = report.changes[2]
    assert (whole.a, whole.b) == (hashlib.sha256(b"kept").hexdigest(), hashlib.sha256(b"other").hexdigest())
    assert json.loads(report.changes[0].a) == {"bytes": 1, "sha256": hashlib.sha256(b"x").hexdigest()}
    assert set(report.summary) == {"OnlyA", "OnlyB", "Whole"}


def test_changes_are_in_record_order(monkeypatch: pytest.MonkeyPatch) -> None:
    labels = [f"|RECORD=25|TEXT=N{n}" for n in range(12)]
    changed = list(labels)
    changed[1], changed[10] = "|RECORD=25|TEXT=X1", "|RECORD=25|TEXT=X10"
    a, b = schdoc([SHEET, *labels], weight=None), schdoc([SHEET, *changed], weight=None)
    assert _paths(diff_records(a, b, kind=KIND)) == [
        ("/FileHeader#3", "changed"),
        ("/FileHeader#12", "changed"),
    ]
    monkeypatch.setattr(roundtrip, "LCS_CELLS", 0)  # past the exact table, runs are paired greedily
    assert _paths(diff_records(a, b, kind=KIND)) == [
        ("/FileHeader#3", "changed"),
        ("/FileHeader#12", "changed"),
    ]


def test_text_kinds_and_pcb_records() -> None:
    project = (DATA / "blink" / "blink.PrjPcb").read_bytes()
    other = project.replace(b"DocumentPath=blink.PcbLib", b"DocumentPath=other.PcbLib")
    assert other != project
    (change,) = diff_records(project, other, kind="altium_prjpcb").changes
    assert change.path.startswith("/text#") and change.change == "changed"
    assert json.loads(change.a)["kind"] == "TextLine"
    board = (DATA / "blink" / "blink.PcbDoc").read_bytes()
    routed = (DATA / "routed" / "routed.PcbDoc").read_bytes()
    report = diff_records(board, routed, kind="altium_pcbdoc")
    assert report.summary["Tracks6/Data"]["added"] > 0 and report.summary["Nets6/Data"]["changed"] == 4
    nets = [c for c in report.changes if c.path.startswith("/Nets6/Data#")]
    assert set(json.loads(nets[0].a)["fields"]) == {"UNIQUEID"}
    assert [c.path for c in nets] == [f"/Nets6/Data#{n}" for n in range(4)]
    assert set(READER_EVIDENCE) == set(roundtrip.CODECS)


def test_unknown_kind_and_unreadable_file() -> None:
    data = schdoc(RECORDS)
    with pytest.raises(ValueError, match="kicad_pcb"):
        diff_records(data, data, kind="kicad_pcb")
    with pytest.raises(FormatError):
        diff_records(data, data[:100], kind=KIND)
