# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The sheet-template writer (capability sheet-templates, "Altium sheet template writing"; change c0087).

The proof is own readback (``H-A-SCHDOT-READBACK``): ``import_sheet`` of the written bytes gives a drawing
sheet that is equal to the written one inside the written scope (``schdot.written_scope``).
No template file is committed (change c0046): the bytes are pinned by their SHA-256 in this file.
"""

from __future__ import annotations

import base64
import hashlib
from collections import Counter
from pathlib import Path

import pytest
from _altium_job import A4, example_sheet

from fenolite.backends.altium import schdot
from fenolite.backends.altium.layout import layout_sheet
from fenolite.backends.altium.read.sch import Label, Parameter, Polyline, read_schematic
from fenolite.backends.altium.read.sheet import ALTIUM_SHEET_TOKENS, ISSUE_CODES, SheetLossError, import_sheet
from fenolite.backends.altium.schdoc import sheet_record
from fenolite.backends.altium.schdot import (
    SPECIAL_STRINGS,
    SheetFrame,
    sheet_frame,
    to_steps,
    write_template,
    written_scope,
)
from fenolite.core.evidence import Level
from fenolite.core.ids import derived_id
from fenolite.model.presentation import (
    PAPER_SIZES,
    DrawingSheet,
    SheetBitmap,
    SheetItem,
    SheetPoint,
    SheetRepeat,
    SheetSetup,
    SheetShape,
    SheetText,
)
from fenolite.templates import layout as predicted_layout

MM = 1_000_000
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 16).decode("ascii")
SIZES = {
    "iso5457_generic": ("A4", "A3"),
    "letter_generic": ("Letter", "Tabloid"),
}


def page(size: str) -> tuple[int, int, str]:
    short, long = PAPER_SIZES[size]
    return long, short, size if size.startswith("A") else "User"


def authored(*items: SheetItem) -> DrawingSheet:
    """An authored sheet with 10 mm margins: a frame, a repeated tick with stepped labels, texts of every
    justification, a turned text, a bold and an italic one, tokens and a parameter."""
    setup = SheetSetup((2 * MM, 2 * MM), 150_000, 150_000, 10 * MM, 10 * MM, 10 * MM, 10 * MM)
    base: list[SheetItem] = [
        SheetShape("rect", SheetPoint("lt", 0, 0), SheetPoint("rb", 0, 0), width=700_000),
        SheetShape(
            "line",
            SheetPoint("lt", 50 * MM, 0),
            SheetPoint("lt", 50 * MM, 5 * MM),
            repeat=SheetRepeat(30, step_x=50 * MM),
        ),
        SheetText(
            "1",
            SheetPoint("lt", 25 * MM, 2_500_000),
            justify="center",
            repeat=SheetRepeat(30, step_x=50 * MM),
        ),
        SheetText(
            "A", SheetPoint("lb", 2 * MM, 25 * MM), repeat=SheetRepeat(3, step_y=50 * MM, label_step=2)
        ),
        SheetText("{title}", SheetPoint("rb", 60 * MM, 12 * MM), size=(5 * MM, 5 * MM), bold=True),
        SheetText("{param:PROJECT_CODE}", SheetPoint("rb", 60 * MM, 6 * MM), italic=True),
        SheetText("{paper}", SheetPoint("rb", 10 * MM, 6 * MM), justify="right", vjustify="top"),
        SheetText("Sheet {{1}}", SheetPoint("rt", 30 * MM, 8 * MM), justify="right", vjustify="bottom"),
        SheetText("up", SheetPoint("lb", 5 * MM, 80 * MM), rotation=90_000_000),
        SheetText("second page", SheetPoint("lt", 5 * MM, 5 * MM), scope="not_first"),
        SheetText("first page", SheetPoint("lt", 5 * MM, 9 * MM), scope="first_only"),
        SheetText("", SheetPoint("lt", 5 * MM, 12 * MM)),
        SheetShape("line", SheetPoint("lb", 0, 20 * MM), SheetPoint("rb", 0, 20 * MM), width=254_000),
    ]
    return DrawingSheet(
        id=derived_id("wks", "test", "authored"), name="authored", setup=setup, items=(*base, *items)
    )


def assert_readback(
    sheet: DrawingSheet, width: int, height: int, paper: str, form: schdot.TemplateForm
) -> None:
    written = write_template(sheet, width=width, height=height, paper=paper, form=form)
    assert not [i for i in written.issues if i.severity != "info"]
    imported = import_sheet(written.data)
    assert {i.code for i in imported.issues} <= {"altium.sheet.appearance", "altium.sheet.rounded"}
    assert (imported.source.form, imported.source.paper) == (form, "custom")
    assert (imported.source.width, imported.source.height) == (width, height)
    scope = written_scope(sheet, width=width, height=height, paper=paper)
    assert written_scope(imported.sheet, width=width, height=height, paper=paper) == scope
    lines, texts = scope
    assert (len(lines), len(texts)) == (written.result.lines, written.result.texts)
    assert imported.reported == ()


@pytest.mark.parametrize("form", schdot.FORMS)
def test_readback(form: schdot.TemplateForm) -> None:
    """Scenario "Shipped example" and ``H-A-SCHDOT-READBACK``: the two shipped examples on each of their
    sizes and the authored sheet, in both forms."""
    for name, sizes in SIZES.items():
        sheet = example_sheet(name)
        for size in sizes:
            assert_readback(sheet, *page(size), form)
    assert_readback(authored(), *page("A4"), form)
    assert_readback(authored(), *page("A3"), form)


def test_scope_follows_the_layout() -> None:
    """The scope holds what ``templates.layout`` predicts on the page: the same lines and text anchors."""
    for sheet, size in ((example_sheet(), "A4"), (example_sheet(), "A3"), (authored(), "A4")):
        width, height, paper = page(size)
        lines, texts = written_scope(sheet, width=width, height=height, paper=paper)
        predicted = predicted_layout(sheet, width=width, height=height)
        ends = sorted(tuple(sorted(((a.x1, a.y1), (a.x2, a.y2)))) for a in predicted.lines)
        assert sorted((line.start, line.end) for line in lines) == ends
        drawn = sorted((t.x, t.y) for t in predicted.texts if t.text)
        assert sorted((t.x, t.y) for t in texts) == drawn


def test_records_of_the_authored_sheet() -> None:
    """Records, fonts, strings and the sheet record of the authored sheet on A4."""
    width, height, paper = page("A4")
    written = write_template(authored(), width=width, height=height, paper=paper)
    document = read_schematic(written.data)
    sheet = document.sheet
    assert sheet is not None and sheet.props is not None
    props = sheet.props
    assert props.bool("USECUSTOMSHEET") and not props.has("SHEETSTYLE")
    assert not any(props.has(key) for key in ("BORDERON", "TITLEBLOCKON", "REFERENCEZONESON"))
    assert not props.has("WORKSPACEORIENTATION")
    assert (props.int("CUSTOMX"), props.int("CUSTOMX_FRAC")) == divmod(to_steps(width), 100_000)
    assert all(record.owner is None for record in document.records[1:])
    kinds = {type(record) for record in document.records[1:]}
    assert kinds == {Polyline, Label, Parameter}
    texts = {record.text for record in document.records if isinstance(record, Label)}
    assert {"=Title", "=PROJECT_CODE", "A4", "Sheet {1}", "up", "first page", "A", "C", "E"} <= texts
    assert "second page" not in texts and "" not in texts
    assert {str(n) for n in range(1, 6)} <= texts and "7" not in texts
    assert written.result.strings == ("=PROJECT_CODE", "=Title")
    assert written.result.parameters == ("PROJECT_CODE",)
    (parameter,) = [r for r in document.records if isinstance(r, Parameter)]
    assert parameter.name == "PROJECT_CODE" and parameter.props is not None
    assert not parameter.props.has("TEXT") and parameter.hidden
    fonts = {font.index: (font.size, font.bold, font.italic) for font in sheet.fonts}
    assert fonts[1] == (10, False, False)
    assert set(fonts.values()) == {(10, False, False), (6, False, False), (14, True, False), (6, False, True)}
    turned = next(r for r in document.records if isinstance(r, Label) and r.text == "up")
    assert turned.orientation == 1
    corner = next(r for r in document.records if isinstance(r, Label) and r.text == "A4")
    assert corner.justification == 8
    widths = sorted(
        {r.props.int("LINEWIDTH") for r in document.records if isinstance(r, Polyline) and r.props}
    )
    assert widths == [0, 1, 2]
    assert [i.code for i in written.issues] == ["altium.sheet.rounded"]
    assert written.issues[0].severity == "info"


def test_special_strings_table() -> None:
    """``SPECIAL_STRINGS`` is the inverse of the import's table; ``paper`` has no special string."""
    assert dict(SPECIAL_STRINGS) == {token: name for name, token in ALTIUM_SHEET_TOKENS.items()}
    assert len(SPECIAL_STRINGS) == len(ALTIUM_SHEET_TOKENS) == 10 and "paper" not in SPECIAL_STRINGS


