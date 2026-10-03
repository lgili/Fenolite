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


def test_project_with_a_library() -> None:
    assert write_prjpcb(schematic="altium_sample.SchDoc", libraries=("FenoliteSample.SchLib",)) == (
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=altium_sample.SchDoc\r\n\r\n"
        b"[Document2]\r\nDocumentPath=FenoliteSample.SchLib\r\n"
    )


def test_project_with_a_pcb_document_and_two_libraries() -> None:
    """``altium-schematic-writer`` "Project file" (change c0035)."""
    data = write_prjpcb(
        schematic="blink.SchDoc", pcb="blink.PcbDoc", libraries=("blink.SchLib", "blink.PcbLib")
    )
    assert data == (
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=blink.SchDoc\r\n\r\n"
        b"[Document2]\r\nDocumentPath=blink.PcbDoc\r\n\r\n[Document3]\r\nDocumentPath=blink.PcbLib\r\n\r\n"
        b"[Document4]\r\nDocumentPath=blink.SchLib\r\n"
    )


def test_pcb_document_path_refused() -> None:
    with pytest.raises(ValueError):
        write_prjpcb(schematic="b.SchDoc", pcb="x/b.PcbDoc")


# --- module sheets and harness definition files (change c0037) --------------------------------------


def test_project_with_a_module_sheet_and_a_harness_file() -> None:
    data = write_prjpcb(schematic="a.SchDoc", sheets=("a_x.SchDoc",), harnesses=("a.Harness",))
    assert data == (
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\n\r\n"
        b"[Document2]\r\nDocumentPath=a_x.SchDoc\r\n\r\n[Document3]\r\nDocumentPath=a.Harness\r\n"
    )


def test_unchanged_without_sheets() -> None:
    plain = write_prjpcb(
        schematic="blink.SchDoc", pcb="blink.PcbDoc", libraries=("blink.SchLib", "blink.PcbLib")
    )
    assert plain == write_prjpcb(
        schematic="blink.SchDoc",
        pcb="blink.PcbDoc",
        libraries=("blink.SchLib", "blink.PcbLib"),
        sheets=(),
        harnesses=(),
    )
    assert plain.count(b"[Document") == 4 and b"[Document2]\r\nDocumentPath=blink.PcbDoc\r\n" in plain


def test_sheets_keep_their_order_and_harnesses_are_sorted() -> None:
    data = write_prjpcb(
        schematic="d.SchDoc",
        pcb="d.PcbDoc",
        libraries=("L.SchLib",),
        sheets=("d_flash.SchDoc", "d_mcu.SchDoc", "d_Adc.SchDoc"),
        harnesses=("d_flash.Harness", "d.Harness", "d_mcu.Harness"),
    )
    paths = [line.partition("=")[2] for line in data.decode("ascii").split("\r\n") if line.startswith("Doc")]
    assert paths == [
        "d.SchDoc",
        "d.PcbDoc",
        "L.SchLib",
        "d_flash.SchDoc",
        "d_mcu.SchDoc",
        "d_Adc.SchDoc",
        "d.Harness",
        "d_mcu.Harness",
        "d_flash.Harness",
    ]
    numbers = [line for line in data.decode("ascii").split("\r\n") if line.startswith("[Document")]
    assert numbers == [f"[Document{n}]" for n in range(1, 10)]


@pytest.mark.parametrize("name", ["sub/a_x.SchDoc", "sub\\a_x.SchDoc", "a|x.SchDoc", ""])
def test_sheet_and_harness_names_are_bare_file_names(name: str) -> None:
    with pytest.raises(ValueError):
        write_prjpcb(schematic="a.SchDoc", sheets=(name,))
    with pytest.raises(ValueError):
        write_prjpcb(schematic="a.SchDoc", harnesses=(name,))
