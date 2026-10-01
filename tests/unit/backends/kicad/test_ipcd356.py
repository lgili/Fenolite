# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""IPC-D-356 parsing on authored texts (capability kicad-file-backend, change c0009)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad.ipcd356 import Ipcd356Record, read_ipcd356
from fenolite.core.errors import FormatError


def _record(code: str, net: str, ref: str, pin: str, fields: str, *, mid: str = " ") -> str:
    """A record laid out in the export's fixed columns (reference cut to 6, pin to 4)."""
    dash = "-" if pin else " "
    return f"{code}{net:<14.14}   {ref:<6.6}{dash}{pin:<4.4}{mid}{fields}"


HEADER = "P  CODE 00\nP  UNITS CUST 0\nP  arrayDim   N\n"


def test_through_hole_record() -> None:
    line = _record("317", "GND", "D1", "1", "D0315PA00X+0001000Y-0002000X0591Y0000R030S0")
    export = read_ipcd356(HEADER + line + "\n999\n")
    assert export.unit_nm == 2540
    assert export.records == (Ipcd356Record("317", "GND", "D1", "1", 1000, -2000, 30, "both"),)


def test_surface_record_on_the_bottom() -> None:
    line = _record("327", "OCKETS/VCC_PIC", "JP1", "2", "      A02X+034085Y+022000X0118Y0118R000S1")
    (record,) = read_ipcd356(HEADER + line + "\n").records
    assert (record.code, record.net, record.ref, record.pin) == ("327", "OCKETS/VCC_PIC", "JP1", "2")
    assert (record.x, record.y, record.rotation, record.side) == (34085, 22000, 0, "bottom")


def test_via_and_truncated_records() -> None:
    via = _record("317", "/CLOCK-RB6", "VIA", "", "D0236PA00X+050250Y+017000X0630Y0000R000S3", mid="M")
    long_ref = _record("327", "N1", "ABCDEFG1", "12345", "      A01X+000100Y+000200X0118Y0118R000S1")
    hole = _record("367", "N/C", "P101", "", "D1693UA00X+006000Y+007000X1693Y0000R000S0")
    records = read_ipcd356(HEADER + "\n".join((via, long_ref, hole)) + "\n").records
    assert [(r.code, r.ref, r.pin) for r in records] == [("317", "VIA", ""), ("327", "ABCDEF", "1234")]
    assert records[1].side == "top"


def test_record_without_rotation() -> None:
    line = _record("317", "A", "R1", "2", "D0315PA00X+000100Y+000200X0591Y0000S0")
    (record,) = read_ipcd356(HEADER + line).records
    assert record.rotation is None


def test_missing_units() -> None:
    line = _record("317", "GND", "D1", "1", "D0315PA00X+0001000Y-0002000X0591Y0000R030S0")
    with pytest.raises(FormatError, match="UNITS"):
        read_ipcd356("P  CODE 00\n" + line + "\n")


def test_unsupported_units() -> None:
    with pytest.raises(FormatError, match="CUST 1"):
        read_ipcd356("P  UNITS CUST 1\n")
