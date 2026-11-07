# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original exact-cache geometry and qualification controls (c0340)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad import derived_teardrops as derived
from fenolite.backends.kicad.sexpr import parse

ZONE = """(zone (net "N") (layer "F.Cu") (priority 12)
 (attr (teardrop (type padvia))) (hatch edge 0.5)
 (connect_pads (clearance 0)) (min_thickness 0.0254)
 (fill yes (thermal_gap 0.3) (thermal_bridge_width 0.3))
 (polygon (pts (xy 0 0) (xy 2 0) (xy 1 2)))
 (filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 2 0) (xy 1 2))))"""
PARENT = """(footprint "Own" (at 1 1) (layer "F.Cu")
 (pad "1" smd circle (at 0 0) (size 1 1) (layers "F.Cu")
 (net "N") (teardrops (enabled yes))))
 (segment (start 1 1) (end 1 3) (width 0.2) (layer "F.Cu") (net "N"))"""


def board(zones: str = ZONE, parent: str = PARENT):
    return parse(f"(kicad_pcb {parent} {zones})")


def test_cyclic_reverse_exact_rational_ring_and_priority_ordinal_equivalence():
    original = derived.regions(board(), {"N": ("R1-1", "R2-1")})
    changed = ZONE.replace("priority 12", "priority 19").replace('net "N"', 'net "Other"')
    changed = changed.replace("(xy 0 0) (xy 2 0) (xy 1 2)", "(xy 1.000 2) (xy 2 0) (xy 0 0)")
    assert derived.regions(board(changed), {"Other": ("R1-1", "R2-1")}) == original


@pytest.mark.parametrize(
    "change",
    [
        lambda z: z.replace("(xy 1 2)", "(xy 1 2.000000001)", 1),
        lambda z: z.replace("(xy 1 2)", "(xy 1 2.000000001)"),
        lambda z: z.replace("min_thickness 0.0254", "min_thickness 0.0255"),
        lambda z: z.replace('layer "F.Cu"', 'layer "B.Cu"'),
        lambda z: z + z,
        lambda z: z.replace('(filled_polygon (layer "F.Cu")', '(filled_polygon (island yes) (layer "F.Cu")'),
    ],
)
def test_geometry_settings_layer_holes_and_duplicate_multiplicity_are_not_ignored(change):
    assert derived.regions(board(change(ZONE)), {"N": ("R1-1",)}) != derived.regions(
        board(), {"N": ("R1-1",)}
    )


@pytest.mark.parametrize(
    "zone",
    [
        ZONE.replace("(xy 1 2)", "(arc (start 1 2))"),
        ZONE.replace('(net "N")', '(net "unknown")'),
        ZONE.replace("(min_thickness 0.0254)", "(min_thickness 0.0254) (min_thickness 0.0254)"),
        ZONE.replace("(hatch edge 0.5)", "(mystery_effect 1)"),
    ],
)
def test_unknown_or_malformed_cache_refuses(zone):
    with pytest.raises(ValueError):
        derived.regions(board(zone), {"N": ("R1-1",)})


def test_only_explicit_padvia_with_enabled_attached_parent_qualifies():
    assert derived.qualifies(board())
    assert not derived.qualifies(board(parent=PARENT.replace("enabled yes", "enabled no")))
    assert not derived.qualifies(board(parent=""))
    assert not derived.qualifies(board(parent=PARENT.replace("(start 1 1)", "(start 1 1.6)")))
    assert not derived.qualifies(board(ZONE.replace("type padvia", "type trackend")))
    assert not derived.qualifies(board(parent=PARENT.replace('(net "N")', '(net "Other")')))
    assert not derived.qualifies(board(parent=PARENT.replace("at 1 1", "at 20 20")))


def test_normal_zone_priority_is_never_normalized_or_classified_as_derived():
    normal = ZONE.replace("(attr (teardrop (type padvia)))", "")
    assert derived.regions(board(normal), {"N": ("R1-1",)}) == ()
    assert not derived.qualifies(board(normal))


