# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kinds table and the issue codes (capability design-equivalence, "Differences are located")."""

from __future__ import annotations

from pathlib import Path

from fenolite.checks import codes as check_codes
from fenolite.checks.equivalence import (
    EQUIVALENCE_CODES,
    Difference,
    EquivalenceReport,
    difference_issues,
    levels,
    model,
)
from fenolite.checks.equivalence import codes as equivalence_codes
from fenolite.checks.equivalence.model import LevelResult
from fenolite.core.errors import ISSUE_CODE

ROOT = Path(__file__).resolve().parents[4]
TABLE = (
    (1, "component-missing", "ref"),
    (1, "ref-ambiguous", "ref"),
    (1, "value", "value"),
    (1, "dnp", "dnp"),
    (2, "pin-missing", "pin"),
    (2, "net", "net"),
    (3, "footprint-missing", "footprint"),
    (3, "footprint-name", "lib_ref"),
    (3, "pad-missing", "pad"),
    (3, "pad-kind", "kind"),
    (3, "pad-shape", "shape"),
    (3, "pad-size", "size"),
    (3, "pad-drill", "drill"),
    (3, "pad-position", "position"),
    (3, "pad-rotation", "rotation"),
    (3, "pad-copper", "layers"),
    (4, "side", "side"),
    (4, "position", "position"),
    (4, "rotation", "rotation"),
)
"""The table of the requirement, written out a second time."""
OTHER = {
    "equiv.excluded": ("info",),
    "equiv.import-message": ("info",),
    "equiv.no-exclusion-profile": ("warning",),
    "equiv.oracle-failed": ("error",),
}


def test_kinds_table_is_closed() -> None:
    assert levels.KINDS == TABLE and levels.KINDS is model.KINDS
    assert len({kind for _, kind, _ in TABLE}) == len(TABLE)
    assert model.LEVELS == (1, 2, 3, 4)
    assert dict(model.LEVEL_NAMES) == {1: "components", 2: "netlist", 3: "footprints", 4: "placement"}
    assert {level for level, _, _ in TABLE} == set(model.LEVELS)


def test_codes_table() -> None:
    kinds = {f"equiv.{kind}": ("error",) for _, kind, _ in TABLE if kind != "net"}
    assert dict(EQUIVALENCE_CODES) == {**kinds, **OTHER}
    assert equivalence_codes.ISSUE_CODES is EQUIVALENCE_CODES
    for code in EQUIVALENCE_CODES:
        assert ISSUE_CODE.match(code), code
    assert "equiv.net" not in EQUIVALENCE_CODES
    assert check_codes.ISSUE_CODES["netlist.assignment-differs"] == ("error",)
    assert not set(EQUIVALENCE_CODES) & set(check_codes.ISSUE_CODES)


def test_every_kind_gives_an_issue_of_its_code() -> None:
    differences = tuple(Difference(level, kind, "R1-1", field, "x", "") for level, kind, field in TABLE)
    report = EquivalenceReport((LevelResult(1, 0, differences),))
    issues = difference_issues(report)
    assert [i.code for i in issues] == [
        "netlist.assignment-differs" if kind == "net" else f"equiv.{kind}" for _, kind, _ in TABLE
    ]
    assert {i.severity for i in issues} == {"error"} and {i.where for i in issues} == {"R1-1"}
    assert (
        issues[0].message == "R1-1: ref is 'x' on side a and nothing on side b (level 1, component-missing)"
    )
    assert issues[5].message == "R1-1 is on x on side a and on  on side b"


def test_docs_list_every_kind() -> None:
    """``docs/equivalence.md`` holds the kinds table of the requirement, row for row."""
    page = (ROOT / "docs" / "equivalence.md").read_text(encoding="utf-8")
    rows = [
        tuple(cell.strip() for cell in line.strip("|").split("|")[:3])
        for line in page.split("## Kinds of difference", 1)[1].split("\n## ", 1)[0].splitlines()
        if line.startswith("| ") and line[2].isdigit()
    ]
    assert rows == [(str(level), f"`{kind}`", f"`{field}`") for level, kind, field in TABLE]
    for name in ("components", "netlist", "footprints", "placement"):
        assert f"`{name}`" in page.split("## Levels", 1)[1].split("\n## ", 1)[0]


def test_docs_list_every_code() -> None:
    """Every code of the table, and the code of a ``net`` difference, is in the contract's section."""
    contract = (ROOT / "docs" / "cli-contract.md").read_text(encoding="utf-8")
    section = contract.split("\n## equivalent\n", 1)[1].split("\n## ", 1)[0]
    for code in (*EQUIVALENCE_CODES, "netlist.assignment-differs"):
        assert f"`{code}`" in section, code
    for exit_code in ("| 0 |", "| 2 |", "| 3 |", "| 5 |", "| 6 |"):
        assert exit_code in section, exit_code
