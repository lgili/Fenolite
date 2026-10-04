# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The project file (capability altium-schematic-writer, "Project file"; change c0032)."""

from __future__ import annotations

import pytest

from fenolite.backends.altium.prjpcb import CLASS_GENERATION, SHEET_CLASS_KEYS, write_prjpcb

SHEET_KEYS = b"ClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n"
"""The three class keys of a schematic document of a project with module sheets (change c0048)."""
CLASS_SECTION = (
    b"\r\n[PrjClassGen]\r\nCompClassManualEnabled=0\r\nCompClassManualRoomEnabled=0\r\n"
    b"NetClassAutoBusEnabled=1\r\nNetClassAutoCompEnabled=0\r\nNetClassAutoNamedHarnessEnabled=0\r\n"
    b"NetClassManualEnabled=1\r\nNetClassSeparateForBusSections=0\r\n"
)


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
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=blink.SchDoc\r\n" + SHEET_KEYS + b"\r\n"
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
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\n" + SHEET_KEYS + b"\r\n"
        b"[Document2]\r\nDocumentPath=a_x.SchDoc\r\n" + SHEET_KEYS + b"\r\n"
        b"[Document3]\r\nDocumentPath=a.Harness\r\n"
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
    """``H-A-SCH-HIER-ORDER``: the top sheet, the module sheets in the order given, then the PCB document,
    the libraries and the harness files; every schematic document precedes every other document."""
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
        "d_flash.SchDoc",
        "d_mcu.SchDoc",
        "d_Adc.SchDoc",
        "d.PcbDoc",
        "L.SchLib",
        "d.Harness",
        "d_mcu.Harness",
        "d_flash.Harness",
    ]
    numbers = [line for line in data.decode("ascii").split("\r\n") if line.startswith("[Document")]
    assert numbers == [f"[Document{n}]" for n in range(1, 10)]
    last_sheet = max(i for i, path in enumerate(paths) if path.endswith(".SchDoc"))
    assert all(path.endswith(".SchDoc") for path in paths[: last_sheet + 1])


@pytest.mark.parametrize("name", ["sub/a_x.SchDoc", "sub\\a_x.SchDoc", "a|x.SchDoc", ""])
def test_sheet_and_harness_names_are_bare_file_names(name: str) -> None:
    with pytest.raises(ValueError):
        write_prjpcb(schematic="a.SchDoc", sheets=(name,))
    with pytest.raises(ValueError):
        write_prjpcb(schematic="a.SchDoc", harnesses=(name,))


# --- class generation keys (change c0048) ------------------------------------------------------------


def test_project_of_a_flat_design_with_a_net_class() -> None:
    """Scenario "Project of a flat design with a net class"."""
    assert write_prjpcb(schematic="a.SchDoc", net_classes=True) == (
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\n" + CLASS_SECTION
    )


def test_project_with_a_module_sheet_has_the_class_keys() -> None:
    """Scenario "Project with a module sheet": the keys in every schematic section and in no other."""
    assert write_prjpcb(schematic="a.SchDoc", sheets=("a_x.SchDoc",), pcb="a.PcbDoc") == (
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\n" + SHEET_KEYS + b"\r\n"
        b"[Document2]\r\nDocumentPath=a_x.SchDoc\r\n" + SHEET_KEYS + b"\r\n"
        b"[Document3]\r\nDocumentPath=a.PcbDoc\r\n"
    )


def test_class_keys_and_section_together() -> None:
    data = write_prjpcb(
        schematic="d.SchDoc",
        pcb="d.PcbDoc",
        libraries=("L.SchLib",),
        sheets=("d_a.SchDoc", "d_b.SchDoc"),
        harnesses=("d_a.Harness",),
        net_classes=True,
    )
    assert data.count(SHEET_KEYS) == 3 and data.endswith(CLASS_SECTION)
    sections = data.decode("ascii").split("\r\n\r\n")
    assert [s.split("\r\n")[0] for s in sections] == [
        "[Design]",
        *(f"[Document{n}]" for n in range(1, 7)),
        "[PrjClassGen]",
    ]
    for section in sections[1:7]:
        lines = section.rstrip("\r\n").split("\r\n")
        assert (len(lines) == 5) == lines[1].endswith(".SchDoc")
    assert SHEET_CLASS_KEYS[1] == ("ClassGenCCAutoRoomEnabled", "0")
    assert dict(CLASS_GENERATION)["NetClassManualEnabled"] == "1" and len(CLASS_GENERATION) == 7


def test_unchanged_without_classes_and_sheets() -> None:
    """Scenario "Unchanged without classes and sheets"."""
    assert write_prjpcb(schematic="altium_sample.SchDoc", libraries=("FenoliteSample.SchLib",)) == (
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=altium_sample.SchDoc\r\n\r\n"
        b"[Document2]\r\nDocumentPath=FenoliteSample.SchLib\r\n"
    )
    plain = write_prjpcb(schematic="x.SchDoc", libraries=("x.SchLib",))
    assert b"ClassGen" not in plain
    assert plain == write_prjpcb(schematic="x.SchDoc", libraries=("x.SchLib",), net_classes=False)


def test_flat_project_with_a_pcb_document_has_the_class_keys() -> None:
    """Scenario "Flat project with a PCB document": the single sheet turns its room off too, because the
    change order of a flat build proposed a room without the key (report of Part E)."""
    assert write_prjpcb(schematic="x.SchDoc", pcb="x.PcbDoc") == (
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=x.SchDoc\r\n" + SHEET_KEYS + b"\r\n"
        b"[Document2]\r\nDocumentPath=x.PcbDoc\r\n"
    )
