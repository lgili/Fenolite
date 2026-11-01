# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Counts, grids, bounds, citations and uncertainty stay explicit (c0265)."""

import copy
from pathlib import Path

import pytest

from fenolite.library.proposals.checks import bind, self_check
from fenolite.library.proposals.schema import Proposal, parse_proposal, proposal_text

DATA = Path(__file__).resolve().parents[3] / "data/proposals"


def changed(change, name="exb6202.proposal.toml"):
    original = parse_proposal((DATA / name).read_text())
    raw = copy.deepcopy(original.data)
    change(raw)
    return parse_proposal(proposal_text(Proposal(raw, {}, {})))


def codes(proposal):
    return {i.code for i in self_check(proposal)}


def test_good_and_datasheet_binding():
    proposal = changed(lambda r: None)
    assert not self_check(proposal)
    assert bind(proposal, (DATA / "exb6202.pdf").read_bytes()) == []
    assert bind(proposal, b"%PDF-authored other")[0].code == "proposal.datasheet-mismatch"


@pytest.mark.parametrize(
    "change,code",
    [
        (lambda r: r["package"].update(family="unknown"), "proposal.unknown-family"),
        (lambda r: r["pin"].pop(), "proposal.pin-count"),
        (lambda r: r["pin"][1].update(number="1"), "proposal.duplicate-pin"),
        (lambda r: r["package"].update(span="8mm..4mm"), "proposal.range"),
        (lambda r: r["package"].update(span="2mm"), "proposal.range"),
        (lambda r: r["package"].update(pins=1000000000), "proposal.range"),
        (lambda r: r["ratings"]["vin"].update(min="7V", max="6V"), "proposal.range"),
        (lambda r: r["ratings"].update(voltage={"max": "6V"}), "proposal.range"),
        (lambda r: r["pin"][0].update(name="EP"), "proposal.exposed-pad"),
        (lambda r: r["package"].pop("cite"), "proposal.uncited"),
        (
            lambda r: r.update(doubt=[{"field": "package.lead.length", "reason": "illegible"}]),
            "proposal.doubt",
        ),
    ],
)
def test_self_checks(change, code):
    assert code in codes(changed(change))


def test_grid_checks_printed_rows_and_depopulated_positions():
    assert not self_check(changed(lambda r: None, "grid-1.proposal.toml"))
    assert "proposal.pin-outside" in codes(
        changed(lambda r: r["pin"][0].update(number="J4"), "grid-1.proposal.toml")
    )
    assert "proposal.depopulated-used" in codes(
        changed(lambda r: r["pin"][0].update(number="B2"), "grid-1.proposal.toml")
    )
    assert "proposal.pin-outside" in codes(
        changed(lambda r: r["package"].pop("row_labels"), "grid-1.proposal.toml")
    )


def test_explicit_side_numbers_follow_the_family_schema():
    def sides(raw):
        raw["package"].update(
            pins=3,
            arrangement="sides",
            side=[{"edge": "left", "numbers": ["1", "2", "4"], "positions": [0, 1, 2]}],
        )
        raw["pin"] = raw["pin"][:3]
        raw["pin"][2]["number"] = "4"

    assert not self_check(changed(sides))


def test_invalid_row_labels_with_center_exclusion_are_findings():
    proposal = changed(
        lambda r: r["package"].update(row_labels=[], depopulated={"center": "1x1"}), "grid-1.proposal.toml"
    )
    assert "proposal.pin-outside" in codes(proposal)
