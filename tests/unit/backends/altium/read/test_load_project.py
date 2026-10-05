# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project loading (capability altium-project-reader, "Project loading")."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from fenolite.backends.altium.read.project import load_project
from fenolite.core.errors import FormatError

DATA = Path(__file__).resolve().parents[4] / "data" / "altium" / "read"


def _project(folder: Path, *paths: str, head: str = "[Design]\r\nVersion=1.0\r\n") -> Path:
    sections = "".join(f"\r\n[Document{i}]\r\nDocumentPath={p}\r\n" for i, p in enumerate(paths, start=1))
    target = folder / "p.PrjPcb"
    target.write_bytes((head + sections).encode("latin-1"))
    return target


def _tree(folder: Path) -> list[tuple[str, int]]:
    return sorted((str(p.relative_to(folder)), p.stat().st_size) for p in folder.rglob("*"))


def test_project_with_companions() -> None:
    """Scenario "Project with companions"."""
    before = _tree(DATA)
    loaded = load_project(DATA / "project_companions.PrjPcb")
    assert loaded.root == DATA and loaded.name == "project_companions"
    assert [(i, job.version) for i, job in loaded.outjobs] == [(2, "1.0")]
    assert [(i, rules.kind) for i, rules in loaded.rule_files] == [(3, "export")]
    assert [(i, len(stack.layers)) for i, stack in loaded.stackups] == [(4, 3)]
    assert [(i, [r.kind for r in m.ruleset.rules]) for i, m in loaded.rules] == [
        (3, ["clearance", "track_width"])
    ]
    first = loaded.documents[0]
    assert first.present is False and first.file == DATA / "Top.SchDoc"
    assert [d.present for d in loaded.documents] == [False, True, True, True]
    assert [i.code for i in loaded.issues] == ["altium.project.document-missing"]
    assert "document 1" in loaded.issues[0].message
    assert _tree(DATA) == before  # nothing written


def test_path_outside_the_project_folder(tmp_path: Path) -> None:
    """Scenario "Path outside the project folder"."""
    folder = tmp_path / "a" / "b" / "project"
    folder.mkdir(parents=True)
    shared = tmp_path / "a" / "shared"
    shared.mkdir()
    (shared / "Fab.OutJob").write_bytes(b"not an output job\n")  # would be unreadable if opened
    target = _project(folder, "Top.SchDoc", "..\\..\\shared\\Fab.OutJob")
    (folder / "Top.SchDoc").write_bytes(b"x")
    loaded = load_project(target)
    second = loaded.documents[1]
    assert second.file is None and second.present is False and loaded.outjobs == ()
    outside = [i for i in loaded.issues if i.code == "altium.project.document-outside"]
    assert len(outside) == 1 and "document 2" in outside[0].message and "shared" not in outside[0].message
    assert [i.code for i in loaded.issues] == ["altium.project.document-outside"]


@pytest.mark.parametrize(
    "path",
    [
        "C:\\boards\\Fab.OutJob",
        "\\\\server\\share\\Fab.OutJob",
        "/abs/Fab.OutJob",
        "..\\Fab.OutJob",
        "a\\..\\..\\x.RUL",
    ],
)
def test_paths_that_leave_the_folder(tmp_path: Path, path: str) -> None:
    loaded = load_project(_project(tmp_path, path))
    assert loaded.documents[0].file is None
    assert [i.code for i in loaded.issues] == ["altium.project.document-outside"]
    assert path not in loaded.issues[0].message


def test_inner_dot_dot_stays_inside(tmp_path: Path) -> None:
    (tmp_path / "jobs").mkdir()
    shutil.copy(DATA / "jobs.OutJob", tmp_path / "jobs" / "jobs.OutJob")
    loaded = load_project(_project(tmp_path, "sub\\..\\jobs\\jobs.OutJob"))
    assert loaded.documents[0].present and [i for i, _ in loaded.outjobs] == [1]


def test_symlink_that_leaves_the_folder(tmp_path: Path) -> None:
    folder = tmp_path / "project"
    folder.mkdir()
    shutil.copy(DATA / "jobs.OutJob", tmp_path / "jobs.OutJob")
    try:
        os.symlink(tmp_path / "jobs.OutJob", folder / "jobs.OutJob")
    except OSError:
        pytest.skip("symbolic links are not available")
    loaded = load_project(_project(folder, "jobs.OutJob"))
    assert loaded.documents[0].file is None and loaded.outjobs == ()
    assert [i.code for i in loaded.issues] == ["altium.project.document-outside"]


