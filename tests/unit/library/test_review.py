# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Canonical review content is sensitive to edits and insensitive to trust metadata (c0262)."""

from dataclasses import replace
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from fenolite.catalog import records
from fenolite.library.review import digest, is_stale, matches_sheet

ROOT = Path(__file__).resolve().parents[3]
TEXT = (ROOT / "tests/data/library/pins/two_pin.toml").read_text()


@given(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=20).filter(lambda s: s != "A"))
def test_every_pin_name_edit_changes_review_digest(name):
    record = records.parse_record(TEXT)
    assert isinstance(record, records.PinsRecord)
    edited = replace(record, pins=(replace(record.pins[0], name=name), *record.pins[1:]))
    assert digest(edited) != digest(record)


def test_reformatting_trust_metadata_and_generated_outputs():
    record = records.parse_record(TEXT)
    rewritten = records.parse_record("\n# only comments and whitespace\n" + records.record_text(record))
    assert digest(record) == digest(rewritten)
    accepted = replace(
        record,
        header=replace(
            record.header,
            evidence="CORPUS-VERIFIED (review 2026-11-01)",
            reviewed_by=(records.Review("person", "2026-11-01", "1.0.0", "a" * 64, "CORPUS-VERIFIED"),),
        ),
    )
    assert digest(record) == digest(accepted)
    assert isinstance(record, records.PinsRecord)
    symbol = records.symbol_def(record)
    assert digest(record, definitions=[symbol]) != digest(
        record, definitions=[replace(symbol, name="Changed")]
    )
    assert digest(record, dependencies={"pins": "a" * 64}) != digest(record, dependencies={"pins": "b" * 64})


def test_sheet_prefix_and_staleness():
    current = "a" * 64
    assert matches_sheet(current[:12], current)
    assert not matches_sheet(current[:11], current)
    assert not matches_sheet("z" * 12, current)
    assert not is_stale({"digest": current, "sheet_sha256": current}, current, current)
    assert is_stale({"digest": current, "sheet_sha256": "b" * 64}, current, current)


def test_authored_strings_with_generator_suffix_are_never_discarded():
    suffix = "; land pattern remains INFERRED and requires part-specific review"
    record = records.parse_record(TEXT)
    edited = replace(record, header=replace(record.header, summary=record.header.summary + suffix))
    assert digest(record) != digest(edited)
    assert digest({"description": "authored"}) != digest({"description": "authored" + suffix})
    assert digest({"pin_name": "A"}) != digest({"pin_name": "A" + suffix})


def test_authored_map_keys_named_like_metadata_are_bound():
    for key in ("evidence", "review", "reviewed_by", "previous_evidence"):
        assert digest({"properties": {key: "before"}}) != digest({"properties": {key: "after"}})
        assert digest({"sources": {key: ["S-0001"]}}) != digest({"sources": {key: ["S-0002"]}})
        assert digest({"other": {key: "before"}}) != digest({"other": {key: "after"}})


def test_scoped_evidence_keeps_the_existing_grammar():
    import pytest

    from fenolite.core.evidence import Level, parse_level

    assert parse_level("CORPUS-VERIFIED (review 2026-11-01)") is Level.CORPUS_VERIFIED
    assert parse_level("ORACLE-VERIFIED(public-tool) (review notes)") is Level.ORACLE_VERIFIED
    with pytest.raises(ValueError):
        parse_level("CORPUS-VERIFIED (   )")
