# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The assembly template and the CSV rendering (capability assembly-outputs, "Assembly template" and "CSV
rendering"; change c0064). Hermetic. Every column name and value here is made up for these tests."""

from __future__ import annotations

import csv
import io
import re
from fractions import Fraction
from pathlib import Path

import pytest
from _assembly import DATA
from hypothesis import given
from hypothesis import strategies as st

import fenolite
from fenolite.exports import assembly
from fenolite.exports.assembly import (
    DEFAULT,
    Column,
    CsvOptions,
    FootprintRotation,
    SideRotation,
    TemplateError,
    format_angle,
    format_length,
    natural_key,
    read_template,
    render_csv,
)

HEADER = "made up"
UNIT_NM = {"mm": 1_000_000, "in": 25_400_000, "mil": 25_400}


def _read(name: str) -> assembly.AssemblyTemplate:
    return read_template((DATA / name).read_text(encoding="utf-8"), file=name)


def _problems(text: str) -> list[tuple[str, str]]:
    with pytest.raises(TemplateError) as caught:
        read_template(text, file="t.toml")
    assert all(i.code == "assembly.template-invalid" and i.severity == "error" for i in caught.value.issues)
    return [(i.where, i.message) for i in caught.value.issues]


# --- the template ---------------------------------------------------------------------------------


def test_default_without_a_file() -> None:
    assert [c.field for c in DEFAULT.bom.columns] == ["refs", "quantity", "value", "footprint"]
    assert all(c.name == c.field for c in (*DEFAULT.bom.columns, *DEFAULT.placement.columns))
    assert DEFAULT.bom.group_by == ("value", "footprint")
    assert (DEFAULT.bom.ref_separator, DEFAULT.bom.exclude_dnp) == (",", True)
    placement = DEFAULT.placement
    assert [c.field for c in placement.columns] == [
        "ref", "value", "footprint_name", "x", "y", "rotation", "side",
    ]  # fmt: skip
    assert (placement.units, placement.origin, placement.y_axis) == ("mm", "page", "up")
    assert (placement.decimals, placement.rotation_decimals) == (4, 2)
    assert (placement.sides.top, placement.sides.bottom) == ("top", "bottom")
    assert (placement.exclude_dnp, placement.smd_only, placement.fiducials) == (True, False, True)
    assert placement.rotation.top == placement.rotation.bottom == SideRotation(1, 0)
    assert placement.rotation.footprint == ()
    assert DEFAULT.csv == CsvOptions(",", "minimal", "lf", True, "utf-8")


def test_an_empty_file_is_the_default() -> None:
    assert read_template("") == DEFAULT
    assert read_template('schema = "fenolite.assembly-template.v0"\n') == DEFAULT


def test_authored_template() -> None:
    template = _read("columns.toml")
    assert [c.name for c in template.bom.columns] == ["Parts", "Count", "Marking", "Shape", "Bin"]
    assert template.bom.columns[-1] == Column("Bin", "property:Bin")
    assert template.bom.group_by == ("value", "footprint", "property:Bin")
    assert (template.bom.ref_separator, template.bom.exclude_dnp) == (",", True)
    assert [c.name for c in template.placement.columns] == ["Part", "Across", "Up", "Face", "Turn"]
    assert template.csv == DEFAULT.csv
    leftover = (template.placement.units, template.placement.origin, template.placement.rotation)
    assert leftover == ("mm", "page", DEFAULT.placement.rotation)


def test_rotation_template() -> None:
    template = _read("rotated.toml")
    placement = template.placement
    assert (placement.units, placement.decimals, placement.origin) == ("mil", 1, "outline")
    assert (placement.sides.top, placement.sides.bottom) == ("upper", "lower")
    assert placement.rotation.top == SideRotation(1, 0)
    assert placement.rotation.bottom == SideRotation(-1, 180_000_000)
    assert placement.rotation.footprint == (
        FootprintRotation("Mini:Mini_QFP*", 90_000_000),
        FootprintRotation("Mini:Mini_R_*", -22_500_000),
    )
    assert template.csv == CsvOptions(";", "all", "crlf", True, "utf-8")
    assert template.bom == DEFAULT.bom


def test_invalid_template_reports_every_problem() -> None:
    with pytest.raises(TemplateError) as caught:
        _read("invalid.toml")
    error = caught.value
    assert type(error).cli_code == "FEN-3004" and error.file == "invalid.toml"
    assert [i.code for i in error.issues] == ["assembly.template-invalid"] * 3
    wheres = [i.where for i in error.issues]
    assert wheres == ["bom.columns[1].field", "bom.colour", "placement.units"]  # file order
    assert "price" in error.issues[0].message and "colour" in error.issues[1].message
    assert "cm" in error.issues[2].message and error.locator == "bom.columns[1].field"