@pytest.mark.parametrize(
    "replacement",
    [
        ("(priority 12)", "(priority nope)"),
        ("(priority 12)", "(priority -1)"),
        ("(hatch edge 0.5)", "(hatch edge nope)"),
        ("(connect_pads (clearance 0))", "(connect_pads (mystery_effect 1))"),
        ("(min_thickness 0.0254)", "(min_thickness -0.0254)"),
        ("(fill yes", "(fill sometimes"),
        ("(thermal_gap 0.3)", "(thermal_gap bad)"),
        ("(xy 0 0) (xy 2 0) (xy 1 2)", "(xy 0 0) (xy 1 0) (xy 2 0)"),
    ],
)
def test_malformed_effectful_metadata_and_degenerate_rings_cannot_be_stripped(replacement):
    with pytest.raises(ValueError):
        derived.regions(board(ZONE.replace(*replacement)), {"N": ("R1-1",)})


def test_stripped_private_copy_preserves_every_other_original_ast_child():
    source = board(ZONE + '(zone (net "N") (layer "F.Cu") (priority 99))')
    stripped = derived.without_regions(source)
    assert stripped.children == tuple(
        child for child in source.children if child is not source.nodes("zone")[0]
    )
    assert source.nodes("zone")[1].find("priority").atoms()[0].value == "99"


def test_track_crossing_parent_body_with_both_endpoints_outside_is_exactly_qualified():
    parent = PARENT.replace("(start 1 1) (end 1 3)", "(start 0 1) (end 2 1)")
    assert derived.qualifies(board(parent=parent))
    assert not derived.qualifies(
        board(parent=parent.replace("(start 0 1) (end 2 1)", "(start 0 1.6) (end 2 1.6)"))
    )
    # c0413: a non-quarter pose qualifies when its bounded contact test settles.
    assert derived.qualifies(board(parent=PARENT.replace("(at 1 1)", "(at 1 1 45)")))


@pytest.mark.parametrize(
    "shape,size,radius,inside,outside",
    [
        ("circle", (2, 2), 0, (1, 0), (1, 1)),
        ("rect", (2, 2), 0, (1, 1), (2, 0)),
        ("oval", (4, 2), 0, (2, 0), (2, 1)),
        ("roundrect", (4, 2), 1, (1, 1), (2, 1)),
    ],
)
def test_exact_parent_shapes_retain_capsule_corner_and_boundary_distinctions(
    shape, size, radius, inside, outside
):
    from fractions import Fraction

    parent = derived._Parent(
        (Fraction(0), Fraction(0)),
        "N",
        ("F.Cu",),
        shape,
        tuple(Fraction(v) for v in size),
        0,
        Fraction(radius),
    )
    assert parent.contains(tuple(Fraction(v) for v in inside))
    assert not parent.contains(tuple(Fraction(v) for v in outside))
    assert parent.intersects((Fraction(-3), Fraction(0)), (Fraction(3), Fraction(0)))
    assert not parent.intersects((Fraction(-3), Fraction(3)), (Fraction(3), Fraction(3)))


def test_exact_circle_tangent_and_quarter_turn_rect_use_no_epsilon():
    from fractions import Fraction

    circle = derived._Parent(
        (Fraction(0), Fraction(0)), "N", ("F.Cu",), "circle", (Fraction(2), Fraction(2)), 0
    )
    assert circle.intersects((Fraction(-2), Fraction(1)), (Fraction(2), Fraction(1)))
    above = Fraction(1) + Fraction(1, 10**12)
    assert not circle.intersects((Fraction(-2), above), (Fraction(2), above))
    rectangle = derived._Parent(
        (Fraction(0), Fraction(0)), "N", ("F.Cu",), "rect", (Fraction(4), Fraction(2)), 90_000_000
    )
    assert rectangle.contains((Fraction(1), Fraction(2)))
    assert not rectangle.contains((Fraction(2), Fraction(1)))


