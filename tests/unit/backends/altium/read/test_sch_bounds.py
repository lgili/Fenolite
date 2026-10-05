# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded reading of untrusted files (capability altium-schematic-reader, "Bounded reading of untrusted
files")."""

from __future__ import annotations

import builtins
import io
import os
import pathlib
import time
from typing import Any, NoReturn

import pytest
from _altium_sch_build import SHEET, schdoc

from fenolite.backends.altium.read import sch
from fenolite.core.errors import Issue


def test_huge_count() -> None:
    issues: list[Issue] = []
    started = time.monotonic()
    wire = sch.read_schematic(
        schdoc([SHEET, "|RECORD=27|LOCATIONCOUNT=2000000000|X1=1|Y1=2|X2=3|Y2=2"]), issues=issues
    )
    assert time.monotonic() - started < 20  # generous: the bound is the loop, checked by the two points
    record = wire.records[1]
    assert isinstance(record, sch.Wire)
    assert len(record.points) == 2
    assert [issue.code for issue in issues] == ["altium.sch.bad-value"]


def test_other_counts_do_not_drive_loops() -> None:
    issues: list[Issue] = []
    records = [
        "|RECORD=31|FONTIDCOUNT=999999999|SIZE1=10|FONTNAME1=A",
        "|RECORD=45|DATAFILECOUNT=99999999|MODELDATAFILE0=x",
        "|RECORD=47|DESIMPCOUNT=-5|DESIMP0=1",
    ]
    document = sch.read_schematic(schdoc(records), issues=issues)
    sheet = document.sheet
    assert sheet is not None and len(sheet.fonts) == 1
    implementation = document.records[1]
    assert isinstance(implementation, sch.Implementation) and len(implementation.data_files) == 1
    assert [issue.code for issue in issues] == ["altium.sch.bad-value"] * 3


def test_deep_chain() -> None:
    count = 100_000
    records = [SHEET, *(f"|RECORD=29|OWNERINDEX={index}" for index in range(count - 1))]
    document = sch.read_schematic(schdoc(records))
    assert len(document.records) == count
    walked = sum(1 for _ in document.walk(document.records[0]))
    assert walked == count
    assert document.roots == (sch.RecordRef("main", 0),)


def test_file_names_are_not_opened(monkeypatch: pytest.MonkeyPatch) -> None:
    data = schdoc(
        [
            SHEET,
            "|RECORD=30|EMBEDIMAGE=F|FILENAME=C:\\nowhere\\does-not-exist.bmp",
            "|RECORD=15|XSIZE=10",
            "|RECORD=33|OWNERINDEX=2|TEXT=..\\..\\x.SchDoc",
            "|RECORD=39|FILENAME=/nowhere/t.SchDot",
            "|RECORD=45|MODELDATAFILE0=/nowhere/x.PcbLib",
        ]
    )

    def refuse(*args: Any, **kwargs: Any) -> NoReturn:
        raise AssertionError(f"file-system call {args!r}")

    for target, name in (
        (builtins, "open"),
        (io, "open"),
        (os, "open"),
        (os, "stat"),
        (os, "lstat"),
        (os, "listdir"),
        (os, "scandir"),
        (pathlib.Path, "open"),
        (pathlib.Path, "exists"),
        (pathlib.Path, "read_bytes"),
    ):
        monkeypatch.setattr(target, name, refuse)
    document = sch.read_schematic(data)
    monkeypatch.undo()
    image = document.records[1]
    file_name = document.records[3]
    assert isinstance(image, sch.Image) and image.file_name == "C:\\nowhere\\does-not-exist.bmp"
    assert isinstance(file_name, sch.SheetFileName) and file_name.text == "..\\..\\x.SchDoc"


def test_reading_time_is_linear() -> None:
    def seconds(count: int) -> float:
        data = schdoc([SHEET, *(f"|RECORD=29|LOCATION.X={n}" for n in range(count))])
        runs: list[float] = []
        for _ in range(3):
            started = time.perf_counter()
            sch.read_schematic(data)
            runs.append(time.perf_counter() - started)
        return min(runs)

    small, large = seconds(2_000), seconds(20_000)
    assert large < small * 30
