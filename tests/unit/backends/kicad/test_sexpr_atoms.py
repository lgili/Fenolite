# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Atoms: spelling, validation, string codec and numbers in nanometres (capability kicad-sexpr)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad import Atom, AtomKind, parse

S, N, Q = AtomKind.SYMBOL, AtomKind.NUMBER, AtomKind.STRING


# --- Atoms keep their spelling --------------------------------------------------------------------


def test_trailing_zeros_survive() -> None:
    (atom,) = parse("(ratio 12.000000)").children
    assert isinstance(atom, Atom)
    assert atom.text == "12.000000" and atom.kind == N


def test_leading_plus_is_not_a_number() -> None:
    assert [a.kind for a in parse("(x +0.8 0x10 1.6mm)").atoms()] == [S, S, S]


def test_quoted_digits_are_a_string() -> None:
    first = parse('(pad "1" smd rect)').atoms()[0]
    assert first.text == '"1"' and first.kind == Q and first.value == "1"


CLASSES = [
    *[(t, N) for t in ("0", "-1.5", ".8", "1.", "1e-3", "-0", "2E+5")],
    *[(t, S) for t in ("+1", "1.2.3", "e5", "-", "#PWR", 'a"b', "${KIPRJMOD}/x.pretty")],
    *[(t, Q) for t in ('""', '"a b"')],
]


@pytest.mark.parametrize(("text", "kind"), CLASSES)
def test_classification(text: str, kind: AtomKind) -> None:
    assert Atom(text, kind).kind == kind


# --- Invalid atoms cannot be built ----------------------------------------------------------------


@pytest.mark.parametrize(
    "text", ["", " ", "a b", "(", ")", "a(", "a\nb", "a\rb", '"a', '"a\nb"', '"a"b', '"a\\"']
)
def test_invalid_text(text: str) -> None:
    with pytest.raises(ValueError):
        Atom(text, AtomKind.SYMBOL)
    with pytest.raises(ValueError):
        Atom(text, AtomKind.STRING)


def test_kind_disagrees_with_the_text() -> None:
    with pytest.raises(ValueError):
        Atom("a", AtomKind.NUMBER)
    with pytest.raises(ValueError):
        Atom.symbol("12")


def test_symbol_that_reads_as_a_string() -> None:
    with pytest.raises(ValueError):
        Atom.symbol('"x"')


def test_kind_is_normalised() -> None:
    atom = Atom("a", "symbol")  # type: ignore[arg-type]
    assert atom.kind is AtomKind.SYMBOL and atom == Atom.symbol("a")


# --- String decoding and encoding -----------------------------------------------------------------


def test_decode_table() -> None:
    atom = Atom('"q\\"b\\\\n\\nt\\101\\x42\\e"', Q)
    assert atom.value == 'q"b\\n' + "\n" + "tAB\\e"


@pytest.mark.parametrize(
    ("body", "value"),
    [
        ("\\t\\v\\r", "\t\v\r"),
        ("\\0", "\x00"),
        ("\\7a", "\x07a"),
        ("\\0123", "\n3"),
        ("\\x4", "\\x4"),
        ("\\x4g", "\\x4g"),
        ("\\xffz", "\xffz"),
        ("\\q", "\\q"),
        ("a\\", None),
    ],
)
def test_decode_cases(body: str, value: str | None) -> None:
    if value is None:
        with pytest.raises(ValueError):
            Atom(f'"{body}"', Q)
        return
    assert Atom(f'"{body}"', Q).value == value


def test_control_characters() -> None:
    assert Atom.string("a\x0bb").text == '"a\\013b"'
    with pytest.raises(ValueError):
        Atom.string("a\x00b")


def test_encoder_table() -> None:
    assert Atom.string('q"\\\n\r\tz\x01é').text == '"q\\"\\\\\\n\\r\tz\\001é"'
    assert Atom.string("").text == '""'


def test_value_of_symbols_and_numbers() -> None:
    assert Atom.symbol("F.Cu").value == "F.Cu"
    assert Atom("1.5", N).value == "1.5"


# --- Numbers in integer nanometres ----------------------------------------------------------------


EXACT = [
    ("0.25", 250000),
    ("1e-3", 1000),
    (".8", 800000),
    ("1.", 1000000),
    ("-0", 0),
    ("-1.5", -1500000),
    ("12.000000", 12000000),
    ("2E2", 200000000),
]


@pytest.mark.parametrize(("text", "nm"), EXACT)
def test_exact_conversions(text: str, nm: int) -> None:
    assert Atom(text, N).to_nm() == nm


def test_inexact_value() -> None:
    atom = Atom("1.60000000000001", N)
    with pytest.raises(ValueError):
        atom.to_nm()
    assert atom.to_nm(exact=False) == 1600000
    assert Atom("0.0000005", N).to_nm(exact=False) == 0
    assert Atom("0.0000015", N).to_nm(exact=False) == 2
    assert Atom("-0.0000025", N).to_nm(exact=False) == -2


def test_writing() -> None:
    assert [Atom.from_nm(n).text for n in (2000000, 123457, -500, 0)] == ["2", "0.123457", "-0.0005", "0"]
    for n in (1, -1, 999999, 10**12, -123456789):
        assert Atom.from_nm(n).to_nm() == n


def test_symbol_is_not_a_length() -> None:
    with pytest.raises(ValueError):
        Atom.symbol("signal").to_nm()
    with pytest.raises(ValueError):
        Atom("1e999", N).to_nm()


def test_integers() -> None:
    assert Atom.integer(20260206).to_int() == 20260206
    assert Atom.integer(-3).text == "-3"
    with pytest.raises(ValueError):
        Atom("1.0", N).to_int()
    with pytest.raises(TypeError):
        Atom.integer(1.0)  # type: ignore[arg-type]
