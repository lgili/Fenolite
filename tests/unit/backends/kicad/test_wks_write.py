# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawing-sheet writer, refusals and the closed issue table (capability kicad-file-backend, "Drawing
sheet files are written" and "Drawing sheet issue codes"; change c0012)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.sexpr import AtomKind, parse, walk
from fenolite.backends.kicad.versions import FileKind, FutureFormatError, LossyWriteError, check_emittable
from fenolite.backends.kicad.wks import (
    ISSUE_CODES,
    VALUE_ATOMS,
    read_drawing_sheet,
    write_drawing_sheet,
)
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.presentation import (
    DrawingSheet,
    SheetBitmap,
    SheetPoint,
    SheetRepeat,
    SheetSetup,
    SheetShape,
    SheetText,
)

MM = 1_000_000
SHEETS = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "sheets"
SETUP = SheetSetup((1_500_000, 1_500_000), 150_000, 150_000, 20 * MM, 10 * MM, 10 * MM, 10 * MM)
PNG = __import__("base64").b64encode((SHEETS / "logo_1x1.png").read_bytes()).decode("ascii")
SEEN: list[Issue] = []


def built(*items: object) -> DrawingSheet:
    return DrawingSheet(id=derived_id("wks", "template", "t"), name="t", setup=SETUP, items=tuple(items))  # type: ignore[arg-type]


def every_kind() -> DrawingSheet:
    return built(
        SheetShape("rect", SheetPoint("lt"), SheetPoint(), width=700_000, name="frame"),
        SheetShape("line", SheetPoint("lt", 50 * MM), SheetPoint("lt", 50 * MM, 5 * MM),
                   repeat=SheetRepeat(8, 50 * MM, 0), scope="first_only", comment="ticks"),
        SheetShape("line", SheetPoint("lb", 0, 50 * MM), SheetPoint("rt", 5 * MM, 50 * MM),
                   scope="not_first"),
        SheetText("A", SheetPoint("rt", 2_500_000, 25 * MM), size=(3_500_000, 3_500_000), bold=True,
                  italic=True, justify="center", repeat=SheetRepeat(8, 0, 50 * MM, 2)),
        SheetText("{title} / {doc_id} / {param:LOT} / {{x}}", SheetPoint("rb", 90 * MM, 20 * MM),
                  justify="right", vjustify="top", rotation=90_000_000, max_len=80 * MM, max_height=5 * MM),
        SheetText("{revision}", SheetPoint("lb", 30 * MM, 5 * MM), vjustify="bottom"),
        SheetBitmap(SheetPoint("lt", 5 * MM, 5 * MM), PNG, scale_ppm=500_000, name="logo"),
    )  # fmt: skip


def write(sheet: DrawingSheet, **kwargs: object) -> str:
    result = write_drawing_sheet(sheet, **kwargs)  # type: ignore[arg-type]
    SEEN.extend(result.issues)
    return result.text


def refused(sheet: DrawingSheet, **kwargs: object) -> LossyWriteError:
    with pytest.raises(LossyWriteError) as info:
        write_drawing_sheet(sheet, **kwargs)  # type: ignore[arg-type]
    SEEN.extend(info.value.issues)
    return info.value


def test_header_and_target_independence() -> None:
    nine, ten = write(every_kind(), target=9), write(every_kind(), target=10)
    assert nine == ten
    assert nine.startswith('(kicad_wks\n\t(version 20231118)\n\t(generator "fenolite")\n')
    assert "generator_version" not in nine
    for target in (9, 10):
        assert check_emittable(parse(nine), FileKind.WORKSHEET, target) == ()


def test_modelled_items_use_listed_values_only() -> None:
    root = parse(write(every_kind()))
    for _, node in walk(root):
        symbols = [a.text for a in node.atoms() if a.kind == AtomKind.SYMBOL]
        if node.name in ("start", "end", "pos"):
            assert set(symbols) <= VALUE_ATOMS["corner"]
        elif node.name in ("option", "justify", "font"):
            assert set(symbols) <= VALUE_ATOMS[node.name]


def test_built_sheet_survives_a_round_trip() -> None:
    sheet = every_kind()
    back = read_drawing_sheet(write(sheet))
    assert (back.setup, back.items) == (sheet.setup, sheet.items)


def test_kicad_forms_written() -> None:
    text = write(every_kind())
    assert '(tbtext "${TITLE} / ${COMMENT1} / ${LOT} / {x}"' in text
    assert "(rotate 90)" in text and "(scale 0.5)" in text and "(linewidth 0.7)" in text
    assert "(option page1only)" in text and "(option notonpage1)" in text
    assert "rbcorner" not in text  # the default corner is written without its atom
    assert "(justify right top)" in text and "(justify bottom)" in text


def test_unknown_head_refused_then_dropped() -> None:
    sheet = read_drawing_sheet((SHEETS / "probe_broken.kicad_wks").read_text(encoding="utf-8"))
    error = refused(sheet)
    assert error.droppable is True and "--allow-lossy" in error.hint
    assert [i.code for i in error.issues] == ["kicad.wks.uninventoried"]
    result = write_drawing_sheet(sheet, allow_lossy=True)
    SEEN.extend(result.issues)
    assert "frobnicate" not in result.text
    assert [i.code for i in result.issues] == ["kicad.wks.dropped-item"]


