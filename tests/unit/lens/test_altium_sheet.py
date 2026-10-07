# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing sheet of an Altium build (capability altium-build, "Drawing sheet in an Altium build";
change c0087): the frame on every schematic document, the sheet parameters and the page."""

from __future__ import annotations

import base64
import dataclasses
import io
import json
from pathlib import Path
from typing import Any

import pytest
from _altium import blink_tree, hier
from _altium_job import (
    A4,
    BOARD_LINE,
    SHEET_LINES,
    blink_output,
    example_sheet,
    grown_paper_issues,
    sheet_parameters,
)

from fenolite.backends.altium.read.sch import read_schematic
from fenolite.backends.altium.read.sheet import SheetLossError, import_sheet
from fenolite.backends.altium.schdot import written_scope
from fenolite.cli import main as cli_main
from fenolite.dsl import to_model
from fenolite.lens.altium import build_altium, sheet_page
from fenolite.lens.altium import sheet_parameters as lens_parameters
from fenolite.model.presentation import PAPER_SIZES, SheetBitmap, SheetFrameRef, SheetPoint, TitleBlock
from fenolite.templates import example_path

MM = 1_000_000
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 16).decode("ascii")
A4_AREA = (11_500 * 25_400, 7_600 * 25_400)
"""The drawing area of the layout's A4 sheet, in nm."""


def scope(sheet: object, width: int = A4[0], height: int = A4[1], paper: str = "A4") -> object:
    return written_scope(sheet, width=width, height=height, paper=paper)  # type: ignore[arg-type]


@pytest.mark.parametrize("form", ["binary", "ascii"])
def test_frame_on_the_sheet(form: str) -> None:
    """Scenario "Frame on the sheet": the frame reads back, and the sheet parameters hold the title block."""
    sheet = example_sheet()
    built = blink_output(framed=True, drawing_sheet=sheet, form=form)
    assert not [i for i in built.issues if i.severity == "error"]
    data = built.files["blink.SchDoc"]
    imported = import_sheet(data, allow_lossy=True)
    assert (imported.source.width, imported.source.height, imported.source.paper) == (*A4, "custom")
    assert scope(imported.sheet) == scope(sheet)
    assert {i.code for i in imported.issues if i.severity == "warning"} == {
        "altium.sheet.not-template-content"
    }
    assert sheet_parameters(data) == {
        "Title": "Blink",
        "Revision": "B",
        "SheetNumber": "1",
        "SheetTotal": "1",
        "PROJECT_CODE": "F-1",
    }
    assert built.summary["drawing_sheet"] == {
        "items": len(sheet.items),
        "pages": [{"file": "blink.SchDoc", "paper": "A4", "width": A4[0], "height": A4[1]}],
    }
    wanted = {"H-A-SCHDOT-OPEN", "H-A-SCHDOT-READBACK", "H-A-SCHDOT-STRINGS"}
    assert wanted <= set(built.evidence.hypotheses)
    assert {i.code for i in built.issues if i.code.startswith("altium.sheet")} == {"altium.sheet.rounded"}


def test_no_drawing_sheet_keeps_the_bytes() -> None:
    """Scenario "No drawing sheet": the sheet and the title block of the script change no byte without a
    drawing sheet, and with one every other file keeps its bytes and every other record its place."""
    plain = blink_output()
    titled = blink_output(framed=True)
    assert titled.files["blink.SchDoc"] == plain.files["blink.SchDoc"]
    assert plain.summary["drawing_sheet"] is None
    assert not {"H-A-SCHDOT-OPEN"} & set(plain.evidence.hypotheses)
    framed = blink_output(framed=True, drawing_sheet=example_sheet())
    for name in ("blink.PcbDoc", "blink.PcbLib", "blink.PrjPcb", "blink.SchLib"):
        assert framed.files[name] == plain.files[name], name
    before = blink_output(form="ascii").files["blink.SchDoc"].split(b"\r\n")
    after = blink_output(framed=True, drawing_sheet=example_sheet(), form="ascii").files["blink.SchDoc"]
    lines = after.split(b"\r\n")
    assert len(lines) > len(before) and lines[2 : len(before) - 1] == before[2:-1]
    assert not [line for line in lines[len(before) - 1 : -1] if b"|OWNERINDEX=" in line]
    sheet = read_schematic(after).records[0].props
    assert sheet is not None and sheet.bool("USECUSTOMSHEET") and not sheet.has("BORDERON")
    assert not sheet.has("SHEETSTYLE") and sheet.int("SNAPGRIDSIZE") == 10


def fonts_and_ids(data: bytes) -> tuple[list[tuple[str, int, bool, bool]], set[int]]:
    """The font table of a schematic document and every font number its records name."""
    document = read_schematic(data)
    sheet = document.sheet
    assert sheet is not None and sheet.system_font == 1
    named = {
        value
        for record in document.all_records()
        for key in ("font_id", "text_font_id")
        if (value := getattr(record, key, None)) is not None
    }
    return [(font.name, font.size, font.bold, font.italic) for font in sheet.fonts], named