def test_unknown_variable() -> None:
    """Scenario "Unknown variable"."""
    text = SheetText("{param:PROJECT_CODE}", SheetPoint("lt", 5 * MM, 5 * MM))
    setup = authored().setup
    sheet = DrawingSheet(id=derived_id("wks", "test", "v"), name="v", setup=setup, items=(text,))
    written = write_template(sheet, width=A4[0], height=A4[1], paper="A4", form="ascii")
    lines = written.data.decode("ascii").split("\r\n")
    assert any(line.startswith("|RECORD=4|") and line.endswith("|TEXT==PROJECT_CODE") for line in lines)
    assert any(line.startswith("|RECORD=41|") and line.endswith("|NAME=PROJECT_CODE") for line in lines)
    assert import_sheet(written.data).parameters == ("PROJECT_CODE",)


def loss(item: SheetItem) -> tuple[str, DrawingSheet]:
    sheet = authored(item)
    with pytest.raises(SheetLossError) as refused:
        write_template(sheet, width=A4[0], height=A4[1], paper="A4")
    assert refused.value.cli_code == "FEN-7001"
    (found,) = [i for i in refused.value.issues if i.severity == "warning"]
    assert found.severity == ISSUE_CODES[found.code] and found.where == f"items[{len(sheet.items) - 1}]"
    return found.code, sheet


