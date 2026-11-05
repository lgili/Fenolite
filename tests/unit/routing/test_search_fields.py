# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0366 hard exclusions, conservative coverage and nonnegative path costs."""

from dataclasses import replace

from _rolefieldbench import field_bench
from _searchbench import MM, point

from fenolite.cli._search_fields import compile_fields
from fenolite.model.rules import RoleSet
from fenolite.routing.octilinear import World, length
from fenolite.routing.search import Limits, search
from fenolite.routing.search_fields import Evaluator, Ground, Spacing


def data(**kwargs):
    job, subject, roles = field_bench(**kwargs)
    fields = compile_fields(job.design, (), roles).fields
    job = replace(job, extra={**job.extra, "search_fields": fields})
    return job, subject, fields, World(job, (), job.extra["outline"])


def test_hard_switch_distance_cannot_be_traded_for_a_shorter_path() -> None:
    job, subject, fields, world = data()
    out = search(job, subject, world, Limits(MM // 2, 40_000, 0), max_length=30 * MM)
    assert out.runs
    assert all(Evaluator(fields).allows("SIG", layer, points, subject.width) for layer, points in out.runs)
    assert any(p.y < 3 * MM or p.y > 7 * MM for _, points in out.runs for p in points)


def test_adjacent_layer_switch_overlap_is_hard_for_sensitive_signals() -> None:
    _, _, fields, _ = data()
    evaluation = Evaluator(fields)
    assert not evaluation.allows("SIG", "B.Cu", (point(5, 5), point(7, 5)), 100_000)
    assert evaluation.allows("SIG", "B.Cu", (point(2, 2), point(3, 2)), 100_000)


def test_high_voltage_projection_is_conservative_on_every_layer() -> None:
    _, _, fields, _ = data(four=True)
    fields = replace(fields, spacings=(Spacing("SIG", "WALL", 2 * MM, "high-voltage", "requirements"),))
    for layer in fields.layers:
        assert not Evaluator(fields).allows("SIG", layer, (point(5, 5), point(7, 5)), 100_000)


def test_validated_ground_coverage_reduces_cost_without_a_negative_reward() -> None:
    _, _, fields, _ = data(sensitive=False)
    evaluation = Evaluator(fields)
    under = evaluation.measure("SIG", "F.Cu", (point(2, 2), point(4, 2)), 100_000)
    assert under.reference_lower_bound == under.length == 2 * MM and under.penalty == 0
    unknown = Evaluator(replace(fields, ground=(), unknowns=("ground:stale",))).measure(
        "SIG", "F.Cu", (point(2, 2), point(4, 2)), 100_000
    )
    assert unknown.reference_lower_bound == 0 and unknown.penalty >= 0
    assert unknown.penalty > under.penalty


def test_midspan_gap_is_not_misreported_as_fully_referenced() -> None:
    _, _, fields, _ = data()
    left = (point(1, 1), point(5, 1), point(5, 9), point(1, 9))
    right = (point(7, 1), point(11, 1), point(11, 9), point(7, 9))
    fields = replace(fields, ground=(Ground("GND", "B.Cu", left), Ground("GND", "B.Cu", right)))
    measured = Evaluator(fields).measure("SIG", "F.Cu", (point(2, 2), point(10, 2)), 100_000)
    assert measured.reference_lower_bound == 0  # conservative lower bound, not a guessed percentage


def test_switching_exposure_is_an_upper_bound_over_full_segments() -> None:
    _, _, fields, _ = data(sensitive=False)
    evaluation = Evaluator(fields)
    near = evaluation.measure("SIG", "F.Cu", (point(5, 5), point(7, 5)), 100_000)
    far = evaluation.measure("SIG", "F.Cu", (point(2, 2), point(4, 2)), 100_000)
    assert near.switching_upper_bound == near.length and far.switching_upper_bound == 0
    assert near.penalty >= near.switching_upper_bound


def test_cost_field_can_prefer_a_longer_path_covered_by_ground() -> None:
    job, subject, fields, world = data(sensitive=False)
    # No copper obstacle: the role policy alone chooses a longer, referenced detour.
    assert job.design.board is not None
    design = replace(job.design, board=replace(job.design.board, tracks=()))
    fields = compile_fields(design, (), RoleSet()).fields
    from fenolite.routing.search_fields import board_fingerprint

    ring = (point(1, 1), point(11, 1), point(11, 4), point(1, 4))
    fields = replace(
        fields,
        provenance=replace(fields.provenance, board=board_fingerprint(design)),
        copper=(),
        influences=(),
        spacings=(),
        ground=(Ground("GND", "B.Cu", ring),),
        reference_expected=True,
    )
    job = replace(job, design=design, extra={**job.extra, "search_fields": fields})
    out = search(
        job, subject, World(job, (), job.extra["outline"]), Limits(MM, 40_000, 0), max_length=30 * MM
    )
    assert out.runs and any(p.y <= 3 * MM for _, points in out.runs for p in points)
    assert sum(length(points) for _, points in out.runs) > 8 * MM


def test_changed_board_or_missing_limit_never_uses_old_fields() -> None:
    job, subject, fields, world = data()
    assert job.design.board is not None
    changed = replace(job, design=replace(job.design, board=replace(job.design.board, tracks=())))
    assert (
        search(changed, subject, world, Limits(MM, 100, 0), max_length=30 * MM).reason == "search-role-stale"
    )
    fields = replace(fields, missing=(("SIG", "roles.limit-missing:SIG~BUS"),))
    job = replace(job, extra={**job.extra, "search_fields": fields})
    assert search(job, subject, world, Limits(MM, 100, 0), max_length=30 * MM).reason == "search-role-limit"
