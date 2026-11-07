# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Current-fill, scoped limits and confirmed role provenance in c0366 compilation."""

from dataclasses import replace

import pytest
from _rolefieldbench import field_bench
from _searchbench import MM, point

from fenolite.analysis.requirements import DistanceReq, NetSelector, Requirements
from fenolite.cli._search_fields import compile_fields
from fenolite.model.rules import NetRole, RoleLimit, RoleSet


@pytest.mark.parametrize("four", [False, True])
def test_only_current_saved_fill_becomes_reference(four: bool) -> None:
    job, _, roles = field_bench(four=four)
    compiled = compile_fields(job.design, (), roles)
    assert compiled.fields.ground
    assert {g.layer for g in compiled.fields.ground} == {job.layers[1]}
    assert compiled.pour.state_of("zon_ground", job.layers[1]) == "saved_fill"
    assert compiled.fields.spacings[0].distance == MM


@pytest.mark.parametrize("state", ["missing", "stale", "island"])
def test_unavailable_stale_and_floating_fill_never_become_reference(state: str) -> None:
    job, _, roles = field_bench(ground=state)
    fields = compile_fields(job.design, (), roles).fields
    assert not fields.ground and any(s.startswith("ground:") for s in fields.unknowns)


def test_unconfirmed_switch_role_is_not_a_hard_or_soft_constraint() -> None:
    job, _, roles = field_bench(switch="inferred")
    fields = compile_fields(job.design, (), roles).fields
    assert not fields.spacings and not fields.influences
    assert "unconfirmed-role:WALL" in fields.unknowns
    assert roles.role_of("WALL").source == "inferred"


def test_sensitive_override_is_scoped_and_keeps_its_origin() -> None:
    job, _, roles = field_bench()
    roles = replace(roles, limits=(RoleLimit("switching_distance_nm", 2 * MM, net="SIG"),))
    fields = compile_fields(job.design, (), roles).fields
    own = [r for r in fields.spacings if r.victim == "SIG" and r.aggressor == "WALL"]
    assert len(own) == 1 and own[0].distance == 2 * MM and own[0].origin == "override"


def test_nonsensitive_signal_has_preference_without_extra_hard_switch_limit() -> None:
    job, _, roles = field_bench(sensitive=False)
    fields = compile_fields(job.design, (), roles).fields
    assert not fields.spacings
    assert any(i.victim == "SIG" and i.aggressor == "WALL" for i in fields.influences)


def test_missing_high_voltage_distance_is_never_replaced_by_switching_profile() -> None:
    job, _, _ = field_bench()
    roles = RoleSet(nets=(NetRole("WALL", "high_voltage", "declared", working_mv=500_000),))
    fields = compile_fields(job.design, (), roles).fields
    assert ("SIG", "roles.limit-missing:SIG~WALL") in fields.missing
    assert not fields.spacings


def test_user_distances_are_symmetric_and_take_clearance_creepage_maximum() -> None:
    job, _, _ = field_bench()
    roles = RoleSet(nets=(NetRole("WALL", "high_voltage", "confirmed", working_mv=500_000),))
    requirements = Requirements(
        distances=(
            DistanceReq(
                NetSelector(net="WALL"), NetSelector(net="*"), clearance_nm=2 * MM, creepage_nm=3 * MM
            ),
        )
    )
    fields = compile_fields(job.design, (), roles, requirements=requirements).fields
    assert not fields.missing
    assert {(s.victim, s.aggressor, s.distance) for s in fields.spacings} >= {
        ("SIG", "WALL", 3 * MM),
        ("WALL", "SIG", 3 * MM),
    }
    assert all(s.origin == "requirements" for s in fields.spacings)


def test_changed_board_roles_profile_and_fill_change_fingerprints() -> None:
    job, _, roles = field_bench()
    original = compile_fields(job.design, (), roles).fields
    other = compile_fields(
        job.design, (), replace(roles, limits=(RoleLimit("switching_distance_nm", 2 * MM),))
    ).fields
    assert original.provenance.profile != other.provenance.profile
    assert original.provenance.roles != other.provenance.roles
    assert job.design.board is not None
    changed = replace(
        job.design,
        board=replace(job.design.board, tracks=(replace(job.design.board.tracks[0], end=point(6, 8)),)),
    )
    assert compile_fields(changed, (), roles).fields.provenance.board != original.provenance.board
    missing, _, _ = field_bench(ground="missing")
    assert compile_fields(missing.design, (), roles).fields.provenance.fill != original.provenance.fill
    assert compile_fields(job.design, (), roles).fields.fingerprint == original.fingerprint


def test_user_pair_distance_is_hard_even_without_high_voltage_classification() -> None:
    job, _, roles = field_bench()
    requirements = Requirements(
        distances=(DistanceReq(NetSelector(net="SIG"), NetSelector(net="WALL"), clearance_nm=2 * MM),)
    )
    fields = compile_fields(job.design, (), roles, requirements=requirements).fields
    assert any(
        s.victim == "SIG" and s.aggressor == "WALL" and s.kind == "declared-distance" and s.distance == 2 * MM
        for s in fields.spacings
    )


def test_embedded_and_insulation_requirements_use_conservative_all_layer_projection() -> None:
    job, _, roles = field_bench()
    requirements = Requirements(
        distances=(
            DistanceReq(
                NetSelector(net="SIG"), NetSelector(net="WALL"), embedded_nm=2 * MM, insulation_nm=3 * MM
            ),
        )
    )
    fields = compile_fields(job.design, (), roles, requirements=requirements).fields
    assert not fields.missing
    assert any(
        s.victim == "SIG" and s.kind == "declared-distance" and s.distance == 3 * MM for s in fields.spacings
    )


def test_an_unresolved_voltage_row_is_not_hidden_by_another_matching_row() -> None:
    job, _, roles = field_bench()
    selectors = (NetSelector(net="SIG"), NetSelector(net="WALL"))
    requirements = Requirements(
        distances=(DistanceReq(*selectors, clearance_nm=MM), DistanceReq(*selectors, millivolts=500_000))
    )
    fields = compile_fields(job.design, (), roles, requirements=requirements).fields
    assert ("SIG", "roles.limit-missing:SIG~WALL") in fields.missing


def test_explicit_pair_distance_includes_zone_aggressors_without_a_role() -> None:
    job, _, _ = field_bench()
    requirements = Requirements(
        distances=(DistanceReq(NetSelector(net="SIG"), NetSelector(net="GND"), clearance_nm=MM),)
    )
    fields = compile_fields(job.design, (), RoleSet(), requirements=requirements).fields
    assert any(c.net == "GND" and c.source == "zone-envelope" for c in fields.copper)
    from fenolite.routing.search_fields import Evaluator

    assert not Evaluator(fields).allows("SIG", "F.Cu", (point(2, 2), point(4, 2)), 100_000)