def test_unreadable_companion(tmp_path: Path) -> None:
    """Scenario "Unreadable companion"."""
    (tmp_path / "bad.RUL").write_bytes(b"hello")
    loaded = load_project(_project(tmp_path, "bad.RUL"))
    assert loaded.rule_files == () and loaded.rules == ()
    assert loaded.documents[0].present is True
    assert [(i.code, i.severity) for i in loaded.issues] == [
        ("altium.project.companion-unreadable", "warning")
    ]
    assert "document 1" in loaded.issues[0].message and str(tmp_path) not in loaded.issues[0].message


def test_case_insensitive_fallback(tmp_path: Path) -> None:
    (tmp_path / "Rules").mkdir()
    shutil.copy(DATA / "rules_summary.RUL", tmp_path / "Rules" / "out.RUL")
    shutil.copy(DATA / "two_layer.stackup", tmp_path / "Two_Layer.STACKUP")
    loaded = load_project(_project(tmp_path, "RULES\\OUT.rul", "two_layer.stackup"))
    assert [d.present for d in loaded.documents] == [True, True]
    assert [i for i, _ in loaded.rule_files] == [1] and [i for i, _ in loaded.stackups] == [2]
    ((_, mapping),) = loaded.rules
    assert [u.reason for u in mapping.unmapped] == ["summary-form"] * 3
    assert loaded.issues == ()


def test_ambiguous_case_is_missing(tmp_path: Path) -> None:
    (tmp_path / "a.RUL").write_bytes(b"x")
    if (tmp_path / "A.RUL").exists():
        pytest.skip("the file system ignores case")
    (tmp_path / "A.RUL").write_bytes(b"y")
    loaded = load_project(_project(tmp_path, "a.rul"))
    assert loaded.documents[0].present is False
    assert [i.code for i in loaded.issues] == ["altium.project.document-missing"]


def test_issue_order(tmp_path: Path) -> None:
    """The issues of the project file first, then those of each document in document order."""
    shutil.copy(DATA / "jobs.OutJob", tmp_path / "jobs.OutJob")
    (tmp_path / "s.stackup").write_bytes(b"|STACKUPVERSION=1|LAYER_V8_0NAME=A|LAYER_V8_0COPTHICK=x")
    (tmp_path / "w.RUL").write_bytes(b"RULEKIND=Width|NAME=W\xb6\n")
    target = _project(
        tmp_path,
        "missing.SchDoc",
        "w.RUL",
        "s.stackup",
        "jobs.OutJob",
        head="[Design]\r\nHierarchyMode=4\r\n",
    )
    loaded = load_project(target)
    assert [i.code for i in loaded.issues] == [
        "altium.project.hierarchy-mode-unknown",
        "altium.project.document-missing",
        "altium.text.encoding-assumed",
        "altium.stackup.length-unreadable",
    ]
    ((_, mapping),) = loaded.rules
    assert [u.reason for u in mapping.unmapped] == ["malformed"]  # no PRIORITY
    assert all(i.code != "altium.rule.unmapped" for i in loaded.issues)


def test_other_kinds_are_listed_not_opened(tmp_path: Path) -> None:
    for name in ("Top.SchDoc", "Board.PcbDoc", "Parts.SchLib", "Cable.Harness"):
        (tmp_path / name).write_bytes(b"\0\0not text")
    loaded = load_project(_project(tmp_path, "Top.SchDoc", "Board.PcbDoc", "Parts.SchLib", "Cable.Harness"))
    assert [d.present for d in loaded.documents] == [True] * 4
    assert loaded.issues == () and loaded.outjobs == loaded.rule_files == loaded.stackups == ()


def test_generated_documents_are_not_opened(tmp_path: Path) -> None:
    (tmp_path / "out.RUL").write_bytes(b"hello")
    target = tmp_path / "p.PrjPcb"
    target.write_bytes(b"[Design]\r\n\r\n[GeneratedDocument1]\r\nDocumentPath=out.RUL\r\n")
    loaded = load_project(target)
    assert loaded.documents == () and loaded.issues == () and loaded.rule_files == ()


def test_missing_and_unreadable_project(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_project(tmp_path / "none.PrjPcb")
    bad = tmp_path / "bad.PrjPcb"
    bad.write_bytes(b"[Design]\0")
    with pytest.raises(FormatError):
        load_project(bad)
