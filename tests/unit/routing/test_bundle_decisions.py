# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Strict atomic bundle records with preserved independent decision bytes (c0367).

Bundles are an optional key of ``fenolite.route-decisions.v0``; ``v1`` is its prepared mirror (c0217)."""

from dataclasses import replace

import pytest

from fenolite.core.errors import FormatError
from fenolite.routing.decisions import (
    SCHEMA,
    Decisions,
    Locked,
    RecordBundle,
    Rejected,
    dumps,
    from_data,
    loads,
    to_data,
    with_entries,
)

BUNDLE = RecordBundle("b-" + "1" * 16, "2" * 64, ("c-a", "c-b"))


def accepted():
    return Decisions(
        "board.kicad_pcb", (Locked("c-a", "p-a", "a", "A"), Locked("c-b", "p-b", "b", "B")), bundles=(BUNDLE,)
    )


def test_bundle_roundtrip_keeps_members_and_input_fingerprint() -> None:
    record = accepted()
    assert to_data(record)["schema"] == SCHEMA and "bundles" in to_data(record)
    assert loads(dumps(record)) == record
    assert dumps(record) == dumps(replace(record, locked=tuple(reversed(record.locked))))


def test_rejected_bundle_is_stored_without_accepted_member_copper() -> None:
    record = with_entries(
        Decisions("board"), rejected=(Rejected(BUNDLE.id, "bundle", "authored"),), bundles=(BUNDLE,)
    )
    assert loads(dumps(record)) == record and not record.locked


@pytest.mark.parametrize(
    "change", ["missing-member", "duplicate-member", "bad-digest", "overlap", "mixed", "future"]
)
def test_partial_ambiguous_and_future_records_are_refused(change: str) -> None:
    raw = to_data(accepted())
    if change == "missing-member":
        raw["locked"] = raw["locked"][:1]
    elif change == "duplicate-member":
        raw["bundles"][0]["members"] = ["c-a", "c-a"]
    elif change == "bad-digest":
        raw["bundles"][0]["fingerprint"] = "unknown"
    elif change == "overlap":
        raw["bundles"].append({**raw["bundles"][0], "id": "b-" + "3" * 16})
    elif change == "mixed":
        raw["rejected"] = [{"id": BUNDLE.id, "subject": "bundle", "reason": "x"}]
    else:
        raw["schema"] = "fenolite.route-decisions.v999"
    with pytest.raises(FormatError):
        from_data(raw)


def test_prepared_v1_mirror_reads_bundles_like_v0() -> None:
    raw = to_data(accepted())
    assert from_data({**raw, "schema": "fenolite.route-decisions.v1"}) == from_data(raw)


def test_forget_is_atomic_and_returns_to_legacy_bytes_when_no_bundle_remains() -> None:
    with pytest.raises(ValueError, match=BUNDLE.id):
        with_entries(accepted(), forget=("c-a",))
    removed = with_entries(accepted(), forget=(BUNDLE.id,))
    assert not (removed.locked or removed.bundles)
    assert set(to_data(removed)) == {"schema", "board", "locked", "rejected"}


def test_independent_v0_decisions_roundtrip_without_new_keys() -> None:
    old = Decisions("board", (Locked("c-old", "p-old", "subject", "SIG"),), (Rejected("c-no", "subject"),))
    assert set(to_data(old)) == {"schema", "board", "locked", "rejected"}
    assert loads(dumps(old)) == old
    updated = with_entries(accepted(), locked=old.locked)
    assert loads(dumps(updated)) == updated
