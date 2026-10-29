# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Resave differences of Altium documents (capability file-safety, "Resave differences of Altium
documents"; change c0207): two spellings of one value are left out of the records view. Hermetic: authored
schematic records with round invented values."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _altium_sch_build import SHEET, schdoc

from fenolite.backends.altium.resave import free_text, same_value
from fenolite.backends.altium.roundtrip import diff_records
from fenolite.backends.base import Change
from fenolite.cli import main as cli_main

KIND = "altium_schdoc_binary"
WIRE = "|RECORD=27|LOCATIONCOUNT=2|X1=10|Y1=20|X2=30|Y2=20|ISHIDDEN=T"
LABEL = "|RECORD=25|TEXT=1|LOCATION.X=10|LOCATION.Y=20"


@pytest.mark.parametrize(
    ("key", "a", "b", "same"),
    [
        ("X", "10mil", "10.0000mil", True),
        ("X", b"10mil", b"10.00001mil", True),  # below one unit of 1/10 000 mil
        ("X", "10mil", "10.0001mil", False),
        ("ROTATION", " 2.70000000000000E+0002", "270", True),
        ("DIELCONST", "4.800", "4.8", True),
        ("DIELCONST", "4.800", "4.81", False),
        ("ISHIDDEN", "T", "TRUE", True),
        ("ISHIDDEN", "F", "TRUE", False),
        ("TEXT", "1.0", "1", False),  # free text: two pad names
        ("SOURCEDESIGNATOR", "10mil", "10.0mil", False),
        ("X", "10mil", "10", False),  # two rules, not one value
        ("X", b"\xff", b"\xfe", False),
    ],
)
def test_spellings_of_one_value(key: str, a: str | bytes, b: str | bytes, same: bool) -> None:
    assert same_value(key, a, b) is same


def test_free_text_keys() -> None:
    assert free_text("text") and free_text("NAME#1") and free_text("UNIQUEID") and not free_text("X1")


def test_a_resave_is_left_out_of_the_records() -> None:
    a = schdoc([SHEET, WIRE, LABEL], weight=None)
    resaved = WIRE.replace("X1=10|", "X1=10.0|").replace("ISHIDDEN=T", "ISHIDDEN=TRUE")
    b = schdoc([SHEET, resaved, LABEL.replace("TEXT=1|", "TEXT=1.0|")], weight=None)
    resave: list[Change] = []
    report = diff_records(a, b, kind=KIND, resave=resave)
    assert [(c.path, c.change) for c in report.changes] == [("/FileHeader#3", "changed")]  # the label text
    assert [c.path for c in resave] == ["/FileHeader#2"]
    assert json.loads(resave[0].a)["fields"] == {"X1": "10", "ISHIDDEN": "T"}
    # without the list, every record that differs is reported, as before change c0207
    assert len(diff_records(a, b, kind=KIND).changes) == 2


def test_a_record_keeps_only_its_real_changes() -> None:
    a = schdoc([SHEET, WIRE], weight=None)
    b = schdoc([SHEET, WIRE.replace("X1=10|", "X1=10.0|").replace("Y2=20", "Y2=40")], weight=None)
    resave: list[Change] = []
    (change,) = diff_records(a, b, kind=KIND, resave=resave).changes
    assert resave == [] and json.loads(change.b)["fields"] == {"Y2": "40"}


def test_the_records_view_counts_resaves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.SchDoc").write_bytes(schdoc([SHEET, WIRE, LABEL], weight=None))
    (tmp_path / "b.SchDoc").write_bytes(
        schdoc([SHEET, WIRE.replace("X1=10|", "X1=10.0|"), LABEL], weight=None)
    )
    monkeypatch.chdir(tmp_path)
    code = cli_main.main(["diff", "a.SchDoc", "b.SchDoc", "--view", "records", "--json"])
    env = json.loads(capsys.readouterr().out)
    result = env["result"]
    assert code == 0 and result["equal"] is True and result["differences"] == []
    assert result["resave"] == {"total": 1, "streams": {"FileHeader": 1}}
    assert "H-A-RD-RESAVE" in env["evidence"]["hypotheses"] and env["evidence"]["level"] == "INFERRED"