def test_complete_keyhole_fill_retains_hole_coordinates_and_bridge_multiplicity():
    outer_and_hole = (
        "(xy 0 0) (xy 4 0) (xy 4 4) (xy 0 4) (xy 0 0) (xy 1 1) (xy 1 3) (xy 3 3) (xy 3 1) (xy 1 1) (xy 0 0)"
    )
    changed = ZONE.replace(
        '(filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 2 0) (xy 1 2)))',
        '(filled_polygon (layer "F.Cu") (pts ' + outer_and_hole + "))",
    )
    baseline = derived.regions(board(changed), {"N": ("R1-1",)})
    assert (
        derived.regions(board(changed.replace("(xy 3 3)", "(xy 3 3.000000001)")), {"N": ("R1-1",)})
        != baseline
    )
    assert (
        derived.regions(board(changed.replace("(xy 1 1) (xy 0 0)", "(xy 0 0)")), {"N": ("R1-1",)}) != baseline
    )


def test_non_simple_ring_crossings_and_vertices_are_retained_exactly_without_winding_assumption():
    vertices = "(xy 0 0) (xy 4 0) (xy 1 3) (xy 1 -1) (xy 4 3)"
    changed = ZONE.replace("(xy 0 0) (xy 2 0) (xy 1 2)", vertices)
    source = board(changed)
    counts = derived.crossing_counts(source)
    assert counts["rings_with_proper_crossings"] == 2
    assert counts["proper_edge_pair_crossings"] > 0
    assert derived.qualifies(source)
    baseline = derived.regions(source, {"N": ("R1-1",)})
    assert (
        derived.regions(board(changed.replace("(xy 1 -1)", "(xy 1 -1.000000001)")), {"N": ("R1-1",)})
        != baseline
    )
    assert derived.regions(board(changed.replace("(xy 1 -1)", "(xy 1 1)")), {"N": ("R1-1",)}) != baseline


STACK = '(layers (0 "F.Cu" signal) (4 "In1.Cu" signal) (6 "In2.Cu" signal) (2 "B.Cu" signal))'
VIA = '(via (at 1 1) (size 1) (drill 0.3) (layers "F.Cu" "B.Cu") (net "N") (teardrops (enabled yes)))'
INNER_TRACK = '(segment (start 1 1) (end 1 3) (width 0.2) (layer "In1.Cu") (net "N"))'


def test_via_declared_endpoint_span_includes_exact_interior_stack_layers():
    source = board(ZONE.replace('"F.Cu"', '"In1.Cu"'), STACK + VIA + INNER_TRACK)
    assert derived.qualifies(source)
    assert derived._parents(source)[0].layers == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def test_blind_via_span_excludes_layers_outside_its_exact_declared_endpoints():
    via = VIA.replace('(layers "F.Cu" "B.Cu")', '(layers "F.Cu" "In1.Cu")')
    assert derived.qualifies(board(ZONE.replace('"F.Cu"', '"In1.Cu"'), STACK + via + INNER_TRACK))
    outside = board(
        ZONE.replace('"F.Cu"', '"In2.Cu"'), STACK + via + INNER_TRACK.replace('"In1.Cu"', '"In2.Cu"')
    )
    assert not derived.qualifies(outside)


@pytest.mark.parametrize(
    "stack,via",
    [
        ("", VIA),
        (STACK, VIA.replace('"B.Cu"', '"missing.Cu"')),
        (STACK, VIA.replace('"B.Cu"', '"F.Cu"')),
        (STACK.replace('(6 "In2.Cu" signal)', '(6 "In1.Cu" signal)'), VIA),
        (STACK.replace('(6 "In2.Cu" signal)', '(4 "In2.Cu" signal)'), VIA),
        (STACK, VIA.replace('(layers "F.Cu" "B.Cu")', '(layers "F.Cu" "In1.Cu" "B.Cu")')),
    ],
)
def test_missing_unknown_duplicate_or_invalid_copper_span_never_defaults_to_two_layers(stack, via):
    assert not derived.qualifies(board(ZONE.replace('"F.Cu"', '"In1.Cu"'), stack + via + INNER_TRACK))


