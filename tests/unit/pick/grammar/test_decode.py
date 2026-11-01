# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Decode of MPNs (change c0263, "Decode", "Opaque tails", "Validity matrix"; scenarios "An excluded
combination", "A decode names where it failed", "A tail is kept, not read")."""

from __future__ import annotations

from _grammars import CHIP_R, MLCC, authored, edited, mlcc

from fenolite.core.evidence import Level
from fenolite.pick.grammar.decode import Failure, decode, parse_mpn


def test_a_decode_gives_every_parameter() -> None:
    found = decode("EX05C471JBT", authored())
    assert found.issues == () and len(found.decoded) == 1
    entry = found.decoded[0].as_json()
    assert {key: entry[key] for key in ("mpn", "family", "value", "case", "dielectric", "tolerance", "rating",
                                        "packing", "suffix", "in_matrix")} == {  # fmt: skip
        "mpn": "EX05C471JBT", "family": "Example:EX_MLCC", "value": "470pF", "case": "0805",
        "dielectric": "C0G", "tolerance": "5%", "rating": "50V", "packing": "reel", "suffix": None,
        "in_matrix": True,
    }  # fmt: skip
    assert entry["device"] == "Example:EX_MLCC@EX05C471JBT" and entry["evidence"] == "INFERRED"


def test_an_excluded_combination() -> None:
    """Scenario "An excluded combination" (the exit code 0 is in test_family_cmd.py)."""
    found = decode("EX03R104KBT", authored())
    assert [item.in_matrix for item in found.decoded] == [False]
    assert [item.code for item in found.issues] == ["family.decode-outside-matrix"]
    assert found.issues[0].severity == "warning"


def test_a_decode_names_where_it_failed() -> None:
    """Scenario "A decode names where it failed"."""
    found = decode("EX07C471JBT", authored())
    assert found.decoded == () and [item.code for item in found.issues] == ["family.decode-no-match"]
    assert found.failures == (Failure("Example:EX_MLCC", 2, "size"),)
    assert "Example:EX_MLCC fails at position 2, field size" in found.issues[0].message
    assert decode("ZZ1", authored()).failures == ()  # no family's literal prefix matches
    assert parse_mpn(mlcc(), "EX03R104KAT9") == Failure("Example:EX_MLCC", 11, "end")  # tail = "none"
    assert parse_mpn(mlcc(), "EX03R1O4KAT") == Failure("Example:EX_MLCC", 5, "value")


def test_a_tail_is_kept_not_read() -> None:
    """Scenario "A tail is kept, not read"."""
    found = decode("EXR06F1002T-Q1", authored())
    assert len(found.decoded) == 1
    entry = found.decoded[0]
    assert entry.candidate.suffix == "-Q1" and entry.as_json()["suffix"] == "-Q1"
    assert entry.evidence.level is Level.UNVERIFIED and entry.as_json()["value"] == "10kΩ"
    assert [item.code for item in found.issues] == ["family.suffix-opaque"]
    assert found.issues[0].severity == "info"
    assert parse_mpn(edited(CHIP_R, 'tail = "opaque"', 'tail = "none"'), "EXR06F1002T-Q1") == Failure(
        "Example:EX_CHIP_R", 11, "end"
    )


def test_two_families_that_parse_one_mpn() -> None:
    twin = edited(MLCC, 'id = "Example:EX_MLCC"', 'id = "Example:EX_MLCC_TWIN"')
    found = decode("EX05C471JBT", [mlcc(), twin])
    assert [item.code for item in found.issues] == ["family.decode-ambiguous"]
    assert "Example:EX_MLCC and Example:EX_MLCC_TWIN" in found.issues[0].message


def test_values_outside_the_series_decode_outside_the_matrix() -> None:
    found = decode("EX03R123KAT", [mlcc()])  # "123" is 12 nF, an E12 value
    assert found.decoded[0].in_matrix
    found = decode("EX03R133KAT", [mlcc()])  # 13 nF is not an E12 value
    assert not found.decoded[0].in_matrix
