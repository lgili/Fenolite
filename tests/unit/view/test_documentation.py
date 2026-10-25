# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Documentation views (capability documentation-view, change c0190): output jobs and BOM documents.

The public output jobs are read from the corpus cache (scenario "Public output jobs"); the other files are
authored here with values of these tests, in the record forms of ``docs/formats/altium/output-job.md`` and
``bom-document.md``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _corpus import manifest_items, require

from fenolite.backends.altium.read.bomdoc import read_bomdoc
from fenolite.backends.altium.read.outjob import read_outjob
from fenolite.view.bom import bom_scene, with_parts
from fenolite.view.outjob import outjob_scene

OUTJOBS = [item for item in manifest_items("altium-text") if item.id.startswith("altium-third-party-outjob-")]

JOB = """[OutputJobFile]
Version=1.0

[OutputGroup1]
Name=Docs
Description=
TargetOutputMedium=PDF
VariantName=[No Variations]
OutputMedium1=PDF
OutputMedium1_Type=Publish
OutputMedium2=Data
OutputMedium2_Type=GeneratedFiles
OutputType1=PCBDrawing
OutputName1=Assembly Drawing
OutputCategory1=Documentation
OutputDocumentPath1=board_Assembly.PCBDwf
OutputVariantName1=
OutputEnabled1=1
OutputEnabled1_OutputMedium1=1
OutputType2=BOM_PartType
OutputName2=Bill of Materials
OutputCategory2=Report
OutputDocumentPath2=[ActiveBOM Document]
OutputVariantName2=
OutputEnabled2=1
OutputEnabled2_OutputMedium2=1

[PublishSettings]
OutputBasePath1=Outputs\\
OutputPathMedia1=[Media Name]
OutputPathOutputer1=
OutputFileName1=board.PDF
OutputBasePath2=Outputs\\
OutputPathMedia2=
OutputPathOutputer2=[Output Type]
OutputFileName2=

[GeneratedFilesSettings]
RelativeOutputPath2=C:\\elsewhere\\Outputs\\
"""

BOM = "\n".join(
    [
        "|RECORD=BOM|VERSION=2|KIND=ALTIUM_DESIGNER_LIVEBOM|CURRENCY=USD|PRODUCTIONQUANTITY=1",
        "|RECORD=SortOrderOptions|SORTORDER=Supplier 1=Up!Comment=Up",
        "|RECORD=VisibleOrderOptions2|BASEVIEW=Line #=-1!Quantity=50!Description=200!Manufacturer=90"
        "!Manufacturer Part Number=120!Supplier 1=80!Price@Default=60!Tolerance=40",
        "|RECORD=ColumnsAliases|COLUMNSALIASES=Comment=Value!Supplier 1=Supplier",
        "|RECORD=CheckGroupCompParamsOptions|CHECKGROUPCOMPPARAMS=Comment=1,Description=0,Footprint=1",
        "|RECORD=LineNumberingOptions|STARTVALUE=10|INCREMENT=10",
        "|RECORD=CatalogItem|ITEMTYPE=Automatic-NonVault|UNIQUEID=parts.SchLib\\\\RES|DESIGNITEMID=RES"
        "|DESCRIPTION=Resistor 0603|LINENUMBER=",
        "|RECORD=PartChoice|MANUFACTURER=Maker A|MANUFACTURERPARTNO=RA-0603|SUPPLIER=Shop|BESTUNITPRICE=0.1",
        "|RECORD=Solution|MANUFACTURER=Maker A|MANUFACTURERPARTNO=RA-0603|RANK=5",
        "|RECORD=PartChoiceGroups|GROUPBYFIELDCOUNT=0",
        "|RECORD=CatalogItem|ITEMTYPE=Manual-Custom|UNIQUEID=0f0e0d0c|DESIGNITEMID=Custom row 1"
        "|DESCRIPTION=Bare board|LINENUMBER=",
        "|RECORD=Solution|MANUFACTURER=Board shop|MANUFACTURERPARTNO=PCB-1|RANK=5",
        "|RECORD=PartChoiceGroups|GROUPBYFIELDCOUNT=0",
        "|RECORD=Item|ITEMTYPE=Manual-Custom|UNIQUEID=0f0e0d0c|DESIGNATOR=|INDEX=0|QUANTITY=2",
    ]
)