def test_a_bitmap_is_a_loss() -> None:
    """Scenario "A bitmap is a loss": refused, and left out with ``allow_lossy``."""
    code, sheet = loss(SheetBitmap(SheetPoint("lt", 20 * MM, 20 * MM), PNG))
    assert code == "altium.sheet.image-not-kept"
    written = write_template(sheet, width=A4[0], height=A4[1], paper="A4", allow_lossy=True)
    plain = write_template(authored(), width=A4[0], height=A4[1], paper="A4")
    assert written.data == plain.data
    assert "altium.sheet.image-not-kept" in {i.code for i in written.issues}


@pytest.mark.parametrize(
    ("item", "code"),
    [
        (SheetText("Rev {revision}", SheetPoint("lt", 5 * MM, 30 * MM)), "altium.sheet.not-representable"),
        (SheetText("{title}{revision}", SheetPoint("lt", 5 * MM, 30 * MM)), "altium.sheet.not-representable"),
        (SheetText("Título", SheetPoint("lt", 5 * MM, 30 * MM)), "altium.sheet.not-representable"),
        (SheetText("a|b", SheetPoint("lt", 5 * MM, 30 * MM)), "altium.sheet.not-representable"),
        (SheetText("=Title", SheetPoint("lt", 5 * MM, 30 * MM)), "altium.sheet.not-representable"),
        (SheetText("{param:Title}", SheetPoint("lt", 5 * MM, 30 * MM)), "altium.sheet.not-representable"),
        (
            SheetText("x", SheetPoint("lt", 5 * MM, 30 * MM), rotation=45_000_000),
            "altium.sheet.style-dropped",
        ),
        (SheetText("x", SheetPoint("lt", 5 * MM, 30 * MM), max_len=10 * MM), "altium.sheet.style-dropped"),
        (SheetText("x", SheetPoint("lt", 5 * MM, 30 * MM), max_height=2 * MM), "altium.sheet.style-dropped"),
        (
            SheetShape("line", SheetPoint("lt", 5 * MM, 5 * MM), SheetPoint("lt", 400 * MM, 5 * MM)),
            "altium.sheet.outside",
        ),
    ],
)
def test_losses(item: SheetItem, code: str) -> None:
    """What the form cannot carry is refused with a code of the import's table, and left out or written
    without the style with ``allow_lossy``."""
    found, sheet = loss(item)
    assert found == code
    written = write_template(sheet, width=A4[0], height=A4[1], paper="A4", allow_lossy=True)
    kept = code == "altium.sheet.style-dropped"
    plain = write_template(authored(), width=A4[0], height=A4[1], paper="A4")
    assert written.result.texts == plain.result.texts + kept
    assert read_schematic(written.data).issues == ()