@pytest.mark.parametrize(
    ("text", "where"),
    [
        ("[fab]\nx = 1\n", "fab"),
        ('schema = "other.v9"\n', "schema"),
        ('[csv]\ndelimiter = ",,"\n', "csv.delimiter"),
        ("[csv]\ndelimiter = '\"'\n", "csv.delimiter"),
        ('[csv]\nquote = "none"\n', "csv.quote"),
        ('[csv]\nline_end = "cr"\n', "csv.line_end"),
        ('[csv]\nheader = "yes"\n', "csv.header"),
        ('[csv]\nencoding = "latin-1"\n', "csv.encoding"),
        ("[bom]\ncolumns = []\n", "bom.columns"),
        ('[bom]\ncolumns = [{ name = "A" }]\n', "bom.columns[0].field"),
        ('[bom]\ncolumns = [{ field = "refs" }]\n', "bom.columns[0].name"),
        ('[bom]\ncolumns = [{ name = "A", field = "refs", width = 3 }]\n', "bom.columns[0].width"),
        ('[bom]\ncolumns = [{ name = "A", field = "x" }]\n', "bom.columns[0].field"),
        ('[bom]\ncolumns = [{ name = "A", field = "property:" }]\n', "bom.columns[0].field"),
        ('[bom]\ncolumns = [{ name = "A", field = "refs" }, { name = "A", field = "value" }]\n',
         "bom.columns[1].name"),
        ('[bom]\ngroup_by = ["refs"]\n', "bom.group_by[0]"),
        ('[bom]\ngroup_by = ["value", "value"]\n', "bom.group_by"),
        ('[bom]\nref_separator = ""\n', "bom.ref_separator"),
        ("[bom]\nexclude_dnp = 1\n", "bom.exclude_dnp"),
        ('[placement]\ncolumns = [{ name = "A", field = "quantity" }]\n', "placement.columns[0].field"),
        ("[placement]\ndecimals = 7\n", "placement.decimals"),
        ("[placement]\nrotation_decimals = -1\n", "placement.rotation_decimals"),
        ("[placement]\ndecimals = true\n", "placement.decimals"),
        ('[placement]\norigin = "centre"\n', "placement.origin"),
        ('[placement]\ny_axis = "left"\n', "placement.y_axis"),
        ('[placement]\nsides = { top = "a", middle = "b" }\n', "placement.sides.middle"),
        ("[placement.rotation]\ntop = { sign = 2 }\n", "placement.rotation.top.sign"),
        ("[placement.rotation]\ntop = { sign = 1.0 }\n", "placement.rotation.top.sign"),
        ("[placement.rotation]\nbottom = { offset = 0.0000001 }\n", "placement.rotation.bottom.offset"),
        ("[placement.rotation]\nbottom = { offset = nan }\n", "placement.rotation.bottom.offset"),
        ("[placement.rotation]\nleft = { sign = 1 }\n", "placement.rotation.left"),
        ('[[placement.rotation.footprint]]\nmatch = "A*"\n', "placement.rotation.footprint[0].offset"),
        ("[[placement.rotation.footprint]]\noffset = 90\n", "placement.rotation.footprint[0].match"),
    ],
)  # fmt: skip
def test_each_problem_names_its_key(text: str, where: str) -> None:
    assert [w for w, _ in _problems(text)] == [where]


def test_a_syntax_error_is_a_template_error() -> None:
    problems = _problems("[bom\n")
    assert len(problems) == 1 and "TOML syntax error" in problems[0][1]


def test_offsets_are_exact_microdegrees() -> None:
    template = read_template("[placement.rotation]\ntop = { offset = 0.000001 }\nbottom = { offset = -90 }\n")
    assert template.placement.rotation.top.offset == 1
    assert template.placement.rotation.bottom.offset == -90_000_000


def test_packaged_templates_and_authored_examples() -> None:
    """Only ``DEFAULT`` ships: the package holds no template file, and the authored templates say that
    their names are made up."""
    package = Path(fenolite.__file__).resolve().parent
    shipped = [p for p in (package / "exports").rglob("*") if p.is_file() and p.suffix != ".py"]
    assert [p.name for p in shipped if "__pycache__" not in p.parts] == []
    for path in package.rglob("*.toml"):
        assert "assembly-template" not in path.read_text(encoding="utf-8"), path
    authored = sorted(DATA.glob("*.toml"))
    assert [p.name for p in authored] == ["columns.toml", "invalid.toml", "rotated.toml"]
    for path in authored:
        head = path.read_text(encoding="utf-8").split("schema", 1)[0]
        assert "Authored for Fenolite" in head and HEADER in head, path.name
    names = {c.name for p in authored[:1] + authored[2:] for c in _columns(p)}
    made_up = {"Parts", "Count", "Marking", "Shape", "Bin", "Part", "Across", "Up", "Face", "Turn"}
    assert names - set(assembly.BOM_FIELDS) == made_up  # the rest are Fenolite's own field names


def _columns(path: Path) -> list[Column]:
    template = read_template(path.read_text(encoding="utf-8"))
    return [*template.bom.columns, *template.placement.columns]


# --- printing -------------------------------------------------------------------------------------


