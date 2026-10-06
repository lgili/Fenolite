# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Import of Altium sheet templates (change c0046, capability sheet-templates): "Altium sheet template
reading", "Altium sheet size and margins", "Altium border and reference zones", "Altium sheet graphics" and
"Sheet import report". Every template is authored in ``tests/_altium_sheet.py``."""

from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

import pytest
from _altium_sheet import CASES, Record, build, label, line, parameter, poly, rec, sheet, template
from hypothesis import given, settings
from hypothesis import strategies as st

import fenolite.backends.altium.read.sheet as sheet_module
from fenolite.backends.altium.read.sheet import (
    EVIDENCE,
    ISSUE_CODES,
    LINE_WIDTHS,
    SHEET_STYLES,
    SheetImport,
    SheetLossError,
    SheetSource,
    import_sheet,
)
from fenolite.core.errors import FenoliteError, FormatError
from fenolite.core.evidence import Level
from fenolite.core.ids import derived_id
from fenolite.model import canonical
from fenolite.model.presentation import PAPER_SIZES, SheetPoint, SheetShape, SheetText

UNIT = 254_000


def lossy(name: str, form: str = "ascii") -> SheetImport:
    return import_sheet(template(name, form=form), allow_lossy=True)  # type: ignore[arg-type]


def codes(result: SheetImport) -> list[str]:
    return [issue.code for issue in result.issues]


# --- Altium sheet template reading ----------------------------------------------------------------------


def test_reading_extension_does_not_matter() -> None:
    data = template("title_block", form="binary")
    first = import_sheet(data, file="t.SchDot")
    second = import_sheet(data, file="t.SchDoc")
    assert canonical.dumps(first.sheet) == canonical.dumps(second.sheet)
    assert first.source.form == second.source.form == "binary"
    assert canonical.dumps(import_sheet(data).sheet) == canonical.dumps(first.sheet)


def test_reading_binary_and_ascii_agree() -> None:
    binary = import_sheet(template("title_block", form="binary"))
    text = import_sheet(template("title_block", form="ascii"))
    assert binary.sheet.setup == text.sheet.setup and binary.sheet.items == text.sheet.items
    assert (binary.source.form, text.source.form) == ("binary", "ascii")


def test_reading_graphics_of_an_applied_template() -> None:
    result = import_sheet(template("applied"))
    kinds = [type(item) for item in result.sheet.items]
    assert kinds.count(SheetShape) == 2 and kinds.count(SheetText) == 1 and len(kinds) == 3
    assert result.imported == {13: 2, 4: 1}


def test_reading_child_of_another_record_belongs_to_its_owner() -> None:
    records = [sheet(SHEETSTYLE=0), rec(1, LIBREFERENCE="A"), line(10, 10, 20, 10, OWNERINDEX=1)]
    result = import_sheet(build(records, form="ascii"), allow_lossy=True)
    assert result.sheet.items == () and result.reported == ("record[1]",)
    assert codes(result) == ["altium.sheet.not-template-content"]


def test_reading_no_sheet_record() -> None:
    with pytest.raises(FormatError) as caught:
        import_sheet(template("no_sheet", form="ascii"), file="t.SchDot")
    assert caught.value.locator == "record[0]" and caught.value.file == "t.SchDot"


def test_reading_reader_error_passes_through() -> None:
    with pytest.raises(FormatError) as caught:
        import_sheet(b"hello")
    assert "compound file" in caught.value.message


def test_reading_name_id_and_parameters() -> None:
    result = import_sheet(template("mixed"), name="mine", allow_lossy=True)
    assert result.sheet.name == "mine" and result.sheet.id == derived_id("wks", "altium", "mine")
    assert result.parameters == ("Title",)
    assert import_sheet(template("a4")).sheet.name == "imported"
    assert all(not hasattr(item, "id") for item in result.sheet.items)


def test_reading_opens_no_file(monkeypatch: pytest.MonkeyPatch) -> None:
    data = template("image_linked")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the importer opened a file")

    monkeypatch.setattr(builtins, "open", refuse)
    monkeypatch.setattr("os.open", refuse)
    assert import_sheet(data, allow_lossy=True).sheet.items == ()


def test_reading_imports_only_allowed_packages() -> None:
    tree = ast.parse(Path(sheet_module.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    allowed = ("fenolite.core", "fenolite.model", "fenolite.backends.altium")
    for name in names - {"__future__"}:
        if name.startswith("fenolite"):
            assert name.startswith(allowed), name
        else:
            assert name.split(".")[0] in sys.stdlib_module_names, name
    assert not {"time", "datetime", "random", "os", "pathlib", "secrets", "uuid"} & names


def test_reading_evidence_is_inferred() -> None:
    assert EVIDENCE.level is Level.INFERRED
    assert "H-A-RD-SHT-SAME" in EVIDENCE.hypotheses and len(EVIDENCE.hypotheses) == 8


# --- Altium sheet size and margins ----------------------------------------------------------------------


def test_size_a4_style_centred_on_the_paper() -> None:
    result = import_sheet(template("a4", form="ascii"))
    assert result.source == SheetSource("ascii", 0, "A4", False, 292_100_000, 193_040_000)
    setup = result.sheet.setup
    assert setup.left_margin == setup.right_margin == 2_450_000
    assert setup.top_margin == setup.bottom_margin == 8_480_000
    assert import_sheet(template("no_style")).source.style == 0


def test_size_custom_portrait_sheet() -> None:
    result = import_sheet(template("custom_portrait"))
    source, setup = result.source, result.sheet.setup
    assert source.paper == "custom" and source.portrait and source.style is None
    assert (source.width, source.height) == (177_800_000, 254_000_000)
    assert (setup.left_margin, setup.right_margin, setup.top_margin, setup.bottom_margin) == (0, 0, 0, 0)


def test_size_custom_keys_ignored_without_the_flag() -> None:
    source = import_sheet(template("custom_ignored")).source
    assert (source.style, source.paper, source.width, source.height) == (1, "A3", 1550 * UNIT, 1110 * UNIT)


def test_size_unknown_style_refused() -> None:
    with pytest.raises(FormatError) as caught:
        import_sheet(template("style_18"))
    assert caught.value.locator == "record[0].SHEETSTYLE"
    with pytest.raises(FormatError):
        import_sheet(build([sheet(SHEETSTYLE=-1)], form="ascii"))


def test_size_style_table() -> None:
    assert len(SHEET_STYLES) == 18
    assert SHEET_STYLES[0] == (1150, 760, "A4") and SHEET_STYLES[12] == (1700, 1100, "Tabloid")
    assert SHEET_STYLES[17] == (4280, 3280, "custom")
    assert [paper for _, _, paper in SHEET_STYLES].count("custom") == 10


@pytest.mark.parametrize("style", range(18))
@pytest.mark.parametrize("portrait", [False, True])
def test_size_every_style_fits_its_paper(style: int, portrait: bool) -> None:
    keys: dict[str, object] = {"SHEETSTYLE": style}
    if portrait:
        keys["WORKSPACEORIENTATION"] = 1
    result = import_sheet(build([sheet(**keys)], form="ascii"))
    source, setup = result.source, result.sheet.setup
    units_x, units_y, paper = SHEET_STYLES[style]
    area = (units_y * UNIT, units_x * UNIT) if portrait else (units_x * UNIT, units_y * UNIT)
    assert (source.width, source.height) == area and source.paper == paper and source.portrait is portrait
    if paper == "custom":
        assert (setup.left_margin, setup.top_margin) == (0, 0)
    else:
        page = PAPER_SIZES[paper] if portrait else PAPER_SIZES[paper][::-1]
        assert source.width + setup.left_margin + setup.right_margin == page[0]
        assert source.height + setup.top_margin + setup.bottom_margin == page[1]
        assert setup.left_margin == setup.right_margin and setup.top_margin == setup.bottom_margin


def test_size_setup_defaults() -> None:
    setup = import_sheet(template("a4")).sheet.setup
    assert setup.text_size == (3_528_000, 3_528_000)
    assert (setup.line_width, setup.text_line_width) == (254_000, 127_000)
    bigger = import_sheet(build([sheet(SIZE2=20, SYSTEMFONT=2)], form="ascii")).sheet.setup
    assert bigger.text_size == (7_056_000, 7_056_000)


def test_size_fractional_coordinate_rounded_and_counted() -> None:
    result = import_sheet(template("fraction"))
    (item,) = result.sheet.items
    assert isinstance(item, SheetShape) and item.start.x % 1_000 == 0
    assert item.start == SheetPoint("lb", 2_571_000, 2_540_000)  # 10.12345 units = 2 571 356.3 nm
    (issue,) = result.issues
    assert (issue.code, issue.severity) == ("altium.sheet.rounded", "info") and issue.message.startswith("1 ")
    assert import_sheet(template("title_block")).issues == ()


# --- Altium border and reference zones ------------------------------------------------------------------


def test_border_custom_with_zones() -> None:
    result = import_sheet(template("border_zones"))
    items = result.sheet.items
    width = 254_000
    assert items[0] == SheetShape("rect", SheetPoint("lt", 0, 0), SheetPoint("rb", 0, 0), width=width)
    inset = 5_080_000
    assert items[1] == SheetShape(
        "rect", SheetPoint("lt", inset, inset), SheetPoint("rb", inset, inset), width=width
    )
    ticks, labels = items[2:10], items[10:]
    assert all(isinstance(t, SheetShape) and t.kind == "line" for t in ticks) and len(labels) == 12
    assert [t.text for t in labels if isinstance(t, SheetText)] == [*"1234", *"1234", *"AB", *"AB"]
    first_tick = ticks[0]
    assert isinstance(first_tick, SheetShape)
    assert first_tick.start == SheetPoint("lt", 63_500_000, 0) and first_tick.end.y == inset
    first = labels[0]
    assert isinstance(first, SheetText)
    assert first.pos == SheetPoint("lt", 31_750_000, 2_540_000) and first.size == (2_540_000, 2_540_000)
    assert (first.justify, first.vjustify) == ("center", "center")
    letter = labels[8]
    assert isinstance(letter, SheetText) and letter.pos == SheetPoint("lt", 2_540_000, 44_450_000)
    assert codes(result) == ["altium.sheet.builtin-drawn"] and result.issues[0].severity == "info"
    assert result.imported == {} and result.reported == ()


def test_border_of_a_standard_style_reported() -> None:
    result = lossy("border_standard")
    assert result.sheet.items == ()
    assert codes(result) == ["altium.sheet.builtin-not-drawn"] * 2
    assert "border" in result.issues[0].message and result.issues[0].where == "record[0].BORDERON"
    assert "title-block" in result.issues[1].message and result.issues[1].where == "record[0].TITLEBLOCKON"
    assert all(issue.severity == "warning" for issue in result.issues)


def test_border_without_margin_or_with_too_many_zones() -> None:
    custom: dict[str, object] = {"USECUSTOMSHEET": True, "CUSTOMX": 1000, "CUSTOMY": 700, "BORDERON": True}
    no_margin = import_sheet(build([sheet(**custom)], form="ascii"), allow_lossy=True)
    assert no_margin.sheet.items == () and codes(no_margin) == ["altium.sheet.builtin-not-drawn"]
    zones = dict(custom, CUSTOMMARGINWIDTH=20, REFERENCEZONESON=True, CUSTOMXZONES=4, CUSTOMYZONES=27)
    many = import_sheet(build([sheet(**zones)], form="ascii"), allow_lossy=True)
    assert len(many.sheet.items) == 2
    assert codes(many) == ["altium.sheet.builtin-drawn", "altium.sheet.builtin-not-drawn"]
    assert "zones" in many.issues[1].message and many.issues[1].where == "record[0].REFERENCEZONESON"
    plain = dict(custom, CUSTOMMARGINWIDTH=20)
    assert len(import_sheet(build([sheet(**plain)], form="ascii")).sheet.items) == 2


# --- Altium sheet graphics ------------------------------------------------------------------------------


def test_graphics_line_near_the_bottom_right_corner() -> None:
    (item,) = import_sheet(template("line_rb")).sheet.items
    assert item == SheetShape(
        "line", SheetPoint("rb", 63_500_000, 2_540_000), SheetPoint("rb", 2_540_000, 2_540_000), width=254_000
    )


def test_graphics_label_with_justification_and_rotation() -> None:
    (item,) = import_sheet(template("label_rotated")).sheet.items
    assert isinstance(item, SheetText)
    assert item.text == "Notes" and item.pos == SheetPoint("lt", 5_080_000, 15_240_000)
    assert item.size == (3_528_000, 3_528_000) and item.bold and not item.italic
    assert (item.justify, item.vjustify, item.rotation) == ("right", "top", 90_000_000)


def test_graphics_justification_table() -> None:
    records = [
        sheet(SHEETSTYLE=0),
        *(label(10, 10, "A", JUSTIFICATION=n) for n in range(9)),
        label(10, 10, "A"),
    ]
    items = import_sheet(build(records, form="ascii")).sheet.items
    found = [(i.vjustify, i.justify) for i in items if isinstance(i, SheetText)]
    assert found[:9] == [(v, h) for v in ("bottom", "center", "top") for h in ("left", "center", "right")]
    assert found[9] == ("bottom", "left")
    turned = [sheet(SHEETSTYLE=0), *(label(10, 10, "A", ORIENTATION=n) for n in range(4))]
    rotations = [i.rotation for i in import_sheet(build(turned, form="ascii")).sheet.items]  # type: ignore[union-attr]
    assert rotations == [0, 90_000_000, 180_000_000, 270_000_000]


def test_graphics_font_outside_the_table_uses_the_system_font() -> None:
    records = [sheet(SHEETSTYLE=0, SIZE2=20, ITALIC2=True, SYSTEMFONT=2), label(10, 10, "A", FONTID=9)]
    (item,) = import_sheet(build(records, form="ascii")).sheet.items
    assert isinstance(item, SheetText) and item.size == (7_056_000, 7_056_000) and item.italic


def test_graphics_rectangle_and_line_widths() -> None:
    assert dict(LINE_WIDTHS) == {0: 102_000, 1: 254_000, 2: 508_000, 3: 1_016_000}
    items = import_sheet(template("title_block")).sheet.items
    frame = items[0]
    assert isinstance(frame, SheetShape) and frame.kind == "rect" and frame.width == 508_000
    assert frame.start.corner == frame.end.corner == "rb"
    thin = items[5]
    assert isinstance(thin, SheetShape) and thin.width == 102_000
    page = items[-2]  # the frame's centre is the area's centre: the rule gives the right, top corner
    assert page == SheetShape(
        "rect",
        SheetPoint("rt", 289_560_000, 190_500_000),
        SheetPoint("rt", 2_540_000, 2_540_000),
        width=102_000,
    )


def test_graphics_polygon_closed_with_lines() -> None:
    result = lossy("polygon_solid")
    items = result.sheet.items
    assert len(items) == 3 and all(isinstance(i, SheetShape) and i.kind == "line" for i in items)
    assert {i.start.corner for i in items if isinstance(i, SheetShape)} == {"lb"}
    assert items[2].end == items[0].start  # type: ignore[union-attr]
    (issue,) = result.issues
    assert (
        issue.code == "altium.sheet.style-dropped" and issue.where == "record[1]" and "fill" in issue.message
    )
    assert result.imported == {7: 1}


def test_graphics_polyline_uses_one_corner() -> None:
    items = import_sheet(template("polyline")).sheet.items
    assert len(items) == 2 and {i.start.corner for i in items if isinstance(i, SheetShape)} == {"rt"}
    assert all(isinstance(i, SheetShape) and i.width == 1_016_000 for i in items)
    assert items[0].end == items[1].start  # type: ignore[union-attr]


def test_graphics_arc_reported_not_drawn() -> None:
    result = lossy("arc")
    assert len(result.sheet.items) == 2
    (issue,) = result.issues
    assert (issue.code, issue.where) == ("altium.sheet.not-representable", "record[3]")
    assert "12" in issue.message and "arc" in issue.message


@pytest.mark.parametrize("kind", [5, 8, 9, 10, 11, 12, 28, 209])
def test_graphics_other_graphic_kinds_not_representable(kind: int) -> None:
    result = import_sheet(build([sheet(), rec(kind, {"LOCATION.X": 10})], form="ascii"), allow_lossy=True)
    assert codes(result) == ["altium.sheet.not-representable"] and result.reported == ("record[1]",)


@pytest.mark.parametrize("kind", [1, 17, 18, 25, 27, 29, 34, 999])
def test_graphics_other_records_are_not_template_content(kind: int) -> None:
    result = import_sheet(build([sheet(), rec(kind, {"LOCATION.X": 10})], form="ascii"), allow_lossy=True)
    assert codes(result) == ["altium.sheet.not-template-content"] and result.sheet.items == ()


def test_graphics_outside_the_drawing_area() -> None:
    result = lossy("outside")
    assert result.sheet.items == () and codes(result) == ["altium.sheet.outside"]
    assert result.reported == ("record[1]",) and result.imported == {}


def test_graphics_styles_dropped() -> None:
    result = lossy("styles_dropped")
    assert len(result.sheet.items) == 4 and result.reported == ()
    found = [(issue.where, issue.message) for issue in result.issues]
    assert codes(result) == ["altium.sheet.style-dropped"] * 5
    for (where, message), (record, word) in zip(
        found,
        [(1, "line-width"), (2, "line-style"), (3, "fill"), (4, "underline"), (4, "mirror")],
        strict=True,
    ):
        assert where == f"record[{record}]" and word in message and "record kind" in message
    unknown_width = result.sheet.items[0]
    assert isinstance(unknown_width, SheetShape) and unknown_width.width == 254_000


def test_graphics_appearance_reported_once() -> None:
    result = import_sheet(template("appearance"))
    (issue,) = result.issues
    assert (issue.code, issue.severity) == ("altium.sheet.appearance", "info")
    assert "2 record(s)" in issue.message and "Times New Roman" in issue.message


# --- Sheet import report --------------------------------------------------------------------------------


def test_report_issue_codes_table() -> None:
    assert len(ISSUE_CODES) == 12
    infos = {code for code, severity in ISSUE_CODES.items() if severity == "info"}
    assert infos == {"altium.sheet.appearance", "altium.sheet.rounded", "altium.sheet.builtin-drawn"}
    assert set(ISSUE_CODES.values()) == {"warning", "info"}


def test_report_every_record_accounted_for() -> None:
    result = lossy("mixed")
    assert result.imported == {13: 2, 4: 1}
    assert result.reported == ("record[4]", "record[5]") and result.parameters == ("Title",)
    assert sum(result.imported.values()) + len(result.reported) == 5 == len(CASES["mixed"][0]) - 2


def test_report_loss_refused_by_default() -> None:
    with pytest.raises(SheetLossError) as caught:
        import_sheet(template("mixed"))
    error = caught.value
    assert isinstance(error, FenoliteError) and SheetLossError.cli_code == "FEN-7001"
    assert [(i.code, i.where) for i in error.issues] == [
        ("altium.sheet.not-representable", "record[4]"),
        ("altium.sheet.not-template-content", "record[5]"),
    ]
    assert "--allow-lossy" in error.hint
    assert lossy("mixed").issues == error.issues


def test_report_clean_template_needs_no_flag() -> None:
    result = import_sheet(template("title_block"))
    assert all(issue.severity == "info" for issue in result.issues)
    assert result.imported == {4: 19, 13: 5, 14: 2} and result.reported == ()
    info_only = import_sheet(template("fraction"))
    assert import_sheet(template("fraction"), allow_lossy=True) == info_only


def test_report_additional_stream_record() -> None:
    from _altium_sch_build import SHEET, schdoc

    data = schdoc([SHEET], additional=["|RECORD=215|LOCATION.X=10|LOCATION.Y=10"])
    result = import_sheet(data, allow_lossy=True)
    (issue,) = [i for i in result.issues if i.severity == "warning"]
    assert (issue.code, issue.where) == ("altium.sheet.not-template-content", "additional[0]")
    assert result.reported == ("additional[0]",)


def test_report_messages_name_the_record_kind() -> None:
    for name in ("mixed", "outside", "styles_dropped", "image_linked", "dynamic", "spaced"):
        for issue in lossy(name).issues:
            if issue.severity == "warning":
                assert issue.where.startswith("record[") and "record kind" in issue.message, issue


_RECORDS: st.SearchStrategy[Record] = st.one_of(
    st.builds(line, st.integers(0, 1300), st.integers(0, 800), st.integers(0, 1300), st.integers(0, 800)),
    st.builds(lambda x, y: label(x, y, "A"), st.integers(0, 1300), st.integers(0, 800)),
    st.builds(lambda n: poly(6, [(10 * i, 10) for i in range(n)]), st.integers(0, 4)),
    st.builds(lambda n: poly(7, [(10 * i, 10 + i) for i in range(n)]), st.integers(0, 4)),
    st.sampled_from([5, 8, 9, 10, 11, 12, 28, 209, 1, 27, 25, 39, 77]).map(lambda kind: rec(kind)),
    st.just(parameter("Title")),
    st.just(rec(30, {"LOCATION.X": 1, "CORNER.X": 5}, FILENAME="a.bmp")),
)


@settings(max_examples=60, deadline=None)
@given(st.lists(st.tuples(_RECORDS, st.integers(0, 40), st.booleans()), max_size=12))
def test_report_property_every_template_record_counted_once(
    drawn: list[tuple[Record, int, bool]],
) -> None:
    """Records with and without an owner: every template record that is not a template (39) or a parameter
    (41) is in ``imported`` or ``reported``, exactly once; owned records of other owners are in neither."""
    records: list[Record] = [sheet(SHEETSTYLE=0)]
    owners: list[int | None] = [None]
    for fields, pick, owned in drawn:
        owner = 1 + pick % (len(records) - 1) if owned and len(records) > 1 else None
        records.append(fields if owner is None else (*fields, ("OWNERINDEX", str(owner))))
        owners.append(owner)
    result = import_sheet(build(records, form="ascii"), allow_lossy=True)
    kinds = [int(dict(fields)["RECORD"]) for fields in records]
    template_records: set[int] = set()
    for index in range(1, len(records)):
        owner = owners[index]
        if owner is None or (owner in template_records and kinds[owner] == 39):
            template_records.add(index)
    counted = {i for i in template_records if kinds[i] not in (39, 41)}
    assert set(result.reported) <= {f"record[{i}]" for i in counted}
    assert len(set(result.reported)) == len(result.reported)
    assert sum(result.imported.values()) + len(result.reported) == len(counted)
    warned = {issue.where for issue in result.issues if issue.severity == "warning"}
    assert set(result.reported) <= warned