def test_unknown_child_of_a_modelled_item_dropped() -> None:
    text = (
        (SHEETS / "all_items.kicad_wks")
        .read_text(encoding="utf-8")
        .replace('(name "frame")', '(name "frame")\n\t\t(frobnicate 1)')
    )
    sheet = read_drawing_sheet(text)
    assert len(sheet.items) == 7
    result = write_drawing_sheet(sheet, allow_lossy=True)
    SEEN.extend(result.issues)
    assert "frobnicate" not in result.text and '(name "frame")' in result.text
    assert len(read_drawing_sheet(result.text).items) == 7


def test_unknown_value_atom_refused() -> None:
    text = (SHEETS / "probe_value_unknown.kicad_wks").read_text(encoding="utf-8")
    error = refused(read_drawing_sheet(text))
    assert "kicad.wks.unknown-value" in [i.code for i in error.issues]
    option = text.replace("bogcorner", "ltcorner").replace('(name "")', '(name "")\n\t\t(option bogus)')
    assert [i.code for i in refused(read_drawing_sheet(option)).issues] == ["kicad.wks.unknown-value"]


def test_sub_micrometre_length_refused() -> None:
    sheet = built(SheetShape("line", SheetPoint("lt"), SheetPoint("lt", 500, 0)))
    error = refused(sheet, allow_lossy=True)
    assert error.droppable is False
    assert [i.code for i in error.issues] == ["kicad.wks.below-resolution"]


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("{param:TITLE}", "kicad.wks.param-reserved"),
        ("{param:KIPRJMOD}", "kicad.wks.param-reserved"),
        ("${{x}}", "kicad.wks.literal-variable"),
        ("Title: %T", "kicad.wks.literal-variable"),
    ],
)
def test_reserved_parameter_and_literal_variables_refused(text: str, code: str) -> None:
    error = refused(built(SheetText(text, SheetPoint("lt", MM, MM))), allow_lossy=True)
    assert error.droppable is False and [i.code for i in error.issues] == [code]


def test_percent_without_letter_allowed() -> None:
    assert "50 % off" in write(built(SheetText("50 % off", SheetPoint())))


def test_label_step_written_only_when_not_1() -> None:
    one = SheetText("A", SheetPoint("lt"), repeat=SheetRepeat(count=3, step_y=5 * MM))
    zero = SheetText("A", SheetPoint("lt", MM), repeat=SheetRepeat(count=3, step_y=5 * MM, label_step=0))
    text = write(built(one, zero))
    tbtexts = [n for n in parse(text).nodes() if n.name == "tbtext"]
    assert tbtexts[0].find("incrlabel") is None
    assert tbtexts[1].find("incrlabel") is not None and "(incrlabel 0)" in text
    assert read_drawing_sheet(text).items == (one, zero)


def test_future_worksheet_not_rewritten() -> None:
    text = (SHEETS / "probe_shape.kicad_wks").read_text(encoding="utf-8").replace("20231118", "29991231")
    issues: list[Issue] = []
    sheet = read_drawing_sheet(text, issues=issues)
    assert "kicad.version.future" in [i.code for i in issues]
    with pytest.raises(FutureFormatError) as info:
        write_drawing_sheet(sheet)
    assert info.value.cli_code == "FEN-3002"


def test_legacy_root_rewritten_as_kicad_wks() -> None:
    sheet = read_drawing_sheet(SHEETS / "probe_percent_legacy.kicad_wks")
    text = write(sheet)
    assert text.startswith("(kicad_wks\n\t(version 20231118)\n")
    assert "Title: %T" in text  # opaque items are re-emitted verbatim


def test_edited_read_item_keeps_its_unmodelled_children() -> None:
    source = (
        (SHEETS / "all_items.kicad_wks")
        .read_text(encoding="utf-8")
        .replace('(name "frame")', '(name "frame")\n\t\t(face "x")')
    )
    sheet = read_drawing_sheet(source)
    frame = sheet.items[0]
    assert isinstance(frame, SheetShape)
    moved = dataclasses.replace(frame, end=SheetPoint("rb", MM, MM))
    sheet = dataclasses.replace(sheet, items=(moved, *sheet.items[1:]))
    text = write(sheet, allow_lossy=True)
    rect = next(n for n in parse(text).nodes() if n.name == "rect")
    assert rect.find("end") is not None and "(end 1 1)" in text
    assert read_drawing_sheet(text).items[0] == moved


def test_write_sheet_and_capability_report() -> None:
    backend = KicadBackend()
    assert backend.write_sheet(every_kind()) == write_drawing_sheet(every_kind(), target=10)
    report = backend.capabilities()
    assert "kicad_wks" in report.write_kinds and "kicad_wks" not in report.read_kinds


def test_codes() -> None:
    """Every code the drawing-sheet unit tests produced is in the closed table (run last)."""
    issues: list[Issue] = list(SEEN)
    for path in sorted(SHEETS.glob("*.kicad_wks")):
        read_drawing_sheet(path, issues=issues)
    assert issues
    for issue in issues:
        assert issue.code in ISSUE_CODES or issue.code.startswith("kicad.version."), issue.code
        if issue.code in ISSUE_CODES:
            assert issue.severity == ISSUE_CODES[issue.code]


def test_example_header_and_target_independence() -> None:
    from fenolite.templates import build_sheet, example_path, load_spec

    sheet = build_sheet(load_spec(example_path("iso5457_generic")))
    nine, ten = write_drawing_sheet(sheet, target=9).text, write_drawing_sheet(sheet, target=10).text
    assert nine == ten
    assert nine.startswith('(kicad_wks\n\t(version 20231118)\n\t(generator "fenolite")\n')
    for target in (9, 10):
        assert check_emittable(parse(nine), FileKind.WORKSHEET, target) == ()
