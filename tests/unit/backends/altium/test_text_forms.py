# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Text outside ASCII (capability altium-schematic-writer, "Text outside ASCII"; change c0086): what each
schematic form carries, the bytes of a value with its ``%UTF8%`` twin, and the refusal that names the
character."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _altium_tree import ASCII_TEXTS, catalog_symbols, documents, read_back, tree_build, tree_model

from fenolite.backends.altium.ascii import (
    CODE_PAGE,
    fold,
    format_record,
    in_code_page,
    record_bytes,
    text_problem,
)
from fenolite.backends.altium.binary import frame_record
from fenolite.backends.altium.read.sch import Parameter
from fenolite.backends.altium.read.sch.props import parse
from fenolite.backends.altium.read.schlib import SchLibComponent, read_schlib
from fenolite.core.errors import Issue
from fenolite.lens.altium import build_altium

ACCENTED = "Indutância 10 µH"


def test_binary_form_accepts_the_code_page() -> None:
    assert CODE_PAGE == "cp1252"
    for text in (ACCENTED, "tolerância ±10 %", "10µF", "R1", "+5V"):
        assert text_problem(text, form="binary") is None, text
    assert text_problem("10µF") is not None  # the default form is the ASCII form
    assert in_code_page("é") and in_code_page("€") and not in_code_page("Ω") and not in_code_page("\x85")


@pytest.mark.parametrize("form", ["ascii", "binary"])
def test_what_no_form_carries(form: str) -> None:
    """A pipe, a line end, an empty text and a surrounding space stay refused in both forms."""
    for text, word in (
        ("A|B", "'|'"),
        ("a\nb", "U+000A"),
        ("a\rb", "U+000D"),
        ("", "empty"),
        (" a", "space"),
        ("a ", "space"),
    ):
        reason = text_problem(text, form=form)  # type: ignore[arg-type]
        assert reason is not None and word in reason, (text, reason)
    assert text_problem("=x", form=form, parameter=True) is not None  # type: ignore[arg-type]
    assert text_problem("=x", form=form) is None  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown schematic form"):
        text_problem("x", form="utf8")  # type: ignore[arg-type]


def test_refusal_names_the_character_and_the_form_that_carries_it() -> None:
    ascii_reason = text_problem(ACCENTED, form="ascii")
    assert ascii_reason is not None and "'â'" in ascii_reason and "U+00E2" in ascii_reason
    assert "the binary form carries it" in ascii_reason
    for form in ("ascii", "binary"):
        reason = text_problem("1 kΩ", form=form)  # type: ignore[arg-type]
        assert reason is not None and "U+03A9" in reason and "no form carries" in reason


def test_bytes_of_a_value_with_its_twin() -> None:
    """The twin comes first and holds UTF-8; the plain value is in the code page; a 7-bit record keeps
    the bytes of ``format_record``."""
    fields = (("RECORD", "41"), ("TEXT", "10µF"), ("NAME", "Comment"))
    assert record_bytes(fields) == b"|RECORD=41|%UTF8%TEXT=10\xc2\xb5F|TEXT=10\xb5F|NAME=Comment"
    plain = (("RECORD", "41"), ("TEXT", "10uF"))
    assert record_bytes(plain) == format_record(plain).encode("ascii")
    props = parse(frame_record(fields)[4:-1])
    assert props.text("TEXT") == "10µF" and props.raw("TEXT") == b"10\xb5F"
    unicode_fields = (("TEXT", "1 kΩ"),)
    assert record_bytes(unicode_fields) == b"|%UTF8%TEXT=1 k\xce\xa9|TEXT=1 k?"
    assert parse(frame_record(unicode_fields)[4:-1]).text("TEXT") == "1 kΩ"
    for bad in ((("TEXT", "a|b"),), (("TE XT", "é"),), ()):
        with pytest.raises(ValueError):
            record_bytes(bad)
    with pytest.raises(ValueError):
        format_record(fields)  # the ASCII form carries no such value


def test_accented_value_in_the_binary_form(tmp_path: Path) -> None:
    """Scenario "Accented value in the binary form": the comment of the component returns the string, and
    so does a parameter value."""
    output = tree_build()
    design = read_back(tmp_path, output)
    parts = {c.ref: c for c in design.circuit.components}
    assert parts["L1"].value == ACCENTED
    assert parts["C1"].properties["Note"] == "tolerância ±10 %"
    power = documents(output)["tree_power.SchDoc"]
    comments = [p for p in power.of_type(Parameter) if p.name == "Comment" and p.text == ACCENTED]
    assert len(comments) == 1 and comments[0].props is not None
    assert comments[0].props.all_keys().index("%UTF8%TEXT") < comments[0].props.all_keys().index("TEXT")