def test_lengths_without_floats() -> None:
    assert format_length(132_000_000, "mm", 4) == "132.0000"
    assert format_length(25_400_000, "in", 3) == "1.000"
    assert format_length(1_270_000, "mil", 0) == "50"
    assert format_length(-109_000_000, "mm", 4) == "-109.0000"
    assert format_length(0, "mm", 2) == "0.00" and format_length(-4, "mm", 2) == "0.00"
    assert format_length(1_234_567, "mm", 6) == "1.234567"
    with pytest.raises(ValueError, match="unknown unit"):
        format_length(1, "cm", 2)


def test_rounding_is_half_to_even() -> None:
    assert [format_length(nm, "mm", 0) for nm in (500_000, 1_500_000, 2_500_000, -500_000, -1_500_000)] == [
        "0", "2", "2", "0", "-2",
    ]  # fmt: skip
    assert format_angle(22_500_000, 1) == "22.5" and format_angle(125_000, 2) == "0.12"
    assert format_angle(135_000, 2) == "0.14" and format_angle(270_000_000, 2) == "270.00"


@given(
    nm=st.integers(-(10**12), 10**12),
    units=st.sampled_from(["mm", "in", "mil"]),
    decimals=st.integers(0, 6),
)
def test_lengths_agree_with_exact_fractions(nm: int, units: str, decimals: int) -> None:
    text = format_length(nm, units, decimals)
    exact = Fraction(nm, UNIT_NM[units])
    printed = Fraction(text)
    step = Fraction(1, 10**decimals)
    assert abs(printed - exact) <= step / 2
    if abs(printed - exact) == step / 2:  # a tie goes to the even last digit
        assert (printed / step) % 2 == 0
    assert re.fullmatch(r"-?\d+" + (rf"\.\d{{{decimals}}}" if decimals else ""), text)
    assert not text.startswith("-") or printed != 0


def test_quoting() -> None:
    row = ("R1,R2", "2", '10k "1%"')
    data = render_csv(("a", "b", "c"), [row], CsvOptions(header=False))
    assert data == b'"R1,R2",2,"10k ""1%"""\n'
    quoted = render_csv(("a", "b"), [("x", "")], CsvOptions(quote="all"))
    assert quoted == b'"a","b"\n"x",""\n'


def test_line_ends_and_header() -> None:
    rows = [("R1", "1"), ("R2", "2")]
    data = render_csv(("a", "b"), rows, CsvOptions(line_end="crlf", header=False))
    assert data == b"R1,1\r\nR2,2\r\n" and data.count(b"\r\n") == 2
    assert render_csv(("a", "b"), rows, CsvOptions()) == b"a,b\nR1,1\nR2,2\n"


def test_encoding_and_delimiter() -> None:
    data = render_csv(("a",), [("µ",)], CsvOptions(encoding="utf-8-sig"))
    assert data.startswith(b"\xef\xbb\xbf") and data.decode("utf-8-sig") == "a\nµ\n"
    assert render_csv(("a", "b"), [("1;2", "3")], CsvOptions(delimiter=";")) == b'a;b\n"1;2";3\n'


def test_rendering_is_repeatable() -> None:
    rows = [("R1", "1"), ("R2", "2")]
    assert render_csv(("a", "b"), rows, CsvOptions()) == render_csv(("a", "b"), rows, CsvOptions())


_CELL = st.text(st.characters(codec="utf-8", exclude_characters="\x00\r"), max_size=8)


@given(
    rows=st.lists(st.lists(_CELL, min_size=2, max_size=4), min_size=1, max_size=5),
    delimiter=st.sampled_from([",", ";", "\t", "|"]),
    quote=st.sampled_from(["minimal", "all"]),
    line_end=st.sampled_from(["lf", "crlf"]),
)
def test_a_rendered_table_reads_back(
    rows: list[list[str]], delimiter: str, quote: str, line_end: str
) -> None:
    options = CsvOptions(delimiter=delimiter, quote=quote, line_end=line_end, header=False)  # type: ignore[arg-type]
    text = render_csv((), rows, options).decode("utf-8")
    assert list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)) == rows


def test_natural_order() -> None:
    refs = ["R10", "R2", "C1", "R1", "U1A", "R02"]
    assert sorted(refs, key=lambda r: (natural_key(r), r)) == ["C1", "R1", "R02", "R2", "R10", "U1A"]


def test_the_fiducial_key_and_field() -> None:
    """``[placement]`` takes the boolean ``fiducials`` and the column field ``fiducial`` (change c0118)."""
    from fenolite.exports.assembly import PLACEMENT_FIELDS

    assert PLACEMENT_FIELDS[-1] == "fiducial"
    template = read_template(
        '[placement]\nfiducials = false\ncolumns = [{ name = "Fid", field = "fiducial" }]\n'
    )
    assert template.placement.fiducials is False
    assert [column.field for column in template.placement.columns] == ["fiducial"]
    with pytest.raises(TemplateError):
        read_template('[placement]\nfiducials = "no"\n')
    with pytest.raises(TemplateError):
        read_template('[bom]\ncolumns = [{ name = "Fid", field = "fiducial" }]\n')
