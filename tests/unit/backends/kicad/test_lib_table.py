# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library identifiers and library tables (kicad-library-resolution)."""

from __future__ import annotations

import pytest
from _libs import MINI

import fenolite.backends.kicad as kicad
from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibRow, read_lib_table, split_lib_id
from fenolite.core.errors import FormatError, Issue

PROJECT = MINI / "project"


def test_qualified_identifier() -> None:
    assert split_lib_id("Resistor_SMD:R_0603_1608Metric") == ("Resistor_SMD", "R_0603_1608Metric")


@pytest.mark.parametrize("bad", ["R_0603", "A:B:C", ":R", "Device:", ""])
def test_invalid_identifiers(bad: str) -> None:
    with pytest.raises(LibraryError) as caught:
        split_lib_id(bad)
    assert caught.value.issue.code == "kicad.lib.invalid-id" and caught.value.issue.severity == "error"


def test_10_syntax() -> None:
    table = read_lib_table(PROJECT / "fp-lib-table")
    assert table.kind == "footprint" and table.version == 7 and table.path.endswith("fp-lib-table")
    mini = table.rows[0]
    assert mini == LibRow("Mini", "KiCad", "${KIPRJMOD}/../Mini.pretty", "", "Authored mini library")
    assert [r.nickname for r in table.rows] == [
        "Mini",
        "MiniRel",
        "MiniDisabled",
        "MiniHidden",
        "MiniLegacy",
        "Nested",
    ]


def test_9_syntax() -> None:
    table = read_lib_table(PROJECT / "nested" / "fp-lib-table")
    assert table.version is None and table.kind == "footprint"
    assert table.rows == (LibRow("NestedMini", "KiCad", "../Mini_v9.pretty", "", "Nested relative row"),)
    quoted = read_lib_table(
        '(fp_lib_table (lib (name "NestedMini") (type "KiCad") (uri "../Mini_v9.pretty") (options "")'
        ' (descr "Nested relative row")))'
    )
    assert quoted.rows == table.rows


def test_disabled_and_hidden_rows() -> None:
    rows = {r.nickname: r for r in read_lib_table(PROJECT / "sym-lib-table").rows}
    assert rows["MiniDisabled"].disabled and not rows["MiniDisabled"].hidden
    assert rows["MiniHidden"].hidden and not rows["MiniHidden"].disabled
    assert rows["MiniLegacy"].type == "Legacy" and rows["Nested"].type == "Table"


def test_duplicate_nickname() -> None:
    row = '(lib (name "Mini") (type "KiCad") (uri "{}"))'
    text = f"(fp_lib_table {row.format('/a')} {row.format('/b')})"
    issues: list[Issue] = []
    table = read_lib_table(text, issues=issues)
    assert [r.uri for r in table.rows] == ["/a"]
    assert [(i.code, i.severity) for i in issues] == [("kicad.lib.duplicate-nickname", "warning")]


def test_unknown_children_are_ignored_with_an_info() -> None:
    text = '(sym_lib_table (version 7) (lib (name "A") (type "KiCad") (uri "/a") (frob 1)) (extra))'
    issues: list[Issue] = []
    table = read_lib_table(text, issues=issues)
    assert table.kind == "symbol" and len(table.rows) == 1
    assert [(i.code, i.severity) for i in issues] == [("kicad.lib.kept-opaque", "info")] * 2


def test_design_block_table_refused() -> None:
    with pytest.raises(FormatError, match="design_block_lib_table"):
        read_lib_table('(design_block_lib_table (version 7) (lib (name "A") (type "KiCad") (uri "/a")))')


@pytest.mark.parametrize(
    "text",
    ['(fp_lib_table (lib (type "KiCad") (uri "/a")))', "(fp_lib_table (version x))"],
)
def test_malformed_tables(text: str) -> None:
    with pytest.raises(FormatError):
        read_lib_table(text)


def test_package_re_exports() -> None:
    assert kicad.LibraryError is LibraryError and kicad.split_lib_id is split_lib_id
    for name in (
        "read_footprint",
        "read_symbol_library",
        "resolve_extends",
        "LibraryResolver",
        "LibraryConfig",
    ):
        assert name in kicad.__all__
