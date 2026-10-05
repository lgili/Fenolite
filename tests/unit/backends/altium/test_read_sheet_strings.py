# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Special strings and images of the Altium sheet import (change c0046, capability sheet-templates):
"Altium special strings" and "Altium sheet images"."""

from __future__ import annotations

import base64

import pytest
from _altium_sheet import IMAGE_NAME, PNG, build, image, label, sheet, template

from fenolite.backends.altium.read.sheet import (
    ALTIUM_SHEET_TOKENS,
    DYNAMIC_STRINGS,
    SheetImport,
    import_sheet,
    neutral_text,
)
from fenolite.model.presentation import (
    SHEET_TOKENS,
    SheetBitmap,
    SheetPoint,
    SheetText,
    SheetToken,
    split_tokens,
)


def lossy(name: str, form: str = "binary") -> SheetImport:
    return import_sheet(template(name, form=form), allow_lossy=True)  # type: ignore[arg-type]


def texts(result: SheetImport) -> list[str]:
    return [item.text for item in result.sheet.items if isinstance(item, SheetText)]


# --- Altium special strings -----------------------------------------------------------------------------


def test_strings_token_table() -> None:
    assert dict(ALTIUM_SHEET_TOKENS) == {
        "Title": "title",
        "DocumentNumber": "doc_id",
        "Revision": "revision",
        "SheetNumber": "sheet",
        "SheetTotal": "sheets",
        "Date": "date",
        "Organization": "organization",
        "DrawnBy": "responsible",
        "ApprovedBy": "approver",
        "DocumentName": "filename",
    }
    assert set(ALTIUM_SHEET_TOKENS.values()) == SHEET_TOKENS - {"paper"}
    assert len(DYNAMIC_STRINGS) == 9 and "CurrentDate" in DYNAMIC_STRINGS
    assert not {name.casefold() for name in DYNAMIC_STRINGS} & {n.casefold() for n in ALTIUM_SHEET_TOKENS}


def test_strings_title_block_strings_mapped() -> None:
    result = import_sheet(template("strings"))
    assert texts(result) == ["{title}", "{doc_id}", "{sheet}", "{param:CheckedBy}", "Rev {{A}}"]
    assert result.strings == (
        ("=CheckedBy", "{param:CheckedBy}"),
        ("=SheetNumber", "{sheet}"),
        ("=Title", "{title}"),
        ("=documentnumber", "{doc_id}"),
    )
    assert result.issues == ()


def test_strings_dynamic_string_reported() -> None:
    result = lossy("dynamic")
    assert texts(result) == ["{param:CurrentDate}"]
    (issue,) = result.issues
    assert (issue.code, issue.where, issue.severity) == (
        "altium.sheet.dynamic-string",
        "record[1]",
        "warning",
    )
    assert result.strings == (("=CurrentDate", "{param:CurrentDate}"),) and result.imported == {4: 1}


def test_strings_name_with_a_space_kept_as_text() -> None:
    result = lossy("spaced")
    assert texts(result) == ["=Drawn By"]
    (issue,) = result.issues
    assert issue.code == "altium.sheet.unknown-string" and result.strings == ()


@pytest.mark.parametrize(
    ("source", "expected", "what"),
    [
        ("=TITLE", "{title}", "token"),
        ("=companyname", "{param:companyname}", "param"),
        ("=CompanyName", "{param:CompanyName}", "param"),
        ("=currenttime", "{param:currenttime}", "dynamic"),
        ("=Rule", "{param:Rule}", "dynamic"),
        ("=", "=", "unknown"),
        ("=A+B", "=A+B", "unknown"),
        ("=1st", "=1st", "unknown"),
        ("={x}", "={{x}}", "unknown"),
        ("a=b", "a=b", "literal"),
        ("{title}", "{{title}}", "literal"),
        ("", "", "literal"),
    ],
)
def test_strings_neutral_text(source: str, expected: str, what: str) -> None:
    assert neutral_text(source) == (expected, what)
    split_tokens(expected)


@pytest.mark.parametrize("name", sorted(DYNAMIC_STRINGS))
def test_strings_every_dynamic_name_is_a_parameter(name: str) -> None:
    assert neutral_text(f"={name}") == (f"{{param:{name}}}", "dynamic")


def test_strings_split_tokens_accepts_every_imported_text() -> None:
    result = import_sheet(template("title_block"))
    found: set[str] = set()
    for text in texts(result):
        for part in split_tokens(text):
            if isinstance(part, SheetToken):
                assert not part.param
                found.add(part.name)
    assert found == SHEET_TOKENS - {"paper"}
    assert len(result.strings) == 10 and result.strings[0] == ("=ApprovedBy", "{approver}")
    for name in ("strings", "dynamic", "spaced"):
        for text in texts(lossy(name)):
            split_tokens(text)


# --- Altium sheet images --------------------------------------------------------------------------------


def test_image_embedded_png_kept() -> None:
    result = lossy("image_png")
    (bitmap,) = result.sheet.items
    assert isinstance(bitmap, SheetBitmap)
    assert bitmap.pos == SheetPoint("lb", 50_800_000, 38_100_000) and bitmap.scale_ppm == 1_000_000
    assert base64.b64decode(bitmap.png) == PNG
    (issue,) = result.issues
    assert (issue.code, issue.severity, issue.where) == ("altium.sheet.image-size", "warning", "record[1]")
    assert "50800000 nm by 25400000 nm" in issue.message
    assert result.imported == {30: 1} and result.reported == ()


def test_image_linked_image_reported() -> None:
    result = lossy("image_linked")
    assert result.sheet.items == ()
    (issue,) = result.issues
    assert issue.code == "altium.sheet.image-not-kept" and issue.where == "record[1]"
    assert "linked" in issue.message and "logo.bmp" in issue.message
    assert "art" not in issue.message and "files" not in issue.message and "\\" not in issue.message
    assert result.reported == ("record[1]",)


@pytest.mark.parametrize(
    ("name", "form", "reason"),
    [
        ("image_missing", "binary", "missing"),
        ("image_png", "ascii", "missing"),
        ("image_not_png", "binary", "not-png"),
    ],
)
def test_image_refusal_reasons(name: str, form: str, reason: str) -> None:
    result = lossy(name, form)
    (issue,) = result.issues
    assert issue.code == "altium.sheet.image-not-kept" and f"({reason})" in issue.message
    assert IMAGE_NAME in issue.message and result.sheet.items == () and result.imported == {}


def test_image_base_name_of_a_posix_path() -> None:
    records = [sheet(SHEETSTYLE=0), image(10, 10, 20, 20, FILENAME="/srv/shared/art/mark.png")]
    (issue,) = import_sheet(build(records, form="ascii"), allow_lossy=True).issues
    assert "mark.png" in issue.message and "shared" not in issue.message


def test_image_outside_and_text_items_keep_order() -> None:
    records = [
        sheet(SHEETSTYLE=0),
        label(10, 10, "A"),
        image(100, 100, 300, 200, EMBEDIMAGE=True, FILENAME=IMAGE_NAME),
        image(1100, 100, 1300, 200, EMBEDIMAGE=True, FILENAME=IMAGE_NAME),
    ]
    result = import_sheet(build(records, files={IMAGE_NAME: PNG}), allow_lossy=True)
    assert [type(item) for item in result.sheet.items] == [SheetText, SheetBitmap]
    assert [issue.code for issue in result.issues] == ["altium.sheet.image-size", "altium.sheet.outside"]
    assert result.reported == ("record[3]",)
