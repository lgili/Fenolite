# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project file read (capability altium-project-reader, "Project file read")."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.altium.prjpcb import write_prjpcb
from fenolite.backends.altium.read.project import (
    DOCUMENT_KINDS,
    HIERARCHY_MODES,
    ProjectDocument,
    document_kind,
    read_project,
)
from fenolite.core.errors import Issue

ROOT = Path(__file__).resolve().parents[5]
DATA = ROOT / "tests" / "data" / "altium"
UTF8 = DATA / "read" / "project_utf8.PrjPcb"
CRLF = DATA / "read" / "project_crlf.PrjPcb"


def _codes(issues: tuple[Issue, ...]) -> list[str]:
    return [issue.code for issue in issues]


# --- documents (task 3.1) -----------------------------------------------------------------------------


def test_documents_and_kinds() -> None:
    """Scenario "Documents and kinds"."""
    project = read_project(UTF8.read_bytes(), file="project_utf8.PrjPcb")
    assert [(d.index, d.path, d.kind) for d in project.documents] == [
        (1, "Top.SchDoc", "schematic"),
        (2, "Board.PcbDoc", "pcb"),
        (4, "Jobs\\Fab.OutJob", "output-job"),
        (7, "notes.txt", "other"),
    ]
    assert project.documents[2].posix == "Jobs/Fab.OutJob"
    assert [d.unique_id for d in project.documents] == ["AAAAAAAA", "BBBBBBBB", "", ""]
    assert _codes(project.issues).count("altium.project.document-kind-unknown") == 1
    unknown = next(i for i in project.issues if i.code == "altium.project.document-kind-unknown")
    assert unknown.severity == "info" and "document 7" in unknown.message and ".txt" in unknown.message


def test_documents_generated_by_section_name() -> None:
    project = read_project(UTF8.read_bytes())
    assert project.generated == (ProjectDocument(1, "Out\\report.html", "other"),)
    assert _codes(project.issues).count("altium.project.document-kind-unknown") == 1


def test_documents_kinds_without_case_and_repeated_sections() -> None:
    project = read_project(CRLF.read_bytes())
    assert [(d.index, d.kind) for d in project.documents] == [
        (1, "schematic"),
        (2, "schematic-library"),
        (3, "harness"),
        (3, "pcb-library"),
    ]
    assert project.documents[0].posix == "Sheets/Main.SchDoc"


def test_documents_without_a_path_are_skipped() -> None:
    project = read_project(
        b"[Design]\nVersion=1.0\n[Document1]\nDocumentUniqueId=X\n[Document2]\nDocumentPath=a.PcbDoc\n"
    )
    assert [(d.index, d.kind) for d in project.documents] == [(2, "pcb")]


@pytest.mark.parametrize(("suffix", "kind"), sorted(DOCUMENT_KINDS.items()))
def test_documents_kind_table(suffix: str, kind: str) -> None:
    assert document_kind(f"a\\b{suffix}") == kind
    assert document_kind(f"b{suffix.upper()}") == kind
    assert document_kind(f"b{suffix.lower()}") == kind


def test_documents_other_kinds() -> None:
    assert document_kind("README") == "other"
    assert document_kind("x.PrjPcbStructure") == "other"
    assert document_kind("dir.SchDoc\\x") == "other"


# --- options and parameters (task 3.2) ----------------------------------------------------------------


def test_options_and_parameters() -> None:
    """Scenario "Options and parameters"."""
    project = read_project(UTF8.read_bytes())
    options = project.options
    assert project.version == "1.0"
    assert options.hierarchy_mode == 0 and options.net_scope == "automatic"
    assert options.allow_port_net_names is False and options.allow_sheet_entry_net_names is True
    assert options.append_sheet_number_to_local_nets is False
    assert options.power_port_names_take_priority is True
    assert options.output_path == "Out\\"
    assert ("PlaceholderOption", "7") in options.raw and options.raw[0] == ("Version", "1.0")
    assert [(p.index, p.name, p.value) for p in project.parameters] == [(1, "rev", "B"), (2, "title", "")]
    assert "altium.project.hierarchy-mode-unknown" not in _codes(project.issues)


