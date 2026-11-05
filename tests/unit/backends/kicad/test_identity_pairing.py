# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The private level-7 identity preparation (c0384 2.1): complete feature-keyed pairing by declared net
name, the one proven identical-pad duplicate admitted, source aliases kept and listed, every refusal."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad.identity_pairing import apply, pair
from fenolite.backends.kicad.sexpr import Node, dumps, parse

NETS = '(net 0 "") (net {a} "{na}") (net {b} "{nb}")'
PAD = '(pad "{n}" smd circle (at {x} 0) (size 1 1) (layers "F.Cu"){pin} (net {code} "{name}") (uuid "{u}"))'
SEG = '(segment (start {x} 0) (end {x} 5) (width 0.2) (layer "F.Cu") (net {code}) (uuid "{u}"))'
VIA = '(via (at {x} 9) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net {code}) (uuid "{u}"))'


def board(
    ids: dict[str, str],
    *,
    a: int = 1,
    b: int = 2,
    twin: bool = False,
    seg_x: float = 0,
    extra: str = "",
    na: str = "A",
    nb: str = "B",
    pin: str = "",
) -> Node:
    """Pads 1 (net ``na``) and 2 (net ``nb``, pin name ``pin``), optionally a stacked twin of pad 1; one
    segment and one via per net."""
    pin2 = f' (pinfunction "{pin}")' if pin else ""
    pads = [
        PAD.format(n="1", x=0, code=a, name=na, u=ids["p1"], pin=""),
        PAD.format(n="2", x=1, code=b, name=nb, u=ids["p2"], pin=pin2),
    ]
    if twin:
        pads.append(PAD.format(n="1", x=0, code=a, name=na, u=ids["p3"], pin=""))
    footprint = (
        '(footprint "R" (layer "F.Cu") (at 10 10 -90) (property "Reference" "R1") ' + " ".join(pads) + ")"
    )
    copper = (
        SEG.format(x=seg_x, code=a, u=ids["s1"])
        + SEG.format(x=1, code=b, u=ids["s2"])
        + VIA.format(x=0, code=a, u=ids["v1"])
        + VIA.format(x=1, code=b, u=ids["v2"])
    )
    return parse("(kicad_pcb " + NETS.format(a=a, b=b, na=na, nb=nb) + footprint + copper + extra + ")")


SOURCE = {
    k: f"00000000-0000-4000-8000-0000000000{i:02d}"
    for i, k in enumerate(("p1", "p2", "p3", "s1", "s2", "v1", "v2"))
}
TARGET = {
    k: f"11111111-0000-4000-8000-0000000000{i:02d}"
    for i, k in enumerate(("p1", "p2", "p3", "s1", "s2", "v1", "v2"))
}


def test_pairs_by_declared_net_name_and_rewrites_only_identities() -> None:
    source = board(SOURCE, a=15, b=3)  # net codes differ from the target's; names agree
    target = board(TARGET)
    pairing = pair(source, target)
    assert pairing.rewritten == (
        ("pad", TARGET["p1"], SOURCE["p1"]),
        ("pad", TARGET["p2"], SOURCE["p2"]),
        ("segment", TARGET["s1"], SOURCE["s1"]),
        ("segment", TARGET["s2"], SOURCE["s2"]),
        ("via", TARGET["v1"], SOURCE["v1"]),
        ("via", TARGET["v2"], SOURCE["v2"]),
    )  # target file order, every rewritten identity
    assert pairing.identical_pairs == () and pairing.source_aliases_kept == ()
    assert apply(target, pairing) == board(SOURCE)  # identities only; the target's net codes stay


def test_equal_identities_need_no_rewrite() -> None:
    pairing = pair(board(SOURCE), board(SOURCE))
    assert pairing.rewritten == () and apply(board(SOURCE), pairing) == board(SOURCE)


def test_exactly_two_fully_identical_pads_pair_in_file_order_and_are_listed() -> None:
    pairing = pair(board(SOURCE, twin=True), board(TARGET, twin=True))
    assert pairing.identical_pairs == ((TARGET["p1"], TARGET["p3"]),)
    assert ("pad", TARGET["p3"], SOURCE["p3"]) in pairing.rewritten


