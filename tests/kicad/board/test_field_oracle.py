# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint fields pass the field oracle (capability kicad-oracle; hypotheses H-K-FIELD-FRAME,
H-K-FIELD-JUSTIFY, H-K-FIELD-DRC, H-K-FIELD-OUTSIDE and H-K-FIELD-RESAVE; change c0030).

The benches of ``_fieldbench`` are built through the model, written with ``write_board`` for target 9 on
both majors and also for target 10 on 10.0.6, and judged by ``pcb drc`` with ``min_silk_clearance`` 0.1 mm.
Only ``silk_edge_clearance`` items are read, each matched to its field by the uuid of the ``property``
node. Every outcome is also a ``field-bench-*`` probe, pinned per ``kicad-cli`` version.
"""

from __future__ import annotations

import _fieldbench
import pytest
from _probes import PROBES, major, run

from fenolite.backends.kicad.fields import field_anchor, field_angle, outside_box
from fenolite.backends.kicad.pcb import read_board

pytestmark = pytest.mark.needs_kicad
TARGETS = [9, pytest.param(10, marks=pytest.mark.kicad_min_major(10))]
MM = 1_000_000


def hits(name: str, target: int, group: str) -> list[tuple[_fieldbench.Case, list[object]]]:
    found = _fieldbench.observed(name, target)
    assert found is not None, f"kicad-cli wrote no DRC report for the {name} bench"
    cases, _ = _fieldbench.bench(name, target)
    return [(case, list(found[f"{case.group}:{case.key}"])) for case in cases if case.group == group]


def test_bench_probes_are_registered() -> None:
    assert set(_fieldbench.bench_probes()) <= set(PROBES)


def test_benches_hold_what_the_spec_names() -> None:
    edge = _fieldbench.edge_cases(9)
    anchors = [c for c in edge if c.group == "anchors"]
    assert len(anchors) == 12 and all(len(c.component.ref) == 10 for c in edge)
    assert {(c.footprint.side, c.footprint.rotation // MM) for c in anchors} == set(_fieldbench.PLACEMENTS)
    assert {c.footprint.lib_ref for c in anchors} == {"Mini:Mini_R_0603", "Mini:Mini_QFP-32_7x7mm_P0.8mm"}
    outside = _fieldbench.outside_cases(9)
    placed = [c for c in outside if c.group == "outside"]
    assert len(placed) == 32 and len([c for c in outside if c.group == "control"]) == 8
    for case in placed:
        box, anchor = outside_box(case.footprint), field_anchor(case.footprint, case.reference)
        outside_x = anchor.x < box.x0 or anchor.x > box.x1
        outside_y = anchor.y < box.y0 or anchor.y > box.y1
        assert outside_x != outside_y and field_angle(case.footprint, case.reference) == 0, case.key


@pytest.mark.parametrize("target", TARGETS)
def test_written_bench_reads_back(target: int) -> None:
    """The bench text holds what the model says: the reader gives the same fields back."""
    cases, _ = _fieldbench.bench("edge", target)
    design = read_board(_fieldbench.bench_text("edge", target))
    assert design.board is not None
    for case, footprint in zip(cases, design.board.footprints, strict=True):
        again = next(f for f in footprint.fields if f.name == "Reference")
        assert again.native_ids == case.reference.native_ids
        assert field_anchor(footprint, again) == field_anchor(case.footprint, case.reference), case.key
        assert field_angle(footprint, again) == field_angle(case.footprint, case.reference), case.key


@pytest.mark.parametrize("target", TARGETS)
def test_anchors(target: int) -> None:
    """A Reference crossing the edge, on top and bottom footprints at 0°, 30° and 90°: one violation whose
    item names the field and lies at ``field_anchor`` (H-K-FIELD-FRAME, H-K-FIELD-DRC)."""
    for case, found in hits("edge", target, "anchors"):
        assert len(found) == 1, (case.key, found)
        item = found[0]
        want = field_anchor(case.footprint, case.reference)
        assert item.description == f"Reference field of {case.component.ref}", case.key  # type: ignore[attr-defined]
        dx, dy = abs(item.position.x - want.x), abs(item.position.y - want.y)  # type: ignore[attr-defined]
        assert dx <= _fieldbench.TOLERANCE and dy <= _fieldbench.TOLERANCE, (case.key, dx, dy)
    assert run(f"field-bench-anchors-t{target}") == "present"


@pytest.mark.parametrize("target", TARGETS)
def test_moved_inside(target: int) -> None:
    """Each of those fields moved inside the board gives no violation, in a report that holds the violation
    of a crossing control on the same board."""
    ((control, found),) = hits("inside", target, "control")
    assert len(found) == 1, control.key
    for case, found in hits("inside", target, "inside"):
        assert found == [], case.key
    assert run(f"field-bench-inside-t{target}") == "absent"


@pytest.mark.parametrize("target", TARGETS)
def test_angle(target: int) -> None:
    """On a footprint at 90° with the anchor 2 mm below the top edge: board angle 0° is silent and board
    angle 90° gives one violation, so the stored angle is the board angle."""
    counts = {case.key: len(found) for case, found in hits("edge", target, "angle")}
    assert counts == {"board-0": 0, "board-90": 1}
    assert run(f"field-bench-angle-t{target}") == "present"


@pytest.mark.parametrize("target", TARGETS)
def test_justify_and_mirror(target: int) -> None:
    """With the anchor 1 mm inside the left edge: ``left`` silent and ``right`` one on the top side, and the
    reverse for a mirrored field on the bottom side (H-K-FIELD-JUSTIFY)."""
    counts = {case.key: len(found) for case, found in hits("edge", target, "justify")}
    assert counts == {"top-left": 0, "top-right": 1, "bottom-left": 1, "bottom-right": 0}
    assert run(f"field-bench-justify-t{target}") == "present"


@pytest.mark.parametrize("target", TARGETS)
def test_keep_upright(target: int) -> None:
    """A left-justified Reference at board angle 180°, 1 mm inside the left edge, is silent; with
    ``(unlocked yes)`` inserted into its node it gives one violation."""
    counts = {case.key: len(found) for case, found in hits("edge", target, "upright")}
    assert counts == {"kept": 0, "unlocked": 1}
    assert "(unlocked yes)" in _fieldbench.bench_text("edge", target)
    assert run(f"field-bench-upright-t{target}") == "present"


@pytest.mark.parametrize("target", TARGETS)
def test_hidden(target: int) -> None:
    """A hidden Reference that crosses the edge gives no violation (H-K-FIELD-DRC)."""
    ((case, found),) = hits("edge", target, "hidden")
    assert not case.reference.visible and found == []
    assert run(f"field-bench-hidden-t{target}") == "absent"


@pytest.mark.parametrize("target", TARGETS)
def test_outside(target: int) -> None:
    """A field set by ``place_outside`` beside a cut-out equal to the courtyard box gives no violation, for
    each side, on top and bottom footprints at 0°, 30° and 90°; a control whose anchor lies 0.1 mm inside
    the box gives one (H-K-FIELD-OUTSIDE)."""
    for case, found in hits("outside", target, "control"):
        assert len(found) == 1, (case.key, found)
    for case, found in hits("outside", target, "outside"):
        assert found == [], (case.key, found)
    assert run(f"field-bench-outside-t{target}") == "absent"


def test_silent_edge_check_is_recorded() -> None:
    """With ``min_silk_clearance`` 0, 9.0.9 reports no crossing field and 10.0.6 does; the outcome is pinned
    by the probe results file and never fails this test."""
    assert run("field-edge-zero") in ("present", "absent")


@pytest.mark.kicad_min_major(10)
def test_resave() -> None:
    """On 10.0.6 a bench whose fields were moved, turned, hidden, resized and justified reads back with
    equal fields after ``pcb upgrade --force`` (H-K-FIELD-RESAVE)."""
    assert major() >= 10
    assert run("field-bench-resave") == "equal"
