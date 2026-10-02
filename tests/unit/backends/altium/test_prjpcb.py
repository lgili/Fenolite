# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The project file (capability altium-schematic-writer, "Project file"; change c0032)."""

from __future__ import annotations

import pytest

from fenolite.backends.altium.prjpcb import write_prjpcb


def test_project_of_the_sample() -> None:
    assert write_prjpcb(schematic="altium_sample.SchDoc") == (
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=altium_sample.SchDoc\r\n"
    )


def test_no_byte_order_mark_and_ascii_only() -> None:
    data = write_prjpcb(schematic="x.SchDoc")
    assert not data.startswith(b"\xef\xbb\xbf")
    assert all(0x20 <= b <= 0x7E for b in data.replace(b"\r\n", b""))
    assert data.count(b"\r\n") == 5 and b"\n" not in data.replace(b"\r\n", b"")


@pytest.mark.parametrize("name", ["", "sub/x.SchDoc", "sub\\x.SchDoc", "µ.SchDoc", "a|b.SchDoc"])
def test_unwritable_names(name: str) -> None:
    with pytest.raises(ValueError):
        write_prjpcb(schematic=name)