def test_frame_on_a_sheet_record() -> None:
    """A frame keeps the grids and the first font of a built sheet record, drops its style and border, and
    the template's own base record is that record without a size."""
    base = sheet_record(layout_sheet([]))
    frame = sheet_frame(authored(), width=A4[0], height=A4[1], paper="A4").frame
    record = frame.sheet_record(base)
    keys = [key for key, _value in record]
    assert not {"SHEETSTYLE", "BORDERON"} & set(keys) and len(set(keys)) == len(keys)
    assert dict(record)["FONTIDCOUNT"] == str(1 + len(frame.fonts)) == "4"
    assert keys.index("SIZE2") == keys.index("FONTNAME1") + 1
    stripped = [field for field in base if field[0] not in ("SHEETSTYLE", "BORDERON")]
    assert schdot.base_sheet_record() == stripped
    assert [f for f in record if f[0] in dict(stripped) and f[0] != "FONTIDCOUNT"] == [
        f for f in stripped if f[0] != "FONTIDCOUNT"
    ]
    assert keys[-5:] == ["USECUSTOMSHEET", "CUSTOMX", "CUSTOMX_FRAC", "CUSTOMY", "CUSTOMY_FRAC"]
    with pytest.raises(ValueError, match="font"):
        SheetFrame(1, 1, (), (), first_font=3).sheet_record(base)


def test_parameters_and_refusals() -> None:
    """Sheet parameters follow the graphics in the order given; a parameter token they name gets no second
    record; a page or a parameter that cannot be written is refused."""
    made = sheet_frame(
        authored(),
        width=A4[0],
        height=A4[1],
        paper="A4",
        parameters=(("Title", "T"), ("PROJECT_CODE", "F-1")),
    )
    assert made.parameters == ("Title", "PROJECT_CODE")
    tail = [dict(record) for record in made.frame.records[-2:]]
    assert [(r["RECORD"], r["NAME"], r["TEXT"]) for r in tail] == [
        ("41", "Title", "T"),
        ("41", "PROJECT_CODE", "F-1"),
    ]
    assert all("OWNERINDEX" not in r and r["ISHIDDEN"] == "T" for r in tail)
    for bad in ((("A", "x"), ("A", "y")), (("A", "=x"),), (("A", "café"),), (("a b|", "x"),)):
        with pytest.raises(ValueError):
            sheet_frame(authored(), width=A4[0], height=A4[1], paper="A4", parameters=bad)
    with pytest.raises(ValueError, match="not positive"):
        sheet_frame(authored(), width=0, height=A4[1], paper="A4")
    with pytest.raises(ValueError, match="form"):
        write_template(authored(), width=A4[0], height=A4[1], paper="A4", form="xml")  # type: ignore[arg-type]


