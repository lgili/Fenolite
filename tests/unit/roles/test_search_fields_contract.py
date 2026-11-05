# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0366 typed hard/soft/unknown data contract, before field compilation."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from fenolite.core.coords import Point
from fenolite.core.ids import content_hash
from fenolite.geometry import Thick
from fenolite.routing.search_fields import Copper, Fields, Ground, Influence, Provenance, Spacing
from fenolite.verify import load_register


def provenance() -> Provenance:
    return Provenance(*(content_hash(name) for name in ("board", "roles", "profile", "fill")))


def test_packet_keeps_hard_soft_and_unknown_information_distinct() -> None:
    hard = Spacing("SIG", "BUS", 3_000_000, "high-voltage", "requirements")
    soft = Influence("SIG", "SW", 1_000_000)
    fields = Fields(
        provenance(),
        ("F.Cu", "B.Cu"),
        spacings=(hard,),
        influences=(soft,),
        unknowns=("ground:GND:B.Cu:stale",),
        reference_expected=True,
    )
    assert fields.spacings[0].distance == 3_000_000
    assert not fields.ground and fields.unknowns
    assert fields.fingerprint == replace(fields).fingerprint
    with pytest.raises(FrozenInstanceError):
        fields.ground = ()  # type: ignore[misc]


@pytest.mark.parametrize("value", [-1, 0.5, True])
def test_negative_or_noninteger_inputs_cannot_become_software_rewards(value) -> None:
    with pytest.raises(ValueError):
        Influence("SIG", "SW", value)
    with pytest.raises(ValueError):
        Spacing("SIG", "BUS", value, "high-voltage", "requirements")


def test_zero_is_an_explicit_valid_user_bound_not_an_absent_limit() -> None:
    assert Spacing("SIG", "BUS", 0, "high-voltage", "requirements").distance == 0
    fields = Fields(provenance(), ("F.Cu",), missing=(("SIG", "roles.limit-missing:BUS"),))
    assert fields.missing and not fields.spacings


def test_each_provenance_input_and_the_payload_affect_identity() -> None:
    fields = Fields(provenance(), ("F.Cu",))
    for name in ("board", "roles", "profile", "fill"):
        assert (
            replace(
                fields, provenance=replace(fields.provenance, **{name: content_hash("changed")})
            ).fingerprint
            != fields.fingerprint
        )
    assert replace(fields, influences=(Influence("SIG", "SW", 1),)).fingerprint != fields.fingerprint


def test_acceleration_cache_does_not_affect_identity() -> None:
    shape = Thick((Point(0, 0), Point(1, 1)), 1)
    fields = Fields(provenance(), ("F.Cu",), copper=(Copper("SW", "F.Cu", shape, "track"),))
    before = fields.fingerprint
    object.__setattr__(shape, "_pieces", ((0, 0, 1, 1),))
    assert fields.fingerprint == before


def test_mutable_collections_and_bad_fingerprints_are_rejected() -> None:
    with pytest.raises(ValueError):
        Fields(provenance(), ["F.Cu"])
    with pytest.raises(ValueError):
        Ground("GND", "B.Cu", [Point(0, 0), Point(1, 0), Point(1, 1)])
    with pytest.raises(ValueError):
        Provenance("not-a-digest", *("0" * 64 for _ in range(3)))


def test_evidence_hypotheses_are_registered_before_compiler_implementation() -> None:
    root = Path(__file__).resolve().parents[3]
    registered = {row.id for row in load_register(root / "docs" / "hypotheses.md")}
    assert {"H-G-SEARCH-ROLE-FIELDS", "H-G-SEARCH-ROLE-COSTS", "H-K-SEARCH-ROLE-DRC"} <= registered