@pytest.mark.parametrize("anchor", ("rect", "circle"))
def test_explicit_custom_anchor_subset_can_qualify_without_replacing_physical_primitive(anchor):
    custom = PARENT.replace("smd circle", "smd custom").replace(
        '(net "N") (teardrops',
        f"(options (clearance outline) (anchor {anchor})) "
        '(primitives (gr_circle (center 0 0) (end 0.1 0) (width 0) (fill yes))) (net "N") (teardrops',
    )
    source = board(parent=custom)
    assert derived.qualifies(source)
    assert source.nodes("footprint")[0].nodes("pad")[0].atoms()[2].value == "custom"
    assert source.nodes("footprint")[0].nodes("pad")[0].find("primitives") is not None


def _primitive(primitive: str, pose: str = "(at 0 0)", footprint: str = "(at 1 1)") -> str:
    custom = PARENT.replace("smd circle", "smd custom").replace(
        '(net "N") (teardrops',
        f'(options (clearance outline) (anchor rect)) (primitives {primitive}) (net "N") (teardrops',
    )
    custom = custom.replace("(at 0 0)", pose).replace("(at 1 1)", footprint)
    return custom.replace("(start 1 1) (end 1 3)", "(start 5 1) (end 5 3)")


SHIFTED = ZONE.replace("(xy 0 0) (xy 2 0) (xy 1 2)", "(xy 4 0) (xy 6 0) (xy 5 2)")


@pytest.mark.parametrize(
    "primitive",
    [
        "(gr_circle (center 4 0) (end 4.5 0) (width 0) (fill yes))",
        "(gr_line (start 0 0) (end 4 0) (width 1))",
        "(gr_poly (pts (xy 3.5 -0.5) (xy 4.5 -0.5) (xy 4.5 0.5) (xy 3.5 0.5)) (width 0) (fill yes))",
        "(gr_rect (start 3.5 -0.5) (end 4.5 0.5) (width 0) (fill yes))",
        "(gr_circle (center 4 0) (end 4.5 0) (stroke (width 0)) (fill solid))",
    ],
)
def test_custom_primitive_copper_outside_the_anchor_attaches_its_cache(primitive):
    """c0413: a line stroke, a filled circle, polygon or rectangle is a known copper subset."""
    assert derived.qualifies(board(SHIFTED, _primitive(primitive)))


@pytest.mark.parametrize(
    "primitive",
    [
        "(gr_circle (center 4 0) (end 4.5 0) (width 0) (fill no))",
        "(gr_circle (center 4 0) (end 4.5 0) (width 0))",
        "(gr_arc (start 3.5 0) (mid 4 0.5) (end 4.5 0) (width 1))",
        "(gr_line (start 0 0) (end 4 0) (width 0))",
        "(gr_line (start 0 0) (end 4 0))",
        "(gr_poly (pts (xy 3.5 -0.5) (arc (start 4.5 -0.5) (mid 5 0) (end 4 0.5))) (fill yes))",
        "(gr_bbox (start 3.5 -0.5) (end 4.5 0.5))",
    ],
)
def test_unbounded_or_unfilled_primitives_add_no_parent_copper(primitive):
    assert not derived.qualifies(board(SHIFTED, _primitive(primitive)))


def test_primitives_turn_with_the_pad_and_stay_off_bottom_footprints():
    # (4, 0) in the pad frame lies at (0, -4) from the pad when the pad turns by 90°.
    line = "(gr_line (start 0 0) (end 4 0) (width 1))"
    turned = _primitive(line, "(at 0 0 90)").replace("(start 5 1) (end 5 3)", "(start 1 -3) (end 1 -5)")
    zone = ZONE.replace("(xy 0 0) (xy 2 0) (xy 1 2)", "(xy 0 -3) (xy 2 -3) (xy 1 -5)")
    assert derived.qualifies(board(zone, turned))
    assert not derived.qualifies(board(SHIFTED, _primitive(line, "(at 0 0 90)")))
    back = _primitive(line).replace('(layer "F.Cu")', '(layer "B.Cu")', 1)
    assert not derived.qualifies(board(SHIFTED, back))


