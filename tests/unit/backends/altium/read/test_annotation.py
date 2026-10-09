# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The annotation file (capability altium-project-reader, "Annotation file read"; change c0083, task 2.1).

The form of a real annotation file is ``UNKNOWN`` (``docs/formats/altium/project.md``, "The annotation
file"): these cases hold the reader to the form it assumes, ``<unique-id path>=<designator>``, and to the
bytes it keeps. Part R, step R4, settles ``H-A-IMP-RPT-ANNOT``."""

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