def _comp(ref: str, comment: str, lib: str = "RES", **params: str) -> dict[str, Any]:
    return {
        "ref": ref,
        "comment": comment,
        "lib": lib,
        "footprint": "R0603",
        "description": "",
        "params": params,
    }


@pytest.mark.parametrize("item", OUTJOBS, ids=[item.id for item in OUTJOBS])
def test_public_outjob(item: Any) -> None:
    """Scenario "Public output jobs": every output of the file, with its name, type and output folder."""
    path = require(item)
    job = read_outjob(path.read_bytes(), file=path.name)
    scene = outjob_scene(path)
    outputs = [o for g in job.groups for o in g.outputs]
    assert scene["kind"] == "table" and len(scene["rows"]) == len(outputs) > 0
    names = scene["columns"].index("Output"), scene["columns"].index("Type")
    assert [(r[names[0]], r[names[1]]) for r in scene["rows"]] == [(o.name, o.type) for o in outputs]
    containers = scene["columns"].index("Containers")
    assert any(" → " in row[containers] for row in scene["rows"])  # an output folder is shown


def test_authored_outjob(tmp_path: Path) -> None:
    path = tmp_path / "Docs.OutJob"
    path.write_text(JOB, encoding="utf-8")
    scene = outjob_scene(path)
    drawing, bom = scene["rows"]
    assert drawing[1:5] == ["Assembly Drawing", "PCBDrawing", "Documentation", "board_Assembly.PCBDwf"]
    assert drawing[-1] == "PDF (Publish) → Outputs\\[Media Name]\\board.PDF"
    assert bom[-1] == "Data (GeneratedFiles) → Outputs\\[Output Type]"  # never the absolute folder
    assert scene["docs"] == [["board_Assembly.PCBDwf"], ["[bom]"]]


def test_bom_document(tmp_path: Path) -> None:
    path = tmp_path / "board.BomDoc"
    path.write_text(BOM, encoding="latin-1")
    doc = read_bomdoc(path.read_bytes())
    assert doc.group_by == ("Comment", "Footprint") and doc.numbering == (10, 10)
    assert [(i.design_item_id, i.manual, i.part_number) for i in doc.catalog] == [
        ("RES", False, "RA-0603"),
        ("Custom row 1", True, "PCB-1"),
    ]
    alone = bom_scene(path)
    assert alone["columns"][:5] == ["Line #", "Designator", "Value", "Footprint", "Quantity"]
    assert "Supplier" not in alone["columns"] and "Price@Default" not in alone["columns"]
    sheets = {
        "a.SchDoc": {"comps": [_comp("R2", "10k", Tolerance="1%"), _comp("R10", "10k"), _comp("R1", "1k")]},
        "b.SchDoc": {"comps": [_comp("R3", "10k"), _comp("U1", "MCU", lib="MCU"), _comp("#PWR1", "VCC")]},
    }
    scene = with_parts(alone, sheets)
    rows = {r[1]: r for r in scene["rows"]}
    col = {name: k for k, name in enumerate(scene["columns"])}
    assert rows["R2, R3, R10"][col["Quantity"]] == "3"  # grouped by Comment and Footprint, natural order
    assert rows["R2, R3, R10"][col["Manufacturer Part Number"]] == "RA-0603"
    assert rows["R2, R3, R10"][col["Description"]] == "Resistor 0603"
    assert rows["R2, R3, R10"][col["Tolerance"]] == "1%"
    assert rows["U1"][col["Manufacturer"]] == ""  # no catalog item for its design item id
    assert rows[""][col["Description"]] == "Bare board" and rows[""][col["Quantity"]] == "2"  # a manual line
    assert [r[col["Value"]] for r in scene["rows"]] == ["", "1k", "10k", "MCU"]  # sorted by Comment
    assert [r[0] for r in scene["rows"]] == ["10", "20", "30", "40"]
    assert scene["refs"][2] == ["R2", "R3", "R10"] and scene["meta"]["counts"]["parts"] == 5
