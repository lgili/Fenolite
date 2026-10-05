# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stable surface for later changes (capability altium-schematic-reader, "Reader interfaces for later
changes", "Schematic reader entry points")."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

from fenolite.backends.altium.read import sch, schlib
from fenolite.core.evidence import min_level
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[5]
REGISTER = ROOT / "docs" / "hypotheses.md"
SCH_NAMES = {
    "read_schematic",
    "detect",
    "encode_stream",
    "check_identity",
    "SchDocument",
    "SchRecord",
    "UnknownRecord",
    "PropertyRecord",
    "RecordRef",
    "PropertyList",
    "Prop",
    "SchLength",
    "Color",
    "Font",
    "Harness",
    "EmbeddedFile",
    "RECORD_TYPES",
    "ISSUE_CODES",
    "DEFAULT_CODEPAGE",
    "MAX_EMBEDDED",
    "UNIT_NM",
    "EVIDENCE",
}
SCHLIB_NAMES = {"read_schlib", "encode_stream", "SchLibrary", "SchLibComponent", "SIDE_STREAMS_DECODED"}
DOCUMENT_METHODS = (
    "components",
    "wires",
    "buses",
    "net_labels",
    "power_ports",
    "ports",
    "junctions",
    "no_ercs",
    "sheet_symbols",
    "harnesses",
    "templates",
    "template_children",
)


def test_surface_exists() -> None:
    assert sorted(SCH_NAMES - set(sch.__all__)) == []
    assert sorted(SCHLIB_NAMES - set(schlib.__all__)) == []
    assert {cls.__name__ for cls in sch.RECORD_TYPES.values()} <= set(sch.__all__)
    for name in sch.__all__:
        assert hasattr(sch, name), name
    for name in schlib.__all__:
        assert hasattr(schlib, name), name


def test_document_accessors_and_signatures() -> None:
    for name in DOCUMENT_METHODS:
        assert callable(getattr(sch.SchDocument, name)), name
    parameters = inspect.signature(sch.read_schematic).parameters
    assert list(parameters) == ["data", "file", "codepage", "issues"]
    assert all(
        parameters[name].kind is inspect.Parameter.KEYWORD_ONLY for name in ("file", "codepage", "issues")
    )
    assert list(inspect.signature(schlib.read_schlib).parameters) == ["data", "file", "codepage", "issues"]
    assert sch.DEFAULT_CODEPAGE == "cp1252" and sch.UNIT_NM == 254_000


def test_evidence_is_the_lowest_registered_row() -> None:
    rows = {row.id: row for row in load_register(REGISTER) if row.id.startswith("H-A-RD-SCH-")}
    assert set(sch.HYPOTHESES) == set(rows)
    live = {ident: row for ident, row in rows.items() if not row.refuted}
    assert set(sch.REFUTED) == set(rows) - set(live) == {"H-A-RD-SCH-TEXT"}
    assert set(sch.EVIDENCE.hypotheses) == set(live), "a refuted row supports no claim (change c0067)"
    assert sch.EVIDENCE.level == min_level(*(row.level for row in live.values()))


def test_capabilities_do_not_list_the_reader() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "fenolite", "capabilities", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    text = json.dumps(json.loads(result.stdout))
    assert "read.sch" not in text and "schematic-reader" not in text and "read_schlib" not in text
