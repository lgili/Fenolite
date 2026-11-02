# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored observation intake: scan first, disclose counts only, never invent native outcomes."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from fenolite.backends.altium.draftsman import (
    DraftsmanItem,
    DraftsmanSheet,
    DraftsmanSpec,
    encode,
    write_draftsman,
)
from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
from fenolite.backends.altium.read.draftsman import decode
from fenolite.cli.altium_observations import ObservationError, checked_files, observe_f0, observe_j
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import Track


def drawing(text: str) -> bytes:
    return write_draftsman(
        DraftsmanSpec(
            "authored",
            (
                DraftsmanSheet(
                    "page",
                    "",
                    "A4",
                    (297_000_000, 210_000_000),
                    (
                        DraftsmanItem(
                            "label", "Text", (1_000_000, 1_000_000), (10_000_000, 5_000_000), texts=(text,)
                        ),
                    ),
                ),
            ),
        )
    )


def test_f0_member_difference_contains_no_values(tmp_path: Path) -> None:
    (tmp_path / "F0-03.PCBDwf").write_bytes(drawing("FENOLITE PRIVATE CONTROL"))
    (tmp_path / "F0-04.PCBDwf").write_bytes(drawing("FENOLITE CHANGED CONTENT"))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = observe_f0(tmp_path)
    text = json.dumps(result)
    assert "PRIVATE CONTROL" not in text and "CHANGED CONTENT" not in text
    assert result["native_verdict"] == "unjudged" and result["privacy_scan"] == "passed"
    row = result["files"][1]
    assert row["control"] == "F0.3"
    assert row["changed_members"] == ["Document/Pages[0]/Page[0]/Items[0]/Item[0]/Text[0]"]
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_scan_refuses_before_parsing_members(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fenolite.cli import altium_observations

    path = "\\".join(("C:", "Users", "ExampleObserver", "own.PcbDoc"))
    (tmp_path / "F0-01.PCBDwf").write_bytes(drawing(path))
    monkeypatch.setattr(
        altium_observations, "read_draftsman", lambda _: pytest.fail("members read before scan")
    )
    with pytest.raises(ObservationError, match="privacy scan") as error:
        observe_f0(tmp_path)
    assert "ExampleObserver" not in str(error.value)


def test_decoded_chunks_are_scanned_before_members(tmp_path: Path) -> None:
    path = "\\".join(("C:", "Users", "ExampleObserver", "own.PcbDoc"))
    xml = decode(drawing(path))[1]
    split = xml.index(b"C:") + 2
    # The chunk framing interrupts the raw path; only the decoded-text scan can see it whole.
    (tmp_path / "F0-01.PCBDwf").write_bytes(encode(xml[:split]) + encode(xml[split:]))
    with pytest.raises(ObservationError, match="decoded kit privacy scan"):
        observe_f0(tmp_path)


def test_duplicate_cases_and_symbolic_links_refuse(tmp_path: Path) -> None:
    (tmp_path / "F0-01.PCBDwf").write_bytes(drawing("own"))
    other = tmp_path / "other"
    other.mkdir()
    (other / "F0-01.PCBDwf").write_bytes(drawing("second"))
    with pytest.raises(ObservationError, match="more than one"):
        observe_f0(tmp_path)


def test_j_plain_resave_comparison_is_not_native_proof(tmp_path: Path) -> None:
    # A minimal authored board exercises the already implemented lossless records comparator.
    data = write_pcbdoc(PcbDocSpec((Point(0, 0), Point(10_000_000, 0), Point(10_000_000, 10_000_000))))
    (tmp_path / "edit.PcbDoc").write_bytes(data)
    (tmp_path / "J01-resave.PcbDoc").write_bytes(data)
    (tmp_path / "J02-resave.PcbDoc").write_bytes(data)
    result = observe_j(tmp_path)
    assert result["native_verdict"] == "unjudged"
    rows = result["files"]
    assert rows[0]["control"] == "edit.PcbDoc" and rows[0]["changes_by_kind"] == {}
    assert rows[1]["control"] == "J01-resave.PcbDoc" and rows[1]["changes_by_kind"] == {}
    assert checked_files(tmp_path)["edit.PcbDoc"] == data


def test_j_changed_records_are_counted_without_content_values(tmp_path: Path) -> None:
    spec = PcbDocSpec((Point(0, 0), Point(10_000_000, 0), Point(10_000_000, 10_000_000)))
    plain = write_pcbdoc(spec)
    track = Track(
        id=derived_id("trk", "observation", "own"),
        start=Point(1_000_000, 1_000_000),
        end=Point(2_000_000, 1_000_000),
        width=250_000,
        layer="F.Cu",
    )
    (tmp_path / "J01-resave.PcbDoc").write_bytes(plain)
    (tmp_path / "J03-move.PcbDoc").write_bytes(write_pcbdoc(replace(spec, tracks=(track,))))
    result = observe_j(tmp_path)
    changed = result["files"][1]
    assert changed["control"] == "J01-resave.PcbDoc"
    assert sum(changed["changes_by_kind"].values()) > 0 and result["native_verdict"] == "unjudged"
    assert "250000" not in json.dumps(result)
