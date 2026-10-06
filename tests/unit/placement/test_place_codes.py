# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed set of ``place.*`` codes and the evidence of placement (capability placement, "Placement issue
codes" and "Placement evidence"; change c0022)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from fenolite.core.errors import Issue
from fenolite.core.evidence import Level
from fenolite.placement import EVIDENCE, ISSUE_CODES
from fenolite.placement.codes import issue
from fenolite.verify.hypotheses import load_register

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "fenolite"
CONTRACT = ROOT / "docs" / "cli-contract.md"
PREFIX = "place."
EXPECTED = {
    "place.courtyard-overlap": "error",
    "place.outside-outline": "error",
    "place.no-definition": "error",
    "place.locked": "error",
    "place.unknown-ref": "error",
    "place.keepout": "error",
    "place.edge-clearance": "warning",
    "place.no-room": "warning",
    "place.copper-left": "warning",
    "place.script-locked": "warning",
    "place.keepout-no-courtyard": "warning",
    "place.no-extent": "info",
    "place.no-outline": "info",
    "place.constraint": "error",
    "place.incomplete": "warning",
    "place.objective": "warning",
}
BOTH_MAJORS = "KICAD-VERIFIED (9.0.x, 10.0.x)"


def sources() -> list[Path]:
    """The modules that may emit a ``place.*`` code."""
    named = [
        SRC / "backends" / "kicad" / "replace.py",
        SRC / "cli" / "cmd_place.py",
        SRC / "cli" / "cmd_build.py",
    ]
    return [*sorted((SRC / "placement").glob("*.py")), *(path for path in named if path.is_file())]


def code_literals(paths: list[Path]) -> set[str]:
    found: set[str] = set()
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
                if (
                    text.startswith(PREFIX)
                    and " " not in text
                    and text[-1] != "."
                    and len(text) > len(PREFIX)
                ):
                    found.add(text)
    return found


def test_codes_closed_set() -> None:
    found = code_literals(sources())
    assert found <= set(ISSUE_CODES), sorted(found - set(ISSUE_CODES))
    assert {"place.courtyard-overlap", "place.no-definition"} <= found
    text = CONTRACT.read_text(encoding="utf-8")
    assert [code for code in ISSUE_CODES if f"`{code}`" not in text] == []


def test_codes_closed_set_detects_an_unknown_code(tmp_path: Path) -> None:
    module = tmp_path / "module.py"
    module.write_text('CODE = "place.made-up"\nNOTE = "place. is a prefix"\n', encoding="utf-8")
    assert code_literals([module]) - set(ISSUE_CODES) == {"place.made-up"}


def test_codes_table_severities() -> None:
    assert dict(ISSUE_CODES) == EXPECTED
    assert issue("place.no-room", "m", "R1") == Issue("place.no-room", "warning", "m", where="R1")
    with pytest.raises(KeyError):
        issue("place.made-up", "m")
    with pytest.raises(TypeError):
        ISSUE_CODES["place.new"] = "error"  # type: ignore[index]


def test_evidence_follows_the_register() -> None:
    rows = {row.id: row for row in load_register(ROOT / "docs" / "hypotheses.md")}
    assert EVIDENCE.hypotheses == ("H-K-PLACE-MOVE", "H-K-PLACE-TOUCH")
    verified = all(
        rows[name].level_text == BOTH_MAJORS and not rows[name].refuted for name in EVIDENCE.hypotheses
    )
    assert EVIDENCE.level is (Level.KICAD_VERIFIED if verified else Level.INFERRED)
