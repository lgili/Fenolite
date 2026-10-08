# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Text outside ASCII (capability altium-schematic-writer, "Text outside ASCII"; change c0086): what each
schematic form carries, the bytes of a value with its ``%UTF8%`` twin, and the refusal that names the
character."""

from __future__ import annotations

from pathlib import Path

import pytest
from _altium_tree import ASCII_TEXTS, documents, read_back, tree_build, tree_model

from fenolite.backends.altium.ascii import CODE_PAGE, format_record, in_code_page, record_bytes, text_problem
from fenolite.backends.altium.binary import frame_record
from fenolite.backends.altium.read.sch import Parameter
from fenolite.backends.altium.read.sch.props import parse

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
    for bad in ((("TEXT", "1 kΩ"),), (("TEXT", "a|b"),), (("TE XT", "é"),), ()):
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