def test_unknown_hierarchy_mode() -> None:
    """Scenario "Unknown hierarchy mode"."""
    project = read_project(CRLF.read_bytes(), file="project_crlf.PrjPcb")
    assert project.options.hierarchy_mode == 9 and project.options.net_scope is None
    found = [i for i in project.issues if i.code == "altium.project.hierarchy-mode-unknown"]
    assert len(found) == 1 and found[0].severity == "warning" and "9" in found[0].message
    assert project.options.allow_port_net_names is None  # "yes" is neither 1 nor 0


def test_hierarchy_mode_that_is_not_a_number() -> None:
    project = read_project(b"[Design]\r\nHierarchyMode=x\r\n")
    assert project.options.hierarchy_mode is None and project.options.net_scope is None
    assert _codes(project.issues) == ["altium.project.hierarchy-mode-unknown"]


def test_no_design_section() -> None:
    project = read_project(b"[Document1]\nDocumentPath=a.SchDoc\n", file="n.PrjPcb")
    assert project.version is None and project.options.hierarchy_mode is None
    assert project.options.raw == () and project.options.allow_port_net_names is None
    assert [(i.code, i.severity) for i in project.issues] == [("altium.project.no-design-section", "warning")]
    assert [d.path for d in project.documents] == ["a.SchDoc"]


def test_other_sections_stay_raw() -> None:
    project = read_project(CRLF.read_bytes())
    group = project.ini.section("OutputGroup1")
    assert group is not None and group.get("Name") == "Group"
    zeta = read_project(UTF8.read_bytes()).ini.section("Zeta Options")
    assert zeta is not None and zeta.keys() == ("B", "A")


def test_hierarchy_table_holds_only_stated_numbers() -> None:
    assert HIERARCHY_MODES == {0: "automatic"}


def test_bytes_come_back() -> None:
    for path in (UTF8, CRLF):
        data = path.read_bytes()
        assert read_project(data).to_bytes() == data


# --- Fenolite's own project files (task 3.3) ----------------------------------------------------------


def test_own_project_file() -> None:
    """Scenario "Fenolite's own project file"."""
    data = write_prjpcb(schematic="a.SchDoc", pcb="a.PcbDoc", libraries=("a.SchLib",))
    project = read_project(data)
    assert [(d.path, d.kind) for d in project.documents] == [
        ("a.SchDoc", "schematic"),
        ("a.PcbDoc", "pcb"),
        ("a.SchLib", "schematic-library"),
    ]
    assert project.version == "1.0" and project.options.hierarchy_mode is None
    assert project.options.net_scope is None and project.issues == ()
    assert project.to_bytes() == data


def test_own_project_file_with_sheets_harnesses_and_classes() -> None:
    data = write_prjpcb(
        schematic="top.SchDoc",
        pcb="top.PcbDoc",
        libraries=("top.PcbLib", "top.SchLib"),
        sheets=("led.SchDoc",),
        harnesses=("top.Harness",),
        net_classes=True,
    )
    project = read_project(data)
    assert [d.kind for d in project.documents] == [
        "schematic",
        "schematic",
        "pcb",
        "pcb-library",
        "schematic-library",
        "harness",
    ]
    assert [d.index for d in project.documents] == [1, 2, 3, 4, 5, 6]
    assert project.ini.section("PrjClassGen") is not None and project.issues == ()
    assert project.to_bytes() == data


OWN_SAMPLES = sorted(DATA.rglob("*.PrjPcb"))


@pytest.mark.parametrize("path", [p for p in OWN_SAMPLES if "read" not in p.parts], ids=lambda p: p.name)
def test_own_committed_samples(path: Path) -> None:
    data = path.read_bytes()
    project = read_project(data, file=path.name)
    assert project.to_bytes() == data
    assert project.issues == ()
    assert project.documents and project.documents[0].kind == "schematic"
    assert all(d.kind != "other" for d in project.documents)