def test_ascii_form_refuses_the_accented_value() -> None:
    output = tree_build(tree_model(), form="ascii")
    assert output.files == {}
    (found,) = [i for i in output.issues if i.code == "altium.text-unwritable"]
    assert "L1 comment" in found.message and "the binary form carries it" in found.message
    # a property is no part of the circuit: it is kept in the model and reported, not refused
    (kept,) = [i for i in output.issues if i.code == "altium.not-lowered" and i.where == "parameters"]
    assert "C1 'Note'" in kept.message
    assert tree_build(tree_model(*ASCII_TEXTS), form="ascii").files


# --- change c0504, D3: degree signs and other compatibility characters --------------------------------
#
# Task 1.1, the paths on dev at 9d7ef2dfd (read from the code and run before the fix):
# - a description ``-40 °C to 125 °C``: written by every path (``°`` is in Windows-1252). Unchanged.
# - a description ``-40 ℃`` in a build, binary or ASCII form (the libraries are binary either way), and
#   through ``schlib.component_record``: written, the plain value as ``-40 ?`` beside a ``%UTF8%`` twin, with
#   no issue (``record_bytes``, ``errors="replace"``).
# - ``-40 ℃`` as a parameter value of a sheet: refused, "outside Windows-1252, which no form carries".
# - ``-40 ℃`` through an edit ``set_property``: ``RecordError`` out of ``Session.apply`` (``FEN-1001``).

DEGREES, CELSIUS = "-40 °C to 125 °C", "-40 ℃"


def _described(description: str) -> tuple[SchLibComponent, list[Issue]]:
    """The library component of the first symbol of the sample, built with ``description``."""
    model = tree_model()
    symbols = catalog_symbols(model)
    lib_id = sorted(symbols)[0]
    symbol = symbols[lib_id]
    symbols[lib_id] = dataclasses.replace(
        symbol, properties={**symbol.properties, "Description": description}
    )
    output = build_altium(model, name="tree", form="binary", sheets="modules", authored_symbols=symbols,
                          symbol_bodies="graphics")  # fmt: skip
    found = [
        c
        for name, data in output.files.items()
        if name.endswith(".SchLib")
        for c in read_schlib(data, file=name).components
        if c.name == lib_id.split(":")[1]
    ]
    assert len(found) == 1, found
    return found[0], list(output.issues)


def test_degree_sign_kept_in_a_description() -> None:
    """Scenario "A degree sign kept": ``°`` is in Windows-1252, so nothing folds."""
    component, issues = _described(DEGREES)
    assert component.description == DEGREES
    assert not [i for i in issues if i.code == "altium.text-folded"]


def test_degree_celsius_is_folded_in_a_description() -> None:
    """Scenario "Degree Celsius in a description": ``℃`` is written as ``°C`` in both twins."""
    component, issues = _described(CELSIUS)
    assert component.description == "-40 °C"
    record = component.records[0]
    assert record.props is not None
    keys = record.props.all_keys()
    assert keys.index("%UTF8%COMPONENTDESCRIPTION") < keys.index("COMPONENTDESCRIPTION")
    [folded] = [i for i in issues if i.code == "altium.text-folded"]
    assert folded.severity == "warning" and "'-40 ℃'" in folded.message and "'-40 °C'" in folded.message


def test_degree_fold_rule() -> None:
    assert fold(CELSIUS) == ("-40 °C", True) and fold(DEGREES) == (DEGREES, False)
    assert fold("1 kΩ") == ("1 kΩ", False)  # U+03A9 has no form in Windows-1252
    assert text_problem(CELSIUS, form="binary") is None
    ascii_reason = text_problem(CELSIUS, form="ascii")
    assert ascii_reason is not None and "the binary form carries it" in ascii_reason
    for ohm in ("1 kΩ", "1 kΩ"):  # the Greek capital omega and the ohm sign, whose form is the omega
        reason = text_problem(ohm, form="binary")
        assert reason is not None and "no form carries" in reason
