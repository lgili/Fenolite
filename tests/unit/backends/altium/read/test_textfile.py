# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Text forms kept byte for byte (capability altium-project-reader, "Text forms are kept byte for byte")."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fenolite.backends.altium.read.textfile import (
    BOM,
    COMPOUND_SIGNATURE,
    TextLine,
    split_text,
    text_kind,
)
from fenolite.core.errors import FormatError, Issue

DATA = Path(__file__).resolve().parents[4] / "data" / "altium" / "read"


def test_bom_and_lf_kept() -> None:
    data = BOM + b"[Design]\nVersion=1.0\n\n[Document1]\nDocumentPath=a.SchDoc\n"
    form = split_text(data)
    assert form.to_bytes() == data
    assert form.bom == BOM and form.encoding == "utf-8"
    assert {line.end for line in form.lines} == {b"\n"}
    assert form.lines[0] == TextLine(b"[Design]", b"\n") and len(form.lines) == 5


def test_three_line_ends_and_a_last_line_without_one() -> None:
    data = b"a\r\nb\nc\rd"
    issues: list[Issue] = []
    form = split_text(data, file="x.PrjPcb", issues=issues)
    assert [(line.raw, line.end) for line in form.lines] == [
        (b"a", b"\r\n"),
        (b"b", b"\n"),
        (b"c", b"\r"),
        (b"d", b""),
    ]
    assert form.to_bytes() == data
    assert [(i.code, i.severity) for i in issues] == [("altium.text.mixed-line-ends", "info")]


def test_mixed_line_ends_change_no_byte() -> None:
    data = b"[Design]\r\nVersion=1.0\nHierarchyMode=0\r\n"
    issues: list[Issue] = []
    assert split_text(data, issues=issues).to_bytes() == data
    assert [i.code for i in issues] == ["altium.text.mixed-line-ends"]


def test_one_line_end_kind_is_quiet() -> None:
    issues: list[Issue] = []
    split_text(b"a\r\nb\r\n", issues=issues)
    assert issues == []


def test_cr_before_end_of_data() -> None:
    form = split_text(b"a\r")
    assert [(line.raw, line.end) for line in form.lines] == [(b"a", b"\r")]


def test_empty_data() -> None:
    form = split_text(b"")
    assert form.lines == () and form.to_bytes() == b"" and form.encoding == "utf-8"


def test_bytes_outside_utf8_read_as_latin1() -> None:
    data = b"[Parameter1]\r\nName=x\r\nValue=caf\xe9\r\n"
    issues: list[Issue] = []
    form = split_text(data, file="p.PrjPcb", issues=issues)
    assert form.encoding == "latin-1" and form.bom == b""
    assert form.lines[2].text(form.encoding) == "Value=café"
    assert form.to_bytes() == data
    assert [(i.code, i.severity, i.where) for i in issues] == [
        ("altium.text.encoding-assumed", "warning", "p.PrjPcb")
    ]


def test_bom_means_utf8() -> None:
    data = BOM + "Value=°C\n".encode()
    form = split_text(data)
    assert form.encoding == "utf-8" and form.texts() == ("Value=°C",)


def test_compound_file_refused() -> None:
    with pytest.raises(FormatError, match="compound file") as caught:
        split_text(COMPOUND_SIGNATURE + b"\0" * 504, file="x.SchDoc")
    assert caught.value.file == "x.SchDoc" and "x.SchDoc" in str(caught.value)
    assert "compound reader" in str(caught.value)


def test_nul_refused() -> None:
    with pytest.raises(FormatError, match="NUL") as caught:
        split_text(b"[Design]\n\0", file="y.PrjPcb")
    assert caught.value.offset == 9 and caught.value.file == "y.PrjPcb"


_ACCEPTED = st.binary(max_size=300).filter(lambda b: b"\0" not in b and not b.startswith(COMPOUND_SIGNATURE))


@given(_ACCEPTED)
def test_any_accepted_input_comes_back(data: bytes) -> None:
    form = split_text(data)
    assert form.to_bytes() == data
    assert all(line.end for line in form.lines[:-1])
    assert all(line.end in (b"\r\n", b"\n", b"\r") for line in form.lines[:-1])


# --- text_kind ------------------------------------------------------------------------------------


def test_kind_of_the_fixtures() -> None:
    """Scenario "Kind from content": the authored fixtures and a summary-form rule file."""
    found = [
        text_kind((DATA / name).read_bytes(), name=name)
        for name in ("project_utf8.PrjPcb", "jobs.OutJob", "rules_export.RUL", "two_layer.stackup")
    ]
    summary = (
        b"DRC Rules Export File for PCB: board.PcbDoc\r\nRuleKind=Width|RuleName=W|Scope=Board|Minimum=1\r\n"
    )
    found.append(text_kind(summary, name="x.RUL"))
    assert found == ["prjpcb", "outjob", "rul-export", "stackup", "rul-summary"]


@pytest.mark.parametrize(
    ("data", "name", "kind"),
    [
        (COMPOUND_SIGNATURE + b"\0" * 8, "a.PrjPcb", "compound"),
        (BOM + b"|STACKUPVERSION=1|LAYER_V8_0NAME=Top", "", "stackup"),
        (b"[Design]\r\nVersion=1.0\r\n", "", "prjpcb"),
        (b"[Document3]\nDocumentPath=a.SchDoc\n", "", "prjpcb"),
        (b"[OutputJobFile]\nVersion=1.0\n", "", "outjob"),
        (b"SELECTION=FALSE|RULEKIND=Width|NAME=W\xb6\n", "", "rul-export"),
        (b"", "empty.PrjPcb", "prjpcb"),
        (b"", "jobs.outjob", "outjob"),
        (b"", "a.STACKUP", "stackup"),
        (b"hello\n", "a.RUL", "unknown"),
        (b"hello\n", "a.txt", "unknown"),
    ],
)
def test_kind_rules(data: bytes, name: str, kind: str) -> None:
    assert text_kind(data, name=name) == kind