def test_distinct_fonts_without_a_drawing_sheet() -> None:
    """Scenario "One sheet with labels in the default font" (capability altium-schematic-writer, "Distinct
    fonts in the font table"; change c0146)."""
    for form in ("binary", "ascii"):
        fonts, named = fonts_and_ids(blink_output(form=form).files["blink.SchDoc"])
        assert fonts == [("Times New Roman", 10, False, False)] and named == {1}


def test_distinct_fonts_in_both_forms() -> None:
    """Scenario "Binary and ASCII": with the shipped sheet, whose texts are of 10, 5 and 7 points, both
    forms hold the same table of three distinct fonts, the system font first, and name only its entries.
    Before change c0146 the table held 10 points twice."""
    tables = []
    for form in ("binary", "ascii"):
        built = blink_output(framed=True, drawing_sheet=example_sheet(), form=form)
        fonts, named = fonts_and_ids(built.files["blink.SchDoc"])
        assert len(set(fonts)) == len(fonts) and named == {1, 2, 3}
        tables.append(fonts)
    assert (
        tables[0]
        == tables[1]
        == [
            ("Times New Roman", 10, False, False),
            ("Times New Roman", 5, False, False),
            ("Times New Roman", 7, False, False),
        ]
    )


def test_page() -> None:
    """The page is the paper of ``sheet()`` when the layout fits it, else the next ISO paper that holds it,
    else the layout's own area."""
    a4, a3 = PAPER_SIZES["A4"], PAPER_SIZES["A3"]
    assert sheet_page(None, A4_AREA) == ("A4", a4[1], a4[0], False)
    assert sheet_page(SheetFrameRef("A3"), A4_AREA) == ("A3", a3[1], a3[0], False)
    assert sheet_page(SheetFrameRef("A5"), A4_AREA) == ("A4", a4[1], a4[0], True)
    assert sheet_page(SheetFrameRef("A4", portrait=True), A4_AREA) == ("A3", a3[0], a3[1], True)
    letter = PAPER_SIZES["Letter"]
    assert sheet_page(SheetFrameRef("Letter"), (200 * MM, 150 * MM)) == ("User", letter[1], letter[0], False)
    custom = SheetFrameRef("custom", width=300 * MM, height=200 * MM)
    assert sheet_page(custom, A4_AREA) == ("User", 300 * MM, 200 * MM, False)
    huge = (2_000 * MM, 1_500 * MM)
    assert sheet_page(SheetFrameRef("A4"), huge) == ("User", *huge, True)


def test_grown_paper() -> None:
    """A paper the layout does not fit gives ``altium.sheet-paper`` and the next paper that holds it."""
    (found,) = [i for i in grown_paper_issues() if i.code == "altium.sheet-paper"]
    assert found.severity == "warning" and found.where == "blink.SchDoc" and "A5" in found.message
    built = blink_output(framed=True, paper="A5", drawing_sheet=example_sheet())
    assert built.summary["drawing_sheet"]["pages"][0]["paper"] == "A4"  # type: ignore[index]
    imported = import_sheet(built.files["blink.SchDoc"], allow_lossy=True)
    assert (imported.source.width, imported.source.height) == A4


def test_a_loss_needs_allow_lossy() -> None:
    """A part the form cannot carry refuses the build; with ``allow_lossy`` it is reported and left out."""
    sheet = example_sheet()
    lossy = dataclasses.replace(
        sheet, items=(*sheet.items, SheetBitmap(SheetPoint("lt", 20 * MM, 20 * MM), PNG))
    )
    with pytest.raises(SheetLossError) as refused:
        blink_output(framed=True, drawing_sheet=lossy)
    assert "altium.sheet.image-not-kept" in {i.code for i in refused.value.issues}
    built = blink_output(framed=True, drawing_sheet=lossy, allow_lossy=True)
    (found,) = [i for i in built.issues if i.code == "altium.sheet.image-not-kept"]
    assert found.where == f"drawing_sheet.items[{len(sheet.items)}]"
    assert built.files["blink.SchDoc"] == blink_output(framed=True, drawing_sheet=sheet).files["blink.SchDoc"]


def test_sheet_parameters() -> None:
    """The fields that are not empty, the sheet number and count, then the variables in code-point order."""
    issues: list[Any] = []
    block = TitleBlock(
        title="T", date="2026-10-06", organization="Org", doc_id="D-1", responsible="R", approver="A",
        params={"b": "2", "a": "1", "empty": ""},
    )  # fmt: skip
    assert lens_parameters(block, 2, 3, issues) == [
        ("Title", "T"),
        ("Date", "2026-10-06"),
        ("Organization", "Org"),
        ("DocumentNumber", "D-1"),
        ("DrawnBy", "R"),
        ("ApprovedBy", "A"),
        ("SheetNumber", "2"),
        ("SheetTotal", "3"),
        ("a", "1"),
        ("b", "2"),
    ]
    assert issues == []
    assert lens_parameters(None, 1, 1, issues) == [("SheetNumber", "1"), ("SheetTotal", "1")]
    lens_parameters(TitleBlock(title="Café", params={"title": "x", "SHEETNUMBER": "9"}), 1, 1, issues)
    assert [i.code for i in issues] == ["altium.text-unwritable"] * 3
    assert all(i.severity == "error" for i in issues)


