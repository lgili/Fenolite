# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Dense packages require two agreeing independent declarations (c0265)."""

import copy
from pathlib import Path

from fenolite.library.proposals.agreement import agreement
from fenolite.library.proposals.schema import Proposal, parse_proposal, proposal_text

DATA = Path(__file__).resolve().parents[3] / "data/proposals"


def pair():
    return [parse_proposal((DATA / f"grid-{i}.proposal.toml").read_text()) for i in (1, 2)]


def edit(proposal, change):
    raw = copy.deepcopy(proposal.data)
    change(raw)
    return parse_proposal(proposal_text(Proposal(raw, {}, {})))


def test_grid_requires_second_and_same_proposer_is_not_independent():
    first, second = pair()
    assert agreement([first])[0].code == "proposal.second-required"
    assert agreement([first, second]) == []
    second = edit(second, lambda r: r["proposer"].update(name="First reader"))
    assert agreement([first, second])[0].code == "proposal.not-independent"


def test_shifted_rows_are_two_differences_with_pages():
    first, second = pair()

    def shift(raw):
        rows = {r["number"]: r for r in raw["pin"]}
        rows["C2"]["name"], rows["C3"]["name"] = rows["C3"]["name"], rows["C2"]["name"]

    found = agreement([first, edit(second, shift)])
    assert {i.where for i in found} == {"pin[C2]", "pin[C3]"}
    assert all("cited pages" in i.message for i in found)


def test_units_and_row_order_normalize_but_parameters_do_not_disappear():
    first, second = pair()
    second = edit(
        second,
        lambda r: (
            r["package"].update(pitch="1000um"),
            r["pin"].reverse(),
            r["package"]["cite"].update(page=2),
        ),
    )
    assert agreement([first, second]) == []
    second = edit(second, lambda r: r["package"]["body"].update(width="4.1mm"))
    found = agreement([first, second])
    assert len(found) == 1 and found[0].where == "package.body.width"