def test_a_polygon_primitive_needs_an_exact_pose():
    poly = "(gr_poly (pts (xy 3.5 -0.5) (xy 4.5 -0.5) (xy 4.5 0.5) (xy 3.5 0.5)) (width 0) (fill yes))"
    assert derived.qualifies(board(SHIFTED, _primitive(poly, "(at 0 0 180)", "(at 9 1 180)")))
    # At 30° only the anchor and the bounded strokes count; this cache touches the polygon alone.
    assert not derived.qualifies(board(SHIFTED, _primitive(poly, "(at 0 0 30)", "(at 1 1 30)")))


@pytest.mark.parametrize(
    "options",
    [
        "",
        "(options (clearance outline))",
        "(options (anchor triangle))",
        "(options (anchor rect) (anchor rect))",
        "(options (anchor rect) (mystery 1))",
        "(options (clearance mystery) (anchor rect))",
        '(options (clearance outline) (anchor "rect"))',
    ],
)
def test_unknown_missing_or_malformed_custom_options_never_guess_an_anchor(options):
    custom = PARENT.replace("smd circle", "smd custom").replace(
        '(net "N") (teardrops', options + ' (net "N") (teardrops'
    )
    assert not derived.qualifies(board(parent=custom))


def test_drill_offset_parent_refuses_until_shifted_body_is_supported():
    parent = PARENT.replace("(size 1 1)", "(size 1 1) (drill 0.3 (offset 2 0))")
    assert not derived.qualifies(board(parent=parent))


def test_arc_chord_is_not_substituted_for_actual_copper_attachment():
    parent = PARENT.replace("(segment (start 1 1) (end 1 3)", "(arc (start 0 1) (mid 1 3) (end 2 1)")
    assert not derived.qualifies(board(parent=parent))


@pytest.mark.parametrize(
    "extra",
    [
        "(padstack (mode custom))",
        "(chamfer_ratio 0.2) (chamfer top_left)",
    ],
)
def test_layer_specific_or_cut_corner_parent_body_is_not_guessed(extra):
    parent = PARENT.replace("smd circle", "smd roundrect").replace(
        "(size 1 1)", "(size 1 1) (roundrect_rratio 0.25) " + extra
    )
    assert not derived.qualifies(board(parent=parent))


def test_arc_actual_endpoint_inside_parent_can_qualify_without_chord_substitution():
    parent = PARENT.replace("(segment (start 1 1) (end 1 3)", "(arc (start 1 1) (mid 2 2) (end 1 3)")
    assert derived.qualifies(board(parent=parent))


