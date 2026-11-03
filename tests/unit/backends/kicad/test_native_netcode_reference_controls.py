# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original authored netcode-closure guards before any COPY transformation (c0355)."""

from __future__ import annotations

import pytest
from _native_netcode_refs import exact_labelled_partitions, netcode_reference_facts

from fenolite.backends.kicad.sexpr import parse

BASE = '(kicad_pcb (net 0 "") (net 5 "A") (segment (net 5)) (footprint "x" (pad "1" smd circle (net 5 "A"))))'


def test_complete_structural_netcode_roles_keep_no_net():
    assert netcode_reference_facts(parse(BASE)) == {
        "declared": {0: "", 5: "A"},
        "reference_occurrences": 2,
        "no_net_retained": True,
    }


@pytest.mark.parametrize(
    "text",
    (
        BASE.replace('(net 5 "A") (segment', '(net 5 "A") (net 5 "B") (segment'),
        BASE.replace('(net 5 "A") (segment', '(net 5 "A") (net 7 "A") (segment'),
        BASE.replace("(segment (net 5))", "(segment (net 7))"),
        BASE.replace('(pad "1" smd circle (net 5 "A"))', '(pad "1" smd circle (net 5 "B"))'),
        BASE.replace("(segment (net 5))", "(segment)"),
        BASE.replace("(segment (net 5))", "(segment (net 5) (net 5))"),
        BASE.replace('(net 0 "") ', ""),
        BASE[:-1] + " (unknown (member 5)))",
        BASE[:-1] + " (unknown (net 5)))",
        BASE.replace("(segment (net 5))", "(segment (net 5) (unknown 5))"),
    ),
)
def test_malformed_ambiguous_and_outside_netcode_references_refuse(text):
    with pytest.raises(ValueError):
        netcode_reference_facts(parse(text))


@pytest.mark.parametrize(
    "body", (b'{"opaque":{"net":5}}', b'{"opaque":[5]}', b'{"opaque":"5"}', b'{"5":"A"}')
)
def test_json_numeric_netcode_reference_refuses(body):
    with pytest.raises(ValueError, match="JSON"):
        netcode_reference_facts(parse(BASE), {"source.kicad_pro": body})


def test_known_nonreference_exemption_is_an_occurrence_not_interned_atom():
    known = BASE.replace("(segment (net 5))", "(segment (net 5) (start 5 2))")
    assert netcode_reference_facts(parse(known), proved_nonreference_occurrences=frozenset({(2, 1, 0)}))
    unknown = known[:-1] + " (unknown 5))"
    with pytest.raises(ValueError, match="outside"):
        netcode_reference_facts(parse(unknown), proved_nonreference_occurrences=frozenset({(2, 1, 0)}))


@pytest.mark.parametrize("changed", ("swap-A-B", "absorb-NO_NET"))
def test_literal_names_bind_complete_physical_terminals_not_only_partition_sets(changed):
    from fenolite.cli._derived_cache import _raw_bindings

    authored = (
        '(kicad_pcb (net 0 "") (net 5 "A") (net 7 "B") '
        '(footprint "x" (property "Reference" "R1") (pad "1" smd circle (net 5 "A"))) '
        '(footprint "x" (property "Reference" "R2") (pad "1" smd circle (net 7 "B"))))'
    )
    expected = {"A": ("R1-1",), "B": ("R2-1",)}
    assert exact_labelled_partitions(parse(authored), expected) == expected
    if changed == "swap-A-B":
        wrong = authored.replace('(net 5 "A")))', '(net 7 "B")))').replace('(net 7 "B"))))', '(net 5 "A"))))')
        # Both partition member sets still exist, so the unlabelled-only check WOULD pass.
        actual = _raw_bindings(parse(wrong), frozenset(expected.values()))
        assert frozenset(actual.values()) == frozenset(expected.values())
        assert actual != expected
        with pytest.raises(ValueError, match="literal"):
            exact_labelled_partitions(parse(wrong), expected)
    else:
        wrong = authored.replace('(net 5 "A")))', '(net 0 "")))')
        with pytest.raises(ValueError, match="partitions"):
            exact_labelled_partitions(parse(wrong), expected)


def test_unnumbered_omitted_net_is_explicitly_counted_no_net_not_a_dropped_object():
    original = BASE[:-1] + ' (footprint "free" (pad "" np_thru_hole circle)))'
    facts = netcode_reference_facts(parse(original))
    assert facts["unnumbered_no_net_pads"] == 1
    assert facts["reference_occurrences"] == 2


@pytest.mark.parametrize("pad", ('(pad "1" np_thru_hole circle)', '(pad "" unknown circle)'))
def test_numbered_or_unknown_pad_cannot_claim_omitted_no_net(pad):
    with pytest.raises(ValueError):
        netcode_reference_facts(parse(BASE[:-1] + f' (footprint "free" {pad}))'))


def test_exact_empty_dru_version_is_not_a_reference_even_when_it_equals_a_netcode():
    original = BASE.replace("(net 5", "(net 1")
    assert netcode_reference_facts(parse(original), {"source.kicad_dru": b"(version 1)\n"})


@pytest.mark.parametrize(
    "body",
    (b"(version 2)", b"(version 1) (unknown 5)", b'(version 1) (rule "x" (condition "A.NetCode == 5"))'),
)
def test_unknown_or_nonempty_dru_never_gets_an_empty_header_exemption(body):
    with pytest.raises(ValueError):
        netcode_reference_facts(parse(BASE), {"source.kicad_dru": body})


@pytest.mark.parametrize("body", (b'{"opaque":5,"opaque":0}', b'{"opaque":NaN}', b'{"opaque":Infinity}'))
def test_duplicate_or_nonfinite_json_cannot_hide_an_affected_reference(body):
    with pytest.raises(ValueError):
        netcode_reference_facts(parse(BASE), {"source.kicad_pro": body})


@pytest.mark.parametrize(
    "text",
    (
        '(unknownroot (net 0 "") (net 5 "A"))',
        '(kicad_pcb (net 0 "") (net 5 "A") (unknown (footprint "x" (pad "1" smd circle (net 5 "A")))))',
        '(kicad_pcb (net 0 "") (net 5.0 "A"))',
    ),
)
def test_wrong_root_nested_owner_and_noninteger_wire_code_refuse(text):
    with pytest.raises(ValueError):
        netcode_reference_facts(parse(text))
