# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The bill that ``kicad-cli sch export bom`` writes, read back (capability assembly-outputs, "BOM parts
from kicad-cli"; change c0064). Hermetic: the CSV is authored, with made-up parts."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.kicad.bom import BASE_FIELDS, BomRow, bom_fields, read_bom_csv, unsupported_fields
from fenolite.core.errors import FormatError

EXPORT = Path(__file__).resolve().parents[3] / "data" / "assembly" / "bom_export.csv"
FIELDS = (*BASE_FIELDS, "Bin")


def _text() -> str:
    return EXPORT.read_bytes().decode("utf-8")


def test_fields_to_ask_for() -> None:
    assert BASE_FIELDS == ("Reference", "Value", "Footprint", "Datasheet", "Description", "${DNP}")
    assert bom_fields(()) == BASE_FIELDS
    assert bom_fields(["Bin", "Alt", "Bin", "Value"]) == (*BASE_FIELDS, "Alt", "Bin")
    assert unsupported_fields(["a,b", "c", "a,b", "Z,"]) == ("Z,", "a,b")
    with pytest.raises(ValueError, match="comma"):
        bom_fields(["a,b"])


def test_rows_of_the_authored_export() -> None:
    rows = read_bom_csv(_text(), fields=FIELDS)
    assert [row.ref for row in rows] == ["R10", "D1", "R1"]  # file order; exports.bom sorts
    r10, d1, r1 = rows
    assert r10 == BomRow(
        "R10", "330", "Mini:Mini_R_0603", "", 'made-up resistor, 1 %, "thick" film', True, {}
    )
    assert (d1.dnp, d1.properties, d1.description) == (False, {}, "")
    assert (r1.value, r1.datasheet, r1.dnp, r1.properties) == ("10k", "none", False, {"Bin": "A"})


def test_unexpected_header() -> None:
    text = _text().replace('"Value"', '"Val"', 1)
    with pytest.raises(FormatError, match="'Val'") as caught:
        read_bom_csv(text, fields=FIELDS, file="bom.csv")
    assert caught.value.file == "bom.csv" and caught.value.locator == "line 1"
    assert "'Value'" in caught.value.message and "cell 2" in caught.value.message


@pytest.mark.parametrize(
    ("change", "message", "line"),
    [
        (lambda t: "", "no header", "line 1"),
        (lambda t: t.replace(',"Bin"\n', "\n", 1), "no cell", "line 1"),
        (lambda t: t.replace(',"Bin"\n', ',"Bin","More"\n', 1), "'More'", "line 1"),
        (lambda t: t + '"R2","1k"\n', "2 cells", "line 5"),
        (lambda t: t + '"","1k","","","","",""\n', "no reference", "line 5"),
    ],
)
def test_malformed_exports(change: object, message: str, line: str) -> None:
    with pytest.raises(FormatError, match=message) as caught:
        read_bom_csv(change(_text()), fields=FIELDS)  # type: ignore[operator]
    assert caught.value.locator == line


def test_blank_lines_and_line_ends() -> None:
    text = _text().replace("\n", "\r\n") + "\r\n"
    assert read_bom_csv(text, fields=FIELDS) == read_bom_csv(_text(), fields=FIELDS)
    assert read_bom_csv('"Reference","Value","Footprint","Datasheet","Description","${DNP}"\n',
                        fields=BASE_FIELDS) == ()  # fmt: skip


def test_fields_must_start_with_the_base() -> None:
    with pytest.raises(ValueError, match="start with"):
        read_bom_csv(_text(), fields=("Reference", "Bin"))
