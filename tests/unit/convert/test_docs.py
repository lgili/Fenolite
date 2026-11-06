# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``docs/conversion.md`` and the section ``convert`` of ``docs/cli-contract.md`` say what the code does
(change c0159)."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from fenolite.api.conversion import profiles
from fenolite.convert import DIRECTIONS, ISSUE_CODES
from fenolite.convert.report import EXPLAINS, KINDS

ROOT = Path(__file__).resolve().parents[3]
PAGE = (ROOT / "docs" / "conversion.md").read_text(encoding="utf-8")
CONTRACT = (ROOT / "docs" / "cli-contract.md").read_text(encoding="utf-8")


def _rows(marker: str) -> list[list[str]]:
    body = PAGE.split(f"<!-- {marker}:begin -->", 1)[1].split(f"<!-- {marker}:end -->", 1)[0]
    lines = body.strip().splitlines()[2:]
    return [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]


def _section(name: str) -> str:
    return CONTRACT.split(f"## {name}\n", 1)[1].split("\n## ", 1)[0]


def test_kinds_table_is_the_code() -> None:
    assert _rows("kinds") == [[f"`{row.name}`", row.group, row.loss] for row in KINDS]


def test_explains_table_names_every_row() -> None:
    named = {kind.strip("` ") for row in _rows("explains") for kind in row[0].split(",")}
    assert named == {row.kind for row in EXPLAINS}


def test_profiles_and_directions_are_documented() -> None:
    for name in profiles():
        assert f"`{name}`" in PAGE
    for source, target in DIRECTIONS:
        assert re.search(rf"^\| {source} \| {target} \|", PAGE, re.MULTILINE), (source, target)


def test_contract_section() -> None:
    section = _section("convert")
    for code in ISSUE_CODES:
        assert f"`{code}`" in section
    for flag in ("--to", "--out", "--name", "--altium-bodies", "--report-ids", "--no-verify"):
        assert f"`{flag}" in section
    for key in ("source", "target", "files", "report", "equivalence", "experimental"):
        assert f"| `{key}` |" in section
    assert "docs/conversion.md" in section


def test_altium_page_links_the_conversion() -> None:
    assert "docs/conversion.md" in (ROOT / "docs" / "altium.md").read_text(encoding="utf-8")


def test_current_pairing_measurements_bind_declared_inputs() -> None:
    """Current backend comparisons supplement dated tables; they make no native-application claim."""
    path = ROOT / "docs/evidence/conversion-comparison-c0319.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    manifest = tomllib.loads((ROOT / "tests/corpus/manifest.toml").read_text(encoding="utf-8"))
    declared = {row["id"]: row for row in manifest["file"]}
    assert record["schema"] == "fenolite.conversion-comparison.v0"
    assert record["source_commit"] == "46d788ee0e10516838a4b0a63b254eab2a475fd1"
    assert record["native_tool"] is None
    assert set(record["rows"]) == {"08", "16"}
    for key, row in record["rows"].items():
        assert row["input_id"] == f"kicad-demo-10-0-6-pcb-{key}"
        assert (row["input_ref"], row["input_sha256"]) == (
            declared[row["input_id"]]["ref"],
            declared[row["input_id"]]["sha256"],
        )
    assert record["rows"]["08"]["differences"] == {}
    assert record["rows"]["16"]["differences"] == {
        "dnp": 11,
        "net-tie-copper": 25,  # compared since change c0431, which writes a net tie's copper
        "pad-missing": 17,  # 20 before change c0433 kept pads without a number in their component
        "route-connectivity": 1,
    }
    page = (ROOT / "docs/evidence/conversion.md").read_text(encoding="utf-8")
    assert path.name in page and "historical" in page
