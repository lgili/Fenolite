# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Frames of binary streams and lines of the ASCII form (capability altium-schematic-reader, "Binary record
framing")."""

from __future__ import annotations

import pytest

from fenolite.backends.altium.read.sch.framing import (
    Frame,
    deframe,
    enframe,
    join_lines,
    line_end,
    split_lines,
)
from fenolite.core.errors import FormatError

TWO_RECORDS = bytes.fromhex("06000000") + b"|A=1\0\0" + bytes.fromhex("03000001") + b"abc"


def test_two_records() -> None:
    assert len(TWO_RECORDS) == 17
    frames = deframe(TWO_RECORDS, where="FileHeader")
    assert frames == (Frame(0, b"|A=1\0\0", 0), Frame(1, b"abc", 10))
    assert enframe(frames) == TWO_RECORDS


def test_cut_payload() -> None:
    data = (20).to_bytes(4, "little") + b"12345678"
    with pytest.raises(FormatError) as caught:
        deframe(data, where="FileHeader", file="a.SchDoc")
    assert (caught.value.file, caught.value.locator, caught.value.offset) == (
        "a.SchDoc",
        "FileHeader/record 0",
        0,
    )


def test_cut_length_word() -> None:
    data = bytes.fromhex("01000000") + b"x" + b"\x05\x00"
    with pytest.raises(FormatError) as caught:
        deframe(data, where="Additional")
    assert (caught.value.locator, caught.value.offset) == ("Additional/record 1", 5)


def test_empty_stream() -> None:
    assert deframe(b"", where="Storage") == ()
    assert enframe(()) == b""


def test_tuples_and_limits() -> None:
    assert enframe([(1, b"ab")]) == bytes.fromhex("02000001") + b"ab"
    with pytest.raises(ValueError):
        enframe([(256, b"")])


def test_lines() -> None:
    data = b"a\r\nb\nc"
    lines = split_lines(data)
    assert lines == (b"a\r\n", b"b\n", b"c")
    assert [line_end(line) for line in lines] == [b"\r\n", b"\n", b""]
    assert join_lines(lines) == data
    assert split_lines(b"") == ()
    assert split_lines(b"x\n") == (b"x\n",)
