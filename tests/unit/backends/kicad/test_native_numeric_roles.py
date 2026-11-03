# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original closed-role ledger controls before a numeric-code COPY experiment (c0355)."""

import pytest
from _native_numeric_roles import numeric_role_ledger, project_role_ledger

from fenolite.backends.kicad.sexpr import parse
from fenolite.core.errors import FormatError


def ledger(body):
    return numeric_role_ledger(parse('(kicad_pcb (net 0 "") (net 5 "A") ' + body + ")"))


def test_physical_coordinate_is_known_only_under_its_complete_declared_owner():
    known = ledger("(segment (net 5) (start 5 7) (end 8 9) (width 0.25))")
    assert known["remaining_unknown_numeric_occurrences"] == 0
    assert known["invalid_known_role_instances"] == 0
    entry = known["paths"]["kicad_pcb/segment/start"]
    assert entry["role"] == "track-coordinate" and entry["source"] and entry["proof"]
    wrong = ledger("(unknown (segment (net 5) (start 5 7)))")
    assert wrong["remaining_unknown_numeric_occurrences"] == 3


def test_unknown_xy_plot_and_glyph_paths_are_not_exempted_by_spelling_or_values():
    result = ledger(
        "(unknown (pts (xy 5 7))) (setup (pcbplotparams (hpglpennumber 5))) "
        '(gr_text "X" (render_cache "X" 5 (polygon (pts (xy 5 7)))))'
    )
    assert result["remaining_unknown_numeric_occurrences"] == 3
    assert result["invalid_known_role_instances"] > 0


def test_known_numeric_role_wrong_arity_or_type_remains_a_blocker():
    for body in ("(segment (start 5))", '(segment (start 5 "7"))'):
        result = ledger(body)
        assert result["invalid_known_role_instances"] == 1


def test_numeric_layer_heads_are_counted_and_not_automatically_exempted():
    result = ledger('(unknown (layers (5 "In5.Cu" signal)))')
    assert result["remaining_unknown_numeric_occurrences"] == 1
    assert result["paths"]["kicad_pcb/unknown/layers/<numeric-head>"]["numeric_occurrences"] == 1


def test_scoped_footprint_keepout_has_only_explicit_no_net_zero_and_empty_name():
    good = ledger('(footprint "x" (zone (net 0) (net_name "") (keepout)))')
    assert good["invalid_known_role_instances"] == 0
    for body in (
        '(footprint "x" (zone (net 5) (net_name "A") (keepout)))',
        '(footprint "x" (zone (net 0.0) (net_name "") (keepout)))',
        '(footprint "x" (zone (net 0) (net_name "A") (keepout)))',
        '(footprint "x" (zone (net 0) (net_name "")))',
    ):
        assert ledger(body)["invalid_known_role_instances"] == 1


def test_net_name_conflict_is_not_hidden_by_an_unchanged_numeric_partition():
    for body in ('(zone (net 5) (net_name "B"))', '(zone (net 5) (net_name "A") (net_name "A"))'):
        assert ledger(body)["invalid_known_role_instances"] == 1


def test_existing_zone_enum_and_drill_roles_are_closed_to_their_declared_shapes():
    good = ledger(
        "(zone (net 5) (priority 5) (hatch edge 0.5) "
        "(fill (island_removal_mode 1) (island_area_min 5))) "
        '(footprint "x" (pad "1" thru_hole oval (net 5 "A") '
        "(drill oval 0.5 0.7 (offset 5 7)) (zone_connect 1)))"
    )
    assert good["remaining_unknown_numeric_occurrences"] == 0
    assert good["invalid_known_role_instances"] == 0
    for body in (
        "(zone (net 5) (fill (island_removal_mode 7)))",
        "(zone (net 5) (fill (island_removal_mode 1.0)))",
        '(footprint "x" (pad "1" smd circle (net 5 "A") (zone_connect 4)))',
        '(footprint "x" (pad "1" thru_hole oval (net 5 "A") (drill unknown 5)))',
    ):
        assert ledger(body)["invalid_known_role_instances"] == 1


def test_project_unknown_keys_refuse_even_when_they_hold_zero_or_false():
    for body in (b'{"meta":{"version":3},"future_code":0}', b'{"meta":{"version":3},"future_code":false}'):
        result = project_role_ledger(body)
        assert result["remaining_unknown_paths"] == 1
        assert result["paths"]["/future_code"]["role"] == "UNKNOWN"
    known = project_role_ledger(b'{"meta":{"version":3}}')
    assert known["remaining_unknown_paths"] == known["invalid_known_role_instances"] == 0


def test_project_wrong_container_and_scalar_do_not_inherit_a_known_role():
    for body in (b'{"meta":[]}', b'{"meta":{"version":"3"}}', b'{"meta":{"version":false}}'):
        assert project_role_ledger(body)["invalid_known_role_instances"] == 1
    fake_array = project_role_ledger(b'{"net_settings":{"classes":{"*":{"name":"Default"}}}}')
    assert fake_array["invalid_known_role_instances"] == 1
    assert fake_array["remaining_unknown_paths"] >= 1


def test_literal_slash_key_never_clobbers_the_nested_documented_version_path():
    result = project_role_ledger(b'{"meta":{"version":3},"meta/version":5}')
    assert result["paths"]["/meta/version"]["role"] == "project-schema-version"
    assert result["paths"]["/meta~1version"]["role"] == "UNKNOWN"
    assert result["remaining_unknown_paths"] == 1


