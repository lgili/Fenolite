# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The proposal schema is closed, cited and independent of document extraction tools (c0265)."""

import copy
from decimal import Decimal
from pathlib import Path

import pytest

from fenolite.core.errors import FormatError
from fenolite.library.proposals.schema import (
    Proposal,
    ProposalTooNew,
    parse_proposal,
    proposal_text,
    skeleton,
)

DATA = Path(__file__).resolve().parents[3] / "data/proposals"


def example():
    return parse_proposal((DATA / "exb6202.proposal.toml").read_text(), file="example.toml")


def edit(change):
    proposal = example()
    raw = copy.deepcopy(proposal.data)
    change(raw)
    return parse_proposal(proposal_text(Proposal(raw, {}, {}, file="edited.toml")), file="edited.toml")


def test_authored_read_and_exact_roundtrip():
    parsed = example()
    assert parsed.family == "gullwing" and len(parsed.pins) == 8
    assert parsed.quantities["package.pitch"].nominal == 1_270_000
    assert proposal_text(parsed) == proposal_text(parse_proposal(proposal_text(parsed)))
    assert not parsed.uncited
    assert not any(isinstance(v, (float, Decimal)) for v in parsed.quantities.values())


@pytest.mark.parametrize("location", ["root", "pin", "body", "land", "cite", "alternate"])
def test_geometry_and_unknown_keys_are_refused(location):
    def change(raw):
        if location == "root":
            raw["pads"] = []
        elif location == "pin":
            raw["pin"][0]["x"] = "1mm"
        elif location == "body":
            raw["package"]["body"]["points"] = []
        elif location == "land":
            raw["package"]["land"]["position"] = []
        elif location == "cite":
            raw["device"]["cite"]["unknown"] = True
        else:
            raw["pin"][0]["alternates"] = [{"name": "ALT", "x": "1mm"}]

    with pytest.raises(FormatError) as caught:
        edit(change)
    assert "edited.toml" in str(caught.value)
    if location != "cite":
        assert "no geometry" in str(caught.value)


@pytest.mark.parametrize(
    "cite", [{"page": 0}, {"page": True}, {"page": 1, "table": "T", "figure": "F"}, {"figure": "F"}]
)
def test_citations_are_exact(cite):
    with pytest.raises(FormatError):
        edit(lambda r: r["pin"][0].update(cite=cite))


def test_doubts_and_missing_citations_are_retained():
    parsed = edit(
        lambda r: (
            r["pin"][0].pop("cite"),
            r.update(doubt=[{"field": "package.lead.length", "reason": "unreadable"}]),
        )
    )
    assert parsed.uncited == ["pin[1]"]
    assert parsed.data["doubt"][0]["field"] == "package.lead.length"


def test_newer_schema_and_decimal_values():
    with pytest.raises(ProposalTooNew):
        parse_proposal(
            (DATA / "exb6202.proposal.toml")
            .read_text()
            .replace("fenolite.proposal.v0", "fenolite.proposal.v1")
        )
    with pytest.raises(FormatError):
        edit(lambda r: r["package"].update(pins=8.0))


def test_skeleton_is_a_parseable_unfilled_proposal():
    data = (DATA / "exb6202.pdf").read_bytes()
    parsed = parse_proposal(skeleton("exb6202.pdf", data))
    assert parsed.pins == [] and parsed.data["datasheet"]["file"] == "exb6202.pdf"


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["proposer"].update(kind={}),
        lambda r: r["pin"][0].update(group={}),
        lambda r: r["pin"][0].update(side=[]),
        lambda r: r["pin"][0].update(alternates=[{"name": "ALT", "type": {}}]),
    ],
)
def test_wrong_enum_container_types_are_bad_input(change):
    with pytest.raises(FormatError):
        edit(change)


@pytest.mark.parametrize(
    "change", [lambda r: r["package"].pop("pins"), lambda r: r["package"]["body"].pop("width")]
)
def test_missing_family_parameters_name_the_required_key(change):
    with pytest.raises(FormatError, match="required key is missing"):
        edit(change)