def test_unwritable_title_gives_no_file() -> None:
    """A title a record cannot hold is an error of the build: no file."""
    design_text = SHEET_LINES.replace('title="Blink"', 'title="Café"')
    from _altium import blink, blink_resolver

    from fenolite.dsl import placements

    design = blink(BOARD_LINE, design_text)
    built = build_altium(
        to_model(design),
        name=design.name,
        placed=tuple(placements(design)),
        placements=placements(design),
        resolver=blink_resolver(Path(".")),
        drawing_sheet=example_sheet(),
    )
    assert built.files == {} and "altium.text-unwritable" in {i.code for i in built.issues}


def test_every_module_sheet() -> None:
    """With module sheets every schematic document gets the frame, numbered among the sheets."""
    design = hier()
    built = build_altium(to_model(design), name=design.name, sheets="modules", drawing_sheet=example_sheet())
    assert not [i for i in built.issues if i.severity == "error"]
    files = [name for name in built.files if name.endswith(".SchDoc")]
    pages = built.summary["drawing_sheet"]["pages"]  # type: ignore[index]
    assert [page["file"] for page in pages] == list(built.summary["sheets"])  # type: ignore[union-attr]
    assert sorted(files) == sorted(page["file"] for page in pages) and len(files) == 3
    for number, page in enumerate(pages, start=1):
        data = built.files[page["file"]]
        parameters = sheet_parameters(data)
        assert (parameters["SheetNumber"], parameters["SheetTotal"]) == (str(number), "3")
        imported = import_sheet(data, allow_lossy=True)
        assert (imported.source.width, imported.source.height) == (page["width"], page["height"])
        reference = scope(example_sheet(), page["width"], page["height"], page["paper"])
        assert scope(imported.sheet, page["width"], page["height"], page["paper"]) == reference
    plain = build_altium(to_model(design), name=design.name, sheets="modules")
    assert {n: d for n, d in built.files.items() if n.endswith((".Harness", ".SchLib", ".PrjPcb"))} == {
        n: d for n, d in plain.files.items() if n.endswith((".Harness", ".SchLib", ".PrjPcb"))
    }


# --- the build command ----------------------------------------------------------------------------------


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def test_build_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``build --target altium`` of a script that names a ``.sheet.toml``: the frame is on the schematic,
    ``result.drawing_sheet`` says where, and a loss needs ``--allow-lossy``."""
    config = tmp_path / "kicad-config"
    config.mkdir()
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(config))
    for name in ("KICAD10_SYMBOL_DIR", "KICAD9_SYMBOL_DIR", "KICAD10_FOOTPRINT_DIR", "KICAD9_FOOTPRINT_DIR"):
        monkeypatch.delenv(name, raising=False)
    folder = blink_tree(tmp_path / "tree")
    script = folder / "design.py"
    source = script.read_text(encoding="utf-8")
    assert BOARD_LINE in source
    script.write_text(source.replace(BOARD_LINE, SHEET_LINES), encoding="utf-8", newline="\n")
    frames = folder / "frames"
    frames.mkdir()
    spec = example_path("iso5457_generic").read_text(encoding="utf-8")
    (frames / "generic.sheet.toml").write_text(spec, encoding="utf-8", newline="\n")
    out = tmp_path / "out"
    code, env, err = run(monkeypatch, str(script), "--out", str(out), "--target", "altium", "--confirm")
    assert code == 0, err
    sheet = env["result"]["drawing_sheet"]
    assert sheet["source"] == "frames/generic.sheet.toml" and sheet["items"] == len(example_sheet().items)
    assert sheet["pages"] == [
        {"file": str(out / "blink.SchDoc"), "paper": "A4", "width": A4[0], "height": A4[1]}
    ]
    data = (out / "blink.SchDoc").read_bytes()
    assert scope(import_sheet(data, allow_lossy=True).sheet) == scope(example_sheet())
    assert sheet_parameters(data)["Title"] == "Blink"
    assert {"H-A-SCHDOT-OPEN", "H-A-SCHDOT-READBACK", "H-A-SCHDOT-STRINGS"} <= set(
        env["evidence"]["hypotheses"]
    )

    # a text that mixes a token with other text is a loss
    lossy = spec.replace('label = "Title"\ntoken = "title"', 'label = "{title} of {sheets}"\ntoken = "title"')
    assert lossy != spec
    (frames / "generic.sheet.toml").write_text(lossy, encoding="utf-8", newline="\n")
    again = tmp_path / "again"
    code, _env, err = run(monkeypatch, str(script), "--out", str(again), "--target", "altium", "--confirm")
    assert code == 7 and "FEN-7001" in err and not again.exists()
    args = [str(script), "--out", str(again), "--target", "altium", "--confirm", "--allow-lossy"]
    code, env, err = run(monkeypatch, *args)
    assert code == 0, err
    assert "altium.sheet.not-representable" in {i["code"] for i in env["issues"]}