def test_three_identical_pads_or_two_identical_tracks_refuse() -> None:
    triple = PAD.format(n="1", x=0, code=1, name="A", u="{u}", pin="")
    source = board(SOURCE, twin=True)
    fp = source.nodes("footprint")[0]
    source = source.with_children(
        tuple(
            fp.with_children((*fp.children, parse(triple.format(u="00000000-0000-4000-8000-0000000000ff"))))
            if c is fp
            else c
            for c in source.children
        )
    )
    with pytest.raises(ValueError, match="duplicate"):
        pair(source, source)
    tracks = board(SOURCE, seg_x=1, a=2)  # both segments now identical on net B
    with pytest.raises(ValueError, match="duplicate"):
        pair(tracks, tracks)


def test_an_aliased_source_identity_is_kept_and_listed_never_rewritten() -> None:
    aliased = dict(SOURCE, p2=SOURCE["p1"])  # one source UUID on two different pads
    pairing = pair(board(aliased), board(TARGET))
    assert pairing.source_aliases_kept == tuple(sorted((TARGET["p1"], TARGET["p2"])))
    assert all(row[1] not in pairing.source_aliases_kept for row in pairing.rewritten)
    prepared = apply(board(TARGET), pairing)
    pads = prepared.nodes("footprint")[0].nodes("pad")
    assert [p.nodes("uuid")[0].atoms()[0].value for p in pads] == [TARGET["p1"], TARGET["p2"]]


