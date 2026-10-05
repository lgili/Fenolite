# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Unmapped records are counted (capability altium-import, "Unmapped records are counted"; c0043): for each
record kind of each authored document, the mapped and the unmapped counts add up to the reader's count."""

from __future__ import annotations

import hashlib
from pathlib import Path

import _altium_records as rec
import pytest

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.adapter.board import read_board
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import Ids
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.core.errors import Issue

DATA = Path(__file__).resolve().parents[5] / "tests" / "data" / "altium"
DOCUMENTS = sorted(p for p in DATA.rglob("*") if p.suffix.lower() == ".pcbdoc")
KINDS = ("nets", "components", "classes", "polygons", "pads", "vias", "tracks", "arcs", "texts", "fills",
         "regions", "shape_regions")  # fmt: skip


def check(document: PcbDocument) -> None:
    parts = read_board(document, file="a.PcbDoc", sha256=rec.SHA, ids=Ids("altium_pcbdoc", EVIDENCE))
    for kind in KINDS:
        assert parts.census.total(kind) == len(getattr(document, kind)), kind


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_census_adds_up_on_the_authored_documents(path: Path) -> None:
    assert len(DOCUMENTS) >= 2
    check(read_pcbdoc(path.read_bytes()))


def test_census_adds_up_on_mixed_records() -> None:
    line, tri = ((0, 0), (9, 0)), [(0, 0), (9, 0), (9, 9)]
    document = rec.document(
        nets=["A", "A", "B"],
        components=[rec.component("R1"), rec.component("R2", x="abc")],
        classes=[rec.net_class("P", ["A"]), rec.net_class("All", [], superclass=True)],
        polygons=[rec.polygon(), rec.polygon(polygon_type="Cutout")],
        pads=[rec.pad("1", component=0), rec.pad("1", component=1), rec.pad("")],
        vias=[rec.via((0, 0)), rec.via((0, 0), hole=0)],
        tracks=[rec.track(*line), rec.track(*line, component=0), rec.track(*line, polygon=1)],
        arcs=[rec.arc((0, 0), 9, 0.0, 90.0), rec.arc((0, 0), 0, 0.0, 90.0)],
        texts=[rec.text("x"), rec.text("R1", designator=True, component=0)],
        fills=[rec.fill((0, 0), (9, 9)), rec.fill((0, 0), (9, 9), component=0)],
        regions=[rec.region(tri), rec.region(tri[:2]), rec.region(tri, polygon=0),
                 rec.region(tri, polygon=1)],
    )  # fmt: skip
    check(document)


def test_storages_kept_as_bytes_are_named() -> None:
    issues: list[Issue] = []
    storages = {
        "Models": {"Data": b"x"},
        "Empty6": {"Data": b"", "Header": b"\0\0\0\0"},
        "": {"FileHeader": b"x"},
    }
    import_board(rec.document(storages=storages), file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    (unmapped,) = [i for i in issues if i.code == "altium.import.unmapped"]
    assert unmapped.message == "records without a model entity: Models 1" and unmapped.severity == "info"


def test_without_anything_unmapped_the_issue_is_not_given() -> None:
    issues: list[Issue] = []
    import_board(
        rec.document(tracks=[rec.track((0, 0), (1000, 0))]), file="a.PcbDoc", sha256=rec.SHA, issues=issues
    )
    assert issues == []


def test_inexact_is_given_once_with_its_counts() -> None:
    issues: list[Issue] = []
    data = (DATA / "blink" / "blink.PcbDoc").read_bytes()
    import_board(
        read_pcbdoc(data), file="blink.PcbDoc", sha256=hashlib.sha256(data).hexdigest(), issues=issues
    )
    found = [i for i in issues if i.code == "altium.import.inexact"]
    assert len(found) == 1 and found[0].severity == "info" and "length(s)" in found[0].message
    assert [i.code for i in issues].count("altium.import.unmapped") == 1
    assert [i for i in issues if i.severity != "info"] == []
