# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Printers, tree equality and locators (capability kicad-sexpr)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from fenolite.backends.kicad import Atom, Node, dumps, first_difference, parse, tree_equal, walk


def test_layout_of_a_pad() -> None:
    node = parse('(pad "1" smd rect (at 1 2) (layers "F.Cu"))')
    assert dumps(node) == '(pad "1" smd rect\n\t(at 1 2)\n\t(layers "F.Cu")\n)\n'


def test_atom_only_list_on_one_line() -> None:
    assert dumps(parse("(version 20260206)")) == "(version 20260206)\n"


def test_atom_after_a_child_list_on_its_own_line() -> None:
    node = parse('(fp_text reference "R1" (at 0 0) hide (effects (font (size 1 1))))')
    assert dumps(node) == (
        '(fp_text reference "R1"\n\t(at 0 0)\n\thide\n\t(effects\n'
        "\t\t(font\n\t\t\t(size 1 1)\n\t\t)\n\t)\n)\n"
    )


def _pts(fourth: str) -> Node:
    xy = ["(xy 0 0)", "(xy 1000.123456 -1000.123456)", "(xy 1000.123456 -1000.123456)", fourth, "(xy 0 0)"]
    return parse("(a (b (c (pts " + " ".join(xy) + "))))")


def test_xy_appended_at_98_columns() -> None:
    lines = dumps(_pts("(xy 10.123456 -10.123456)")).splitlines()
    xy_lines = [line for line in lines if "(xy" in line]
    assert len(xy_lines) == 1 and xy_lines[0].startswith("\t\t\t\t(xy 0 0)") and xy_lines[0].count("(xy") == 5
    four = xy_lines[0][: xy_lines[0].rindex(" (xy")]
    assert len(four) == 98


def test_xy_wrapped_at_99_columns() -> None:
    lines = dumps(_pts("(xy 10.123456 -100.123456)")).splitlines()
    xy_lines = [line for line in lines if "(xy" in line]
    assert [line.count("(xy") for line in xy_lines] == [4, 1]
    assert len(xy_lines[0]) == 99
    assert xy_lines[1] == "\t\t\t\t(xy 0 0)"


def test_xy_packing_only_inside_pts_and_broken_by_arcs() -> None:
    text = (
        "(fp_poly (pts (xy 0 0) (arc (start 2 0) (mid 3 1) (end 2 2)) (xy 0 2) (xy 0 3))"
        " (other (xy 1 1) (xy 2 2)))"
    )
    out = dumps(parse(text))
    assert "\t\t(xy 0 0)\n\t\t(arc\n" in out
    assert "\t\t(xy 0 2) (xy 0 3)\n" in out
    assert "\t\t(xy 1 1)\n\t\t(xy 2 2)\n" in out


def test_idempotence_and_rt0() -> None:
    text = '# c\n(kicad_pcb (version 20260206) (layers (0 "F.Cu" signal)) (gr_text "a\\"b" (at 1 2) hide))'
    once = dumps(parse(text))
    assert dumps(parse(once)) == once
    assert tree_equal(parse(once), parse(text))


def test_comments_on_a_nested_node() -> None:
    child = replace(parse("(b 1)"), comments=("# x",))
    root = Node(Atom.symbol("a"), (child,))
    for style in ("kicad", "compact"):
        with pytest.raises(ValueError):
            dumps(root, style=style)  # type: ignore[arg-type]


def test_invalid_root_comment() -> None:
    with pytest.raises(ValueError):
        dumps(replace(parse("(a)"), comments=("no hash",)))
    with pytest.raises(ValueError):
        dumps(replace(parse("(a)"), comments=("# two\nlines",)))


def test_compact_fragment() -> None:
    assert (
        dumps(parse("(stroke\n\t(width 0.1)\n\t(type solid)\n)"), style="compact")
        == "(stroke (width 0.1) (type solid))"
    )


def test_compact_output_drops_root_comments() -> None:
    root = parse("# note\n(a 1)")
    assert dumps(root, style="compact") == "(a 1)"
    assert tree_equal(parse(dumps(root, style="compact")), replace(root, comments=()))


def test_unknown_style() -> None:
    with pytest.raises(ValueError):
        dumps(parse("(a)"), style="pretty")  # type: ignore[arg-type]


def test_atoms_dump_to_their_text() -> None:
    for atom in (Atom.symbol("locked"), Atom.string("a b"), Atom.from_nm(1500)):
        assert dumps(atom) == atom.text and dumps(atom, style="compact") == atom.text


def test_too_deep_tree_rejected() -> None:
    node = Node(Atom.symbol("a"))
    for _ in range(300):
        node = Node(Atom.symbol("a"), (node,))
    with pytest.raises(ValueError, match="MAX_DEPTH"):
        dumps(node)


def test_spelling_matters() -> None:
    a, b = parse("(a (w 12))"), parse("(a (w 12.0))")
    assert not tree_equal(a, b)
    assert first_difference(a, b) == "/a/w[0]"


@pytest.mark.parametrize(
    ("x", "y", "where"),
    [
        ("(a (w 1))", "(a (w 1))", None),
        ("(a (w 1))", "(b (w 1))", "/a"),
        ("(a (w 1) (w 2))", "(a (w 1) (w 3))", "/a/w[1]"),
        ("(a (w 1))", "(a (w 1) x)", "/a"),
        ("(a (w 1) x)", "(a (w 1) (x))", "/a"),
        ("(a (w (q 1)) (v 2))", "(a (w (q 2)) (v 2))", "/a/w[0]/q[0]"),
        ('(a "1")', "(a 1)", "/a"),
    ],
)
def test_first_difference(x: str, y: str, where: str | None) -> None:
    assert first_difference(parse(x), parse(y)) == where
    assert tree_equal(parse(x), parse(y)) is (where is None)


def test_root_comments_matter() -> None:
    assert not tree_equal(parse("# a\n(x)"), parse("(x)"))
    assert first_difference(parse("# a\n(x)"), parse("(x)")) == "/x"


def test_locator_of_the_second_footprint() -> None:
    board = parse('(kicad_pcb (net 0 "") (footprint "a") (footprint "b" (pad "1")) (footprint "c"))')
    found = dict((loc, node) for loc, node in walk(board))
    assert found["/kicad_pcb/footprint[1]"].atoms()[0].value == "b"
    assert list(found) == [
        "/kicad_pcb",
        "/kicad_pcb/net[0]",
        "/kicad_pcb/footprint[0]",
        "/kicad_pcb/footprint[1]",
        "/kicad_pcb/footprint[1]/pad[0]",
        "/kicad_pcb/footprint[2]",
    ]