def test_lengths() -> None:
    """A whole micrometre is written to the nearest step and read back exactly by a reader that rounds."""
    for nm in (0, 1_000, 254_000, 297 * MM, 123_457_000):
        steps = to_steps(nm)
        assert abs(steps * 127 - nm * 50) <= 63
        assert round(steps * 127 / 50 / 1_000) * 1_000 == nm
    assert schdot.length_fields("X1", 100_000) == (("X1", "1"),)
    assert schdot.length_fields("X1", 100_001) == (("X1", "1"), ("X1_FRAC", "1"))
    with pytest.raises(ValueError):
        schdot.length_fields("X1", -1)
    assert [schdot.points_of(h) for h in (1, 352_778, 2_500_000, 3_500_000)] == [1, 1, 7, 10]
    assert [schdot.width_code(w) for w in (0, 102_000, 178_000, 254_000, 700_000, 5 * MM)] == [
        0,
        0,
        0,
        1,
        2,
        3,
    ]


PINNED = (
    ("iso5457_generic", "binary", "0b161a6e93c98e4d7b5735c1657f3ea1f689f8ab99d95a5715b9489e4ca727d1"),
    ("iso5457_generic", "ascii", "07422325444d75ad25d2ead92526ae136655179b92013cb2d91d718bcf428b98"),
    ("authored", "binary", "ad86c76902302127b479afca2fecdad6ef0908fc6293bd15eb60307cb0c80dfa"),
)
"""Sheet, form and the SHA-256 of its template for an A4 landscape page. No template file is committed: a
tracked ``.SchDot`` is refused by ``tests/residue/test_template_residue.py`` (change c0046), so the bytes
are pinned here instead."""


def test_deterministic_and_pinned(tmp_path: Path) -> None:
    """Two writes give the same bytes, the bytes are the pinned ones, and a template written to a file
    reads back from it with the census of its records."""
    sheets = {"iso5457_generic": example_sheet(), "authored": authored()}
    width, height, paper = page("A4")
    for name, form, digest in PINNED:
        made = write_template(sheets[name], width=width, height=height, paper=paper, form=form)  # type: ignore[arg-type]
        again = write_template(sheets[name], width=width, height=height, paper=paper, form=form)  # type: ignore[arg-type]
        assert made.data == again.data
        assert hashlib.sha256(made.data).hexdigest() == digest, f"{name} ({form}) changed its bytes"
        path = tmp_path / f"{name}-{form}.SchDot"
        path.write_bytes(made.data)
        document = read_schematic(path.read_bytes())
        census = Counter(type(record).__name__ for record in document.records[1:])
        assert census["Label"] == made.result.texts and document.issues == ()
        assert census["Parameter"] == len(made.result.parameters)
        imported = import_sheet(path.read_bytes())
        assert written_scope(imported.sheet, width=width, height=height, paper=paper) == written_scope(
            sheets[name], width=width, height=height, paper=paper
        )
    iso = write_template(sheets["iso5457_generic"], width=width, height=height, paper=paper)
    records = read_schematic(iso.data).records[1:]
    assert Counter(type(record).__name__ for record in records) == {"Polyline": 27, "Label": 36}
    assert (iso.result.lines, iso.result.texts) == (36, 36)


def test_evidence() -> None:
    assert schdot.EVIDENCE.level is Level.INFERRED
    assert set(schdot.EVIDENCE.hypotheses) == {"H-A-SCHDOT-OPEN", "H-A-SCHDOT-READBACK", "H-A-SCHDOT-STRINGS"}