@pytest.mark.parametrize("shape", ("rect", "roundrect"))
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
def test_exact_offset_body_contact_moves_without_changing_original_hole(shape, angle):
    from fractions import Fraction

    x, y = Fraction(2), Fraction(0)
    for _ in range(angle // 90):
        x, y = y, -x
    parent = PARENT.replace("smd circle", "thru_hole " + shape).replace("(at 0 0)", f"(at 0 0 {angle})")
    parent = parent.replace("(size 1 1)", "(size 1 1) (drill 0.3 (offset 2 0))")
    if shape == "roundrect":
        parent = parent.replace("(size 1 1)", "(size 1 1) (roundrect_rratio 0.25)")
    root = board(parent=parent)
    pad = root.nodes("footprint")[0].nodes("pad")[0]
    at = pad.find("at")
    assert derived._parents(root)[0].center == (Fraction(1) + x, Fraction(1) + y)
    assert pad.find("at") is at and tuple(a.value for a in at.atoms()) == ("0", "0", str(angle))


def test_supported_offset_qualifies_actual_shifted_contact_and_refuses_unshifted_one():
    parent = PARENT.replace("smd circle", "thru_hole rect").replace(
        "(size 1 1)", "(size 1 1) (drill 0.3 (offset 2 0))"
    )
    shifted = parent.replace("(start 1 1) (end 1 3)", "(start 3 1) (end 3 3)")
    region = ZONE.replace("(xy 0 0) (xy 2 0) (xy 1 2)", "(xy 2 0) (xy 4 0) (xy 3 2)")
    assert derived.qualifies(board(region, shifted))
    assert not derived.qualifies(board(parent=parent))


@pytest.mark.parametrize(
    "offset", ["(offset 0.0000000001 0)", "(offset bad 0)", "(offset 1)", "(offset 1 0 0)"]
)
def test_inexact_or_malformed_offsets_are_not_rounded_or_guessed(offset):
    parent = PARENT.replace("smd circle", "thru_hole rect").replace(
        "(size 1 1)", f"(size 1 1) (drill 0.3 {offset})"
    )
    assert not derived.qualifies(board(parent=parent))


def test_convex_hull_clearance_keeps_the_anchor_as_copper():
    custom = PARENT.replace("smd circle", "smd custom").replace(
        '(net "N") (teardrops', '(options (clearance convexhull) (anchor rect)) (net "N") (teardrops'
    )
    assert derived.qualifies(board(parent=custom))


def test_non_quarter_rect_uses_its_turned_body():
    from fractions import Fraction

    turned = derived._Parent(
        (Fraction(0), Fraction(0)),
        "N",
        ("F.Cu",),
        "rect",
        (Fraction(4), Fraction(2, 5)),
        30_000_000,
        margin=derived.MARGIN,
    )
    # Along the turned long side (cos 30°, -sin 30°): inside, though outside the unturned body.
    assert turned.contains((Fraction(13, 10), Fraction(-3, 4)))
    # Inside the unturned body, outside the turned one.
    assert not turned.contains((Fraction(3, 2), Fraction(0)))
    assert turned.intersects((Fraction(13, 10), Fraction(-3, 4)), (Fraction(5), Fraction(5)))
    assert not turned.intersects((Fraction(3, 2), Fraction(0)), (Fraction(3, 2), Fraction(1, 10)))


def test_a_contact_the_bound_cannot_settle_refuses():
    from fractions import Fraction

    circle = derived._Parent(
        (Fraction(0), Fraction(0)),
        "N",
        ("F.Cu",),
        "circle",
        (Fraction(2), Fraction(2)),
        30_000_000,
        margin=derived.MARGIN,
    )
    assert circle.contains((Fraction(1, 2), Fraction(0)))
    with pytest.raises(ValueError, match="undecidable"):
        circle.contains((Fraction(1), Fraction(0)))
    with pytest.raises(ValueError, match="error bound"):
        derived._Parent(
            (Fraction(0), Fraction(0)), "N", ("F.Cu",), "circle", (Fraction(2), Fraction(2)), 30_000_000
        )
    far = derived._Parent(
        (Fraction(5000), Fraction(0)), "N", ("F.Cu",), "circle", (Fraction(2), Fraction(2)), 30_000_000,
        margin=derived.MARGIN,
    )  # fmt: skip
    with pytest.raises(ValueError, match="bounded board frame"):
        far.contains((Fraction(5000), Fraction(0)))


@pytest.mark.parametrize("angle", ("30.0000001", "1e-7"))
def test_a_finer_than_microdegree_pose_refuses(angle):
    assert not derived.qualifies(board(parent=PARENT.replace("(at 1 1)", f"(at 1 1 {angle})")))


def test_turned_footprint_offsets_place_the_pad_on_the_turned_frame():
    # Footprint at 30°, pad offset (2, 0): the pad lies at (1 + 2cos30°, 1 - 2sin30°) = (2.732.., 0).
    parent = PARENT.replace("(at 1 1)", "(at 1 1 30)").replace("(at 0 0)", "(at 2 0 30)")
    parent = parent.replace("(start 1 1) (end 1 3)", "(start 2.732 0) (end 2.732 -2)")
    zone = ZONE.replace("(xy 0 0) (xy 2 0) (xy 1 2)", "(xy 2.2 0.2) (xy 3.2 0.2) (xy 2.7 -1)")
    assert derived.qualifies(board(zone, parent))
    unturned = parent.replace("(start 2.732 0) (end 2.732 -2)", "(start 3 1) (end 3 3)")
    assert not derived.qualifies(board(zone, unturned))
