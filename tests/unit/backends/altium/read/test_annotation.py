# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The annotation file (capability altium-project-reader, "Annotation file read"; change c0083, task 2.1).

Legacy authored flat maps and the native indexed form measured in S-0737 are
read without changing their bytes. Incomplete rows and unknown metadata remain
located information findings."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.altium.read.annotation import read_annotation
from fenolite.backends.altium.read.project import load_project
from fenolite.core.errors import FormatError

SAMPLE = Path(__file__).resolve().parents[4] / "data" / "altium" / "channels" / "two" / "two.Annotation"


def test_authored_annotation_file() -> None:
    """Scenario "Authored annotation file"."""
    data = SAMPLE.read_bytes()
    read = read_annotation(data, file="two.Annotation")
    assert [(entry.path, entry.designator) for entry in read.entries] == [
        ("\\UTOP0001", "U101"),
        ("\\JTOP0001", "J101"),
    ]
    assert read.to_bytes() == data and read.issues == ()
    assert read.designators() == {"\\UTOP0001": "U101", "\\JTOP0001": "J101"}


def test_empty_file_has_no_entry() -> None:
    """The one public annotation file is empty (0 bytes): it gives nothing."""
    read = read_annotation(b"", file="p.Annotation")
    assert read.entries == () and read.issues == () and read.to_bytes() == b""


def test_other_lines_are_kept_and_reported() -> None:
    data = b"\xef\xbb\xbf[Head]\r\nVersion=2\r\n\r\n[Map]\r\n\\SYMBOL01\\RUID0001=R7\r\n\\AB\\CD=\r\nnote\r\n"
    read = read_annotation(data, file="p.Annotation")
    assert read.to_bytes() == data
    assert [(entry.path, entry.designator, entry.section, entry.line) for entry in read.entries] == [
        ("\\SYMBOL01\\RUID0001", "R7", "Map", 5)
    ]
    codes = [(issue.code, issue.severity, issue.where) for issue in read.issues]
    assert codes == [
        ("altium.text.stray-line", "info", "p.Annotation:7"),
        ("altium.text.unknown-key", "info", "p.Annotation:2"),
        ("altium.text.unknown-key", "info", "p.Annotation:6"),
    ]


def test_first_entry_of_a_path_wins() -> None:
    read = read_annotation(b"\\A\\B=R1\n\\A\\B=R2\n")
    assert read.designators() == {"\\A\\B": "R1"}


@pytest.mark.parametrize("data", [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(504), b"\\A=R1\x00\n"])
def test_not_text_raises(data: bytes) -> None:
    with pytest.raises(FormatError):
        read_annotation(data, file="p.Annotation")


def test_load_project_returns_the_annotation_file(tmp_path: Path) -> None:
    (tmp_path / "p.Annotation").write_bytes(b"\\SYMBOL01\\RUID0001=R1_A\r\n")
    (tmp_path / "p.PrjPcb").write_bytes(
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=p.Annotation\r\n"
    )
    project = load_project(tmp_path / "p.PrjPcb")
    ((index, annotation),) = project.annotations
    assert index == 1 and [entry.designator for entry in annotation.entries] == ["R1_A"]
    assert project.annotation_designators() == {"\\SYMBOL01\\RUID0001": "R1_A"}
    assert project.issues == ()


def test_project_without_annotation_file(tmp_path: Path) -> None:
    (tmp_path / "p.PrjPcb").write_bytes(b"[Design]\r\nVersion=1.0\r\n")
    project = load_project(tmp_path / "p.PrjPcb")
    assert project.annotations == () and project.annotation_designators() == {}


def test_native_indexed_annotation_retains_bytes_and_metadata() -> None:
    """Native field facts S-0737, authored independently of native saved bytes."""
    data = (
        b"\xef\xbb\xbf[DesignatorManager]\r\nLogicalDesignator0=R4\r\nLogicalPartID0=1\r\n"
        b"DocumentName0=unit_child.SchDoc\r\nChannelName0=UNIT2\r\n"
        b"UniqueID0=\\2PARENT01\\RES00001\r\nPhysicalDesignator0=R42\r\n"
        b"PhysicalDesignatorLocked0=1\r\n\r\n[SheetNumberManager]\r\n"
        b"SheetNumberOrder=Display Order\r\nSheetNumberMethod=Increasing\r\n"
    )
    read = read_annotation(data, file="unit.Annotation")
    assert read.to_bytes() == data and read.issues == ()
    assert [(entry.path, entry.designator, entry.section, entry.line) for entry in read.entries] == [
        ("\\2PARENT01\\RES00001", "R42", "DesignatorManager", 6)
    ]


def test_native_sparse_indexes_and_reversed_keys() -> None:
    data = (
        b"[DesignatorManager]\nPhysicalDesignator7=C87\nUniqueID7=\\PARTC008\n"
        b"UniqueID0=\\PARTR009\nPhysicalDesignator0=R90\n"
    )
    read = read_annotation(data)
    assert read.designators() == {"\\PARTC008": "C87", "\\PARTR009": "R90"}
    assert [entry.line for entry in read.entries] == [3, 4]
    assert read.to_bytes() == data and read.issues == ()


@pytest.mark.parametrize(
    "record",
    [
        b"UniqueID0=\\PARTA001\n",
        b"PhysicalDesignator0=R7\n",
        b"UniqueID0=\\PARTA001\nPhysicalDesignator0=\n",
        b"UniqueID0=not-a-uid-path\nPhysicalDesignator0=R7\n",
        b"UniqueID0=\\PARTA001\nPhysicalDesignator1=R7\n",
    ],
)
def test_native_incomplete_or_invalid_records_do_not_invent_mappings(record: bytes) -> None:
    data = b"[DesignatorManager]\n" + record
    read = read_annotation(data, file="unit.Annotation")
    assert read.entries == () and read.to_bytes() == data
    assert len(read.issues) == len(record.splitlines())
    assert all(issue.code == "altium.text.unknown-key" for issue in read.issues)
    assert all(issue.where.startswith("unit.Annotation:") for issue in read.issues)


def test_native_keys_in_another_section_are_unknown() -> None:
    data = b"[Other]\nUniqueID0=\\PARTA001\nPhysicalDesignator0=R7\n"
    read = read_annotation(data)
    assert read.entries == () and read.to_bytes() == data
    assert [issue.code for issue in read.issues] == ["altium.text.unknown-key"] * 2


def test_native_duplicate_paths_and_unknown_metadata_preserve_first_mapping() -> None:
    data = (
        b"[DesignatorManager]\nUniqueID2=\\PARTA001\nPhysicalDesignator2=R8\n"
        b"UniqueID6=\\PARTA001\nPhysicalDesignator6=R9\nFutureField2=kept\n"
        b"[Legacy]\n\\PARTA001=R10\n"
    )
    read = read_annotation(data, file="unit.Annotation")
    assert read.designators() == {"\\PARTA001": "R8"}
    assert [entry.designator for entry in read.entries] == ["R8", "R9", "R10"]
    assert read.to_bytes() == data
    assert [(issue.code, issue.where) for issue in read.issues] == [
        ("altium.text.unknown-key", "unit.Annotation:6")
    ]
