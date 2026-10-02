# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project library tables written per target (capability kicad-library-resolution, "Project library
tables are written per target"; change c0011)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad.libs import LibRow, LibTable, read_lib_table, write_lib_table

TABLE = LibTable("footprint", (LibRow("Mini", "KiCad", "${KIPRJMOD}/lib/Mini.pretty"),))


def test_target_10_form() -> None:
    text = write_lib_table(TABLE, target=10)
    assert text.startswith("(fp_lib_table\n\t(version 7)\n") and text.endswith(")\n")
    assert (
        '\t(lib (name "Mini") (type "KiCad") (uri "${KIPRJMOD}/lib/Mini.pretty") (options "") (descr ""))\n'
        in text
    )


def test_target_9_form() -> None:
    text = write_lib_table(TABLE, target=9)
    assert "version" not in text
    assert (
        '\t(lib (name Mini) (type KiCad) (uri ${KIPRJMOD}/lib/Mini.pretty) (options "") (descr ""))\n' in text
    )


def test_read_back_equal() -> None:
    nine, ten = (read_lib_table(write_lib_table(TABLE, target=t)) for t in (9, 10))
    assert nine.rows == ten.rows == TABLE.rows and (nine.version, ten.version) == (None, 7)


def test_flags_symbols_and_quoting() -> None:
    table = LibTable("symbol", (LibRow("A b", "KiCad", "x", disabled=True, hidden=True),))
    text = write_lib_table(table, target=9)
    assert text.startswith("(sym_lib_table\n") and '(name "A b")' in text and "(disabled) (hidden)" in text
    assert read_lib_table(text).rows == table.rows
    assert write_lib_table(table, target=9) == text


def test_unknown_target() -> None:
    with pytest.raises(ValueError):
        write_lib_table(TABLE, target=8)