@pytest.mark.parametrize("body", (b'{"meta":{"version":3,"version":3}}', b'{"meta":{"version":NaN}}'))
def test_project_duplicates_and_nonfinite_are_not_a_profiled_shape(body):
    with pytest.raises(FormatError):
        project_role_ledger(body)


def test_declared_layer_record_ordinal_is_a_separate_closed_identifier_namespace():
    result = ledger('(layers (5 "F.SilkS" user "Silkscreen") (0 "F.Cu" signal))')
    assert result["remaining_unknown_numeric_occurrences"] == 0
    assert result["invalid_known_role_instances"] == 0
    assert result["paths"]["kicad_pcb/layers/<numeric-head>"]["role"] == "layer-record-ordinal"
    for rows in (
        '(5.0 "F.SilkS" user)',
        '(5 "F.SilkS" unknown)',
        '(5 "F.SilkS" user 5)',
        '(5 "UnknownLayer" user)',
        '(5 "F.SilkS" user) (5 "B.SilkS" user)',
    ):
        invalid = ledger("(layers " + rows + ")")
        assert invalid["invalid_known_role_instances"] > 0


def cache_body(cache='(render_cache "X" 0 (polygon (pts (xy 1 2) (xy 3 4) (xy 5 6))))', extra=""):
    return (
        '(gr_text "X" (at 10 20 0) (layer "F.SilkS") (effects (font (face "Authored"))) '
        + cache
        + extra
        + ")"
    )


def test_glyph_cache_is_closed_to_measured_owner_text_angle_layer_and_ordered_vertices():
    result = ledger(cache_body())
    assert result["remaining_unknown_numeric_occurrences"] == 0
    assert result["invalid_known_role_instances"] == 0
    for cache in (
        '(render_cache "Y" 0 (polygon (pts (xy 1 2) (xy 3 4) (xy 5 6))))',
        '(render_cache "X" 90 (polygon (pts (xy 1 2) (xy 3 4) (xy 5 6))))',
        '(render_cache "X" 0 (polygon (pts (xy 1 2) (xy 3 4))))',
        '(render_cache "X" 0 (polygon (pts (xy 1 "2") (xy 3 4) (xy 5 6))))',
        '(render_cache "X" 0 (polygon (pts (xy 1 2) (xy 3 4) (xy 5 6))) (future 0))',
        '(render_cache "X" 0 (polygon (pts (xy 1 2) (xy 3 4) (xy 5 6)) (future 0)))',
    ):
        assert ledger(cache_body(cache))["invalid_known_role_instances"] > 0
    for body in (
        cache_body().replace('"F.SilkS"', '"F.Cu"'),
        cache_body().replace('(face "Authored")', ""),
        cache_body().replace("(at 10 20 0)", "(at 10 20 0) (at 10 20 0)"),
        cache_body(extra='(render_cache "X" 0)'),
    ):
        assert ledger(body)["invalid_known_role_instances"] > 0
    wrong_owner = ledger("(unknown " + cache_body() + ")")
    assert wrong_owner["remaining_unknown_numeric_occurrences"] > 0


def test_footprint_connection_enum_requires_direct_owner_unique_integer_0_through_3():
    for code in range(4):
        result = ledger(f'(footprint "x" (zone_connect {code}))')
        assert result["remaining_unknown_numeric_occurrences"] == 0
        assert result["invalid_known_role_instances"] == 0
    for values in ("4", "-1", "1.0", "1 2", '"1"'):
        assert ledger(f'(footprint "x" (zone_connect {values}))')["invalid_known_role_instances"] > 0
    assert ledger('(footprint "x" (zone_connect 1) (zone_connect 1))')["invalid_known_role_instances"] > 0
    assert ledger('(unknown (footprint "x" (zone_connect 1)))')["remaining_unknown_numeric_occurrences"] > 0


@pytest.mark.parametrize("bad", (3, -1, 1.0, "1", True, None))
def test_erc_pin_map_rejects_unknown_enum_or_noninteger_cells(bad):
    import json

    matrix = [[0] * 12 for _ in range(12)]
    matrix[0][0] = bad
    result = project_role_ledger(json.dumps({"erc": {"pin_map": matrix}}).encode())
    assert result["invalid_known_role_instances"] > 0


def test_erc_pin_map_has_exact_shape_and_closed_ownership():
    import json

    matrix = [[(row + col) % 3 for col in range(12)] for row in range(12)]
    result = project_role_ledger(json.dumps({"erc": {"pin_map": matrix}}).encode())
    assert result["remaining_unknown_paths"] == result["invalid_known_role_instances"] == 0
    for bad in (matrix[:11], [row[:11] for row in matrix], {"0": matrix[0]}):
        result = project_role_ledger(json.dumps({"erc": {"pin_map": bad}}).encode())
        assert result["invalid_known_role_instances"] > 0
    extra = project_role_ledger(json.dumps({"erc": {"pin_map": matrix, "future": 0}}).encode())
    assert extra["remaining_unknown_paths"] == 1
    wrong = project_role_ledger(json.dumps({"unknown": {"pin_map": matrix}}).encode())
    assert wrong["remaining_unknown_paths"] > 0
    duplicate = b'{"erc":{"pin_map":[],"pin_map":[]}}'
    with pytest.raises(FormatError):
        project_role_ledger(duplicate)
