# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Container measurement of the public Altium Draftsman documents (change c0172, task 1.2;
``H-A-DWF-CONTAINER``, ``H-A-DWF-FIELD``).

The four rows ``altium-third-party-pcbdwf-01`` to ``-04`` (S-0785, S-0786) are measured with
``tools/draftsman_census.py``. The expected values are counts and container bytes only, recorded in
``docs/evidence/altium-draftsman.md``, "Census"; no value or name of a document's content is kept.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium.read.draftsman import NAMESPACE, read_draftsman, summary

pytestmark = pytest.mark.needs_corpus
ROOT = Path(__file__).resolve().parents[2]
ROWS = manifest_items("altium-draftsman")
CONTAINER: dict[str, dict[str, Any]] = {
    "altium-third-party-pcbdwf-01": {
        "first_bytes": "01 80 80 40 8d 75 f2 5a",
        "chunks": 73,
        "flags": {"1": 73},
        "last_chunk_size": 783065,
        "decoded_bytes": 76280537,
        "elements": 2662429,
    },
    "altium-third-party-pcbdwf-02": {
        "first_bytes": "01 80 80 40 f5 e0 02 f2",
        "chunks": 26,
        "flags": {"0": 2, "1": 24},
        "last_chunk_size": 349325,
        "decoded_bytes": 26563725,
        "elements": 1089079,
    },
    "altium-third-party-pcbdwf-03": {
        "first_bytes": "01 80 80 40 be a0 02 f2",
        "chunks": 6,
        "flags": {"1": 6},
        "last_chunk_size": 719643,
        "decoded_bytes": 5962523,
        "elements": 243822,
    },
    "altium-third-party-pcbdwf-04": {
        "first_bytes": "01 80 80 40 d6 92 05 f2",
        "chunks": 4,
        "flags": {"1": 4},
        "last_chunk_size": 645697,
        "decoded_bytes": 3791425,
        "elements": 172161,
    },
}
"""Per row, the measured container (``docs/evidence/altium-draftsman.md``, "Census")."""
FULL_CHUNK = 1 << 20


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("draftsman_census", ROOT / "tools" / "draftsman_census.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_container_rows_declared() -> None:
    """The manifest holds the four rows of the census, from two repositories."""
    assert sorted(item.id for item in ROWS) == sorted(CONTAINER)


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_container(item: CorpusItem) -> None:
    """Every chunk is a stored or an LZ4 chunk of at most 1 MiB, every LZ4 block decodes on its own, the
    file ends with its last chunk, the text is one well-formed XML document of the Draftsman namespace,
    the four bytes after ``01 80 80 40`` are the first chunk's stored length and the start of its block,
    and no other candidate of design Decision 1 decodes any chunk."""
    path = require(item)
    row = _tool().measure(path.read_bytes())
    wanted = CONTAINER[item.id]
    assert row["first_bytes"] == wanted["first_bytes"]
    assert row["first_four_are_flag_and_size"] and row["field_is_length_and_first_token"]
    assert row["chunks"] == wanted["chunks"]
    assert row["flags"] == wanted["flags"]
    assert row["full_chunk_sizes"] == {str(FULL_CHUNK): wanted["chunks"] - 1}
    assert 0 < row["last_chunk_size"] <= FULL_CHUNK and row["last_chunk_size"] == wanted["last_chunk_size"]
    assert row["decoded_bytes"] == wanted["decoded_bytes"]
    assert row["largest_offset"] <= 0xFFFF
    assert row["starts_with_document"]
    assert row["xml"] == {"well_formed": True, "namespace_ok": True, "elements": wanted["elements"]}
    candidates = row["candidates"]
    assert candidates.pop("lz4-block-chunks") == wanted["flags"].get("1", 0)
    assert set(candidates.values()) == {0}, candidates


SHEETS = {
    "altium-third-party-pcbdwf-01": 2,
    "altium-third-party-pcbdwf-02": 3,
    "altium-third-party-pcbdwf-03": 1,
    "altium-third-party-pcbdwf-04": 1,
}
"""Sheets per row (``docs/evidence/altium-draftsman.md``, "Census")."""


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_samples_decode(item: CorpusItem) -> None:
    """Scenario "Public samples decode": the product reader decodes each row into a Draftsman document of
    the namespace, with as many chunks as the measuring tool counts and at least one sheet."""
    file = read_draftsman(require(item).read_bytes())
    assert file.root.tag == f"{{{NAMESPACE}}}Document"
    assert len(file.chunks) == CONTAINER[item.id]["chunks"]
    sheets = summary(file).sheets
    assert len(sheets) == SHEETS[item.id] and all(sheet.items for sheet in sheets)


def test_container_output_holds_no_content() -> None:
    """The tool's report holds counts, container bytes and candidate names, never a path or a name of the
    documents' content."""
    tool = _tool()
    rows = [(item.id, require(item)) for item in ROWS[-1:]]
    text = json.dumps(tool.census(rows))
    for path in (path for _, path in rows):
        assert str(path) not in text and path.name not in text
    assert "Document" not in text and "Altium" not in text


TREE: dict[str, dict[str, Any]] = {
    "altium-third-party-pcbdwf-01": {
        "elements": 2662429,
        "board_data_percent": 96.6,
        "kinds": {"BoardAssemblyViewData": 2, "Line": 16, "Picture": 2, "Text": 31},
        "views": [["board-assembly", "Top", ["2", "5"]], ["board-assembly", "Bottom", ["1", "2"]]],
        "tables": [],
        "note_entries": [],
        "parameter_texts": 14,
        "document_parameters": 31,
    },
    "altium-third-party-pcbdwf-02": {
        "elements": 1089079,
        "board_data_percent": 99.5,
        "kinds": {
            "BoardFabricationViewData": 6,
            "DrillTableBoardView": 1,
            "LayerStackLegendView": 1,
            "Line": 24,
            "Picture": 5,
            "Text": 48,
            "TransmissionLineTableData": 1,
        },
        "views": [
            *[["board-fabrication", "Top", ["1", "1"]]] * 3,
            ["board-fabrication", "Top", ["1", "2"]],
            *[["board-fabrication", "Top", ["1", "1"]]] * 2,
            ["layer-stack-legend", None, []],
        ],
        "tables": [["drill-table", None], ["transmission-line", None]],
        "note_entries": [],
        "parameter_texts": 21,
        "document_parameters": 31,
    },
    "altium-third-party-pcbdwf-03": {
        "elements": 243822,
        "board_data_percent": 95.3,
        "kinds": {
            "BillOfMaterialsView": 1,
            "BoardAssemblyViewData": 4,
            "Line": 14,
            "LinearDimension": 3,
            "Picture": 2,
            "Rectangle": 1,
            "Text": 19,
        },
        "views": [["board-assembly", side, ["1", "2"]] for side in ("Top", "Right", "Front", "Bottom")],
        "tables": [["bill-of-materials", "All"]],
        "note_entries": [],
        "parameter_texts": 10,
        "document_parameters": 42,
    },
    "altium-third-party-pcbdwf-04": {
        "elements": 172161,
        "board_data_percent": 97.8,
        "kinds": {
            "BoardFabricationViewData": 1,
            "Callout": 1,
            "DrillTableBoardView": 1,
            "DrillViewView": 1,
            "LayerStackLegendView": 1,
            "Line": 14,
            "LinearDimension": 2,
            "Note": 1,
            "Picture": 2,
            "Rectangle": 1,
            "Text": 19,
        },
        "views": [
            ["layer-stack-legend", None, []],
            ["drill-drawing", "Top", ["1", "2"]],
            ["board-fabrication", "Top", ["1", "2"]],
        ],
        "tables": [["drill-table", None]],
        "note_entries": [12],
        "parameter_texts": 10,
        "document_parameters": 42,
    },
}
"""Per row, the tree census (``docs/evidence/altium-draftsman.md``, "Census", "Tree")."""
VERSION_MEMBERS = {"DocumentId", "LayoutDrawingData", "WiringDiagramData", "WiringListInformationData"}
"""The root members that only the two documents of format version 22 hold."""


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_tree(item: CorpusItem) -> None:
    """Task 2.2, the public half: the forms of the sheets, views, tables, notes and parameters, and the
    share of the board data members (design Decision 4)."""
    row = _tool().tree(require(item).read_bytes())
    wanted = TREE[item.id]
    for key, value in wanted.items():
        assert row[key] == value, key
    assert len(row["sheets"]) == SHEETS[item.id]
    assert ({"22": 37, "21": 33}[row["format_version"]]) == len(row["root_members"])
    assert (VERSION_MEMBERS <= set(row["root_members"])) == (row["format_version"] == "22")
