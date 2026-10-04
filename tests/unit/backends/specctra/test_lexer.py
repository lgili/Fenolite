# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Specctra lexer (capability specctra-dsn, "Specctra syntax"). Every text here is authored for
Fenolite."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from fenolite.backends.specctra.lexer import SNode, dumps, is_word, number, parse, writable
from fenolite.core.errors import FormatError

DATA = Path(__file__).resolve().parents[3] / "data" / "specctra"
FILES = ("two_pads.dsn", "two_pads.ses")

AUTHORED = """(pcb demo
  (parser
    (string_quote ")
    (space_in_quoted_tokens on)
  )
  (resolution um 10)
  (unit um)
  (network
    (net "A (1)" (pins R1-1 "R 2-2"))
    (net B)
  )
)
"""


def test_reads_lists_words_and_strings() -> None:
    tree = parse(AUTHORED)
    assert tree.head == "pcb" and tree.words == ("demo",)
    assert [node.head for node in tree.lists] == ["parser", "resolution", "unit", "network"]
    resolution = tree.first("resolution")
    assert resolution is not None and resolution.items == ("um", "10")
    network = tree.first("network")
    assert network is not None
    first, second = network.all("net")
    assert first.words == ("A (1)",)
    pins = first.first("pins")
    assert pins is not None and pins.items == ("R1-1", "R 2-2")
    assert second.items == ("B",)
    assert tree.first("wiring") is None


def test_round_trip_of_an_authored_text() -> None:
    tree = parse(AUTHORED)
    printed = dumps(tree)
    assert parse(printed) == tree
    assert dumps(parse(printed)) == printed


@pytest.mark.parametrize("name", FILES)
def test_round_trip_of_an_authored_file(name: str) -> None:
    """Scenario "Round trip of an authored file"."""
    text = (DATA / name).read_text(encoding="utf-8")
    tree = parse(text, file=name)
    assert parse(dumps(tree)) == tree


def test_unbalanced_input() -> None:
    """Scenario "Unbalanced input"."""
    with pytest.raises(FormatError) as caught:
        parse("(pcb x (unit um)", file="x.dsn")
    assert caught.value.offset == 0 and caught.value.file == "x.dsn"


@pytest.mark.parametrize(
    ("text", "offset", "message"),
    [
        ("", 0, "holds no list"),
        ("   ", 3, "holds no list"),
        ("pcb", 0, "must start with a list"),
        ("(pcb x))", 7, "after the end"),
        ("(pcb x) (pcb y)", 8, "after the end"),
        ("(pcb ())", 6, "must start with a keyword"),
        ("((a))", 1, "must start with a keyword"),
        ('(pcb "open)', 5, "not closed"),
        ("(pcb (string_quote x))", 5, "string_quote needs"),
        ("(pcb (string_quote))", 5, "string_quote needs"),
        ("(pcb (space_in_quoted_tokens maybe))", 5, "needs on or off"),
        ("(", 0, "not closed"),
    ],
)
def test_malformed_input(text: str, offset: int, message: str) -> None:
    with pytest.raises(FormatError) as caught:
        parse(text)
    assert caught.value.offset == offset
    assert message in str(caught.value)


def test_offsets_are_bytes() -> None:
    with pytest.raises(FormatError) as caught:
        parse("(pcb µ (a ())")
    assert caught.value.offset == len("(pcb µ (a (".encode())


def test_declared_quote_character() -> None:
    """Scenario "Declared quote character"."""
    text = '(pcb x (parser (string_quote $) (space_in_quoted_tokens on)) (net $A (1)$ "B"))'
    tree = parse(text)
    net = tree.first("net")
    assert net is not None and net.items == ("A (1)", '"B"')
    printed = dumps(tree)
    assert '(net $A (1)$ "B")' in printed
    assert "(string_quote $)" in printed
    assert parse(printed) == tree


def test_quote_before_a_declaration_is_the_double_quote() -> None:
    tree = parse('(pcb "a(b)" (parser (string_quote ")))')
    assert tree.words == ("a(b)",)


def test_blank_ends_a_string_without_the_declaration() -> None:
    tree = parse('(pcb (net "A B"))')
    net = tree.first("net")
    assert net is not None and net.items == ("A", 'B"')


def test_blank_kept_after_the_declaration() -> None:
    tree = parse('(pcb (space_in_quoted_tokens on) (net "A B" "") (space_in_quoted_tokens off) (net "C D"))')
    first, second = tree.all("net")
    assert first.items == ("A B", "")
    assert second.items == ("C", 'D"')


def test_node_offsets_do_not_take_part_in_equality() -> None:
    assert parse("(a (b c))") == parse("(a\n\n   (b   c)\n)")
    inner = parse("(a   (b c))").first("b")
    assert inner is not None and inner.offset == 5


def test_dumps_layout() -> None:
    tree = SNode("pcb", ("x", SNode("unit", ("um",)), SNode("net", ("A B",)), "tail"))
    with pytest.raises(ValueError, match="holds a blank"):
        dumps(tree)
    tree = SNode(
        "pcb",
        ("x", SNode("space_in_quoted_tokens", ("on",)), SNode("net", ("A B", "", "p;q", "it's")), "tail"),
    )
    assert dumps(tree) == (
        '(pcb x\n  (space_in_quoted_tokens on)\n  (net "A B" "" "p;q" "it\'s")\n  tail\n)\n'
    )
    assert parse(dumps(tree)) == tree


@pytest.mark.parametrize("name", ['a"b', "a\nb", "a\rb"])
def test_dumps_refuses_a_name_the_syntax_cannot_carry(name: str) -> None:
    with pytest.raises(ValueError, match="cannot carry"):
        dumps(SNode("net", (name,)))
    assert not writable(name)


def test_word_rules() -> None:
    assert is_word("GND") and is_word("F.Cu") and is_word("R1-1") and is_word("+3V3") and is_word("/a/b")
    for text in ("", "a b", "a(b", "a)b", "a;b", "a'b", 'a"b', "a\tb", "a\nb"):
        assert not is_word(text), text
    assert is_word('a"b', quote="$") and not is_word("a$b", quote="$")
    assert writable("a b (c)") and writable("")


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("0", Fraction(0)),
        ("12", Fraction(12)),
        ("-5000", Fraction(-5000)),
        ("+7", Fraction(7)),
        ("10000.5", Fraction(100005, 10)),
        ("12.", Fraction(12)),
        (".5", Fraction(1, 2)),
        ("-0.1", Fraction(-1, 10)),
    ],
)
def test_numbers_are_exact(text: str, value: Fraction) -> None:
    assert number(text) == value


@pytest.mark.parametrize("text", ["", "abc", "1e3", "1/2", "1.2.3", "--1", "0x10", "."])
def test_not_a_number(text: str) -> None:
    with pytest.raises(FormatError):
        number(text, file="x.ses", offset=3)