@pytest.mark.parametrize(
    ("target", "match"),
    [
        (board(TARGET, seg_x=2), "differ"),  # changed geometry
        (board(TARGET, extra=SEG.format(x=4, code=1, u="11111111-0000-4000-8000-0000000000ee")), "differ"),
        (board(dict(TARGET, s2=TARGET["s1"])), "target identity aliases"),
        (board(TARGET, extra='(net 9 "A")'), "two netcodes"),
        # canonical names (coordinator decision 2026-11-05): two nets under one key, either rule
        (board(TARGET, na="{slash}A", extra='(net 9 "/A")'), "share one canonical"),
        (
            board(TARGET, nb="unconnected-(R1-Pad2)", extra='(net 9 "unconnected-single-pad:R1:2")'),
            "share one canonical",
        ),
        # an unconnected-( net of two pads, or one whose name names another pad
        (board(TARGET, na="unconnected-(R1-Pad1)", twin=True), "exactly one pad"),
        (board(TARGET, nb="unconnected-(R9-Pad2)"), "does not derive"),
        (board(TARGET, nb="unconnected-(R1-y-Pad2)", pin="x"), "does not derive"),
        (
            board(TARGET, nb="unconnected-(R1-Pad2)", extra='(net 9 "unconnected-(R1-Pad7)")'),
            "exactly one pad",
        ),
    ],
)
def test_refusals(target: Node, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        pair(board(SOURCE), target)


def test_an_object_net_outside_the_declarations_refuses() -> None:
    bad = parse(
        "(kicad_pcb "
        + NETS.format(a=1, b=2, na="A", nb="B")
        + SEG.format(x=0, code=7, u="11111111-0000-4000-8000-0000000000aa")
        + ")"
    )
    with pytest.raises(ValueError, match="declared netcode"):
        pair(bad, bad)


def _swap_roots(root: Node, first: int, second: int) -> Node:
    roots = [c for c in root.children if isinstance(c, Node) and c.name in ("segment", "arc", "via")]
    a, b = roots[first], roots[second]
    return root.with_children(tuple(b if c is a else a if c is b else c for c in root.children))


def test_order_preparation_moves_root_copper_into_source_order_in_its_own_slots() -> None:
    source = _swap_roots(board(SOURCE), 0, 3)  # source order: v2, s2, v1, s1
    target = board(TARGET)
    pairing = pair(source, target)
    assert pairing.moved == (
        ("segment", TARGET["s1"], 0, 3),
        ("via", TARGET["v2"], 3, 0),
    )
    assert apply(target, pairing) == source
    unordered = apply(target, pairing, order=False)
    assert [c.name for c in unordered.children if isinstance(c, Node)] == [
        c.name for c in target.children if isinstance(c, Node)
    ]


def test_a_stale_order_pairing_refuses() -> None:
    source = _swap_roots(board(SOURCE), 0, 3)
    pairing = pair(source, board(TARGET))
    with pytest.raises(ValueError, match="does not match"):
        apply(_swap_roots(board(TARGET), 0, 1), pairing)


def test_a_stored_slash_pairs_with_its_label_text_and_is_receipted() -> None:
    source, target = board(SOURCE, na="/s/A"), board(TARGET, na="{slash}s{slash}A")
    pairing = pair(source, target)
    assert len(pairing.rewritten) == 6
    assert pairing.canonical_nets == (("b", "slash", "{slash}s{slash}A", "/s/A"),)
    assert apply(target, pairing) == board(SOURCE, na="{slash}s{slash}A")  # identities only, names stay


def test_a_single_pad_unconnected_net_pairs_by_its_pad_in_either_spelling() -> None:
    source = board(SOURCE, nb="unconnected-(R1-Pad2)", pin="x")  # the 9.0.9 demo spelling
    target = board(TARGET, nb="unconnected-(R1-x-Pad2)", pin="x")  # the spelling with the pin name
    pairing = pair(source, target)
    key = "unconnected-single-pad:R1:2"
    assert pairing.canonical_nets == (
        ("a", "unconnected-single-pad", "unconnected-(R1-Pad2)", key),
        ("b", "unconnected-single-pad", "unconnected-(R1-x-Pad2)", key),
    )
    assert len(pairing.rewritten) == 6


def test_an_object_net_name_contradicting_its_canonical_declaration_refuses() -> None:
    target = parse(
        dumps(board(TARGET, na="{slash}A")).replace(
            '(net 1 "{slash}A")\n\t\t\t(uuid', '(net 1 "/A")\n\t\t\t(uuid'
        )
    )
    with pytest.raises(ValueError, match="contradicts"):
        pair(board(SOURCE, na="/A"), target)


def test_a_rewritten_identity_named_elsewhere_refuses_the_preparation() -> None:
    target = board(
        TARGET, extra=f'(group "" (uuid "11111111-0000-4000-8000-0000000000ab") (members "{TARGET["s1"]}"))'
    )
    pairing = pair(board(SOURCE), target)
    with pytest.raises(ValueError, match="referenced elsewhere"):
        apply(target, pairing)


def test_a_written_identity_that_collides_with_another_in_the_board_refuses() -> None:
    clash = f'(gr_text "x" (at 0 0) (layer "F.SilkS") (uuid "{SOURCE["v1"]}"))'
    target = board(TARGET, extra=clash)
    pairing = pair(board(SOURCE), target)
    with pytest.raises(ValueError, match="collides"):
        apply(target, pairing)


ZONE = '(zone (net 1) (net_name "A") (layer "F.Cu") (uuid "11111111-0000-4000-8000-0000000000cd"))'


def test_a_preparation_keeps_every_root_child_but_the_own_identities() -> None:
    from fenolite.backends.kicad.identity_pairing import _without_own_identities

    target = board(TARGET, extra=ZONE)  # a zone is not an electrical object: it keeps its identity
    prepared = apply(target, pair(_swap_roots(board(SOURCE, extra=ZONE), 0, 3), target))
    assert prepared.nodes("zone") == target.nodes("zone")
    assert _without_own_identities(prepared) == _without_own_identities(target)


def test_a_net_name_both_boards_declare_verbatim_takes_no_canonical_rule() -> None:
    # the public RoyalBlue J1 case: one pin, two physical pads numbered alike, on an unconnected-( net that
    # both sides spell alike; it pairs by its name and is never refused as a multi-pad unconnected net
    name = "unconnected-(R1-Pad1)"
    pairing = pair(board(SOURCE, na=name, twin=True), board(TARGET, na=name, twin=True))
    assert pairing.canonical_nets == () and len(pairing.rewritten) == 7
