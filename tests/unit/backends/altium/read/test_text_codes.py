# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed set of issue codes of the text readers (capability altium-project-reader, "Text reader issue
codes", scenario "Closed set")."""

from __future__ import annotations

import re
from pathlib import Path

from fenolite.backends.altium.read.ini import parse_ini
from fenolite.backends.altium.read.outjob import read_outjob
from fenolite.backends.altium.read.project import load_project, read_project
from fenolite.backends.altium.read.rul import read_rule_file
from fenolite.backends.altium.read.rules import map_rules
from fenolite.backends.altium.read.stackup import read_stackup
from fenolite.backends.altium.read.textfile import TEXT_READ_CODES, split_text
from fenolite.core.errors import Issue

READ = Path(__file__).resolve().parents[5] / "src" / "fenolite" / "backends" / "altium" / "read"
TEXT_MODULES = ("textfile", "ini", "proptext", "project", "outjob", "rul", "rules", "scope", "stackup")
LITERAL = re.compile(r"[\"'](altium\.(?:text|project|outjob|rule|stackup)\.[a-z0-9-]+)[\"']")


def test_literals_equal_the_table() -> None:
    literals: set[str] = set()
    for name in TEXT_MODULES:
        literals |= set(LITERAL.findall((READ / f"{name}.py").read_text(encoding="utf-8")))
    assert literals == set(TEXT_READ_CODES)


def test_no_error_severity() -> None:
    assert set(TEXT_READ_CODES.values()) <= {"warning", "info"}


def _every_issue(tmp_path: Path) -> list[Issue]:
    issues: list[Issue] = []
    split_text(b"a\r\nb\n\xe9", issues=issues)
    issues += parse_ini(b"[S]\nk=1\nk=2\nstray\n").issues
    issues += read_project(b"[Design]\nHierarchyMode=7\n[Document1]\nDocumentPath=x.txt\n").issues
    issues += read_project(b"[Document1]\nDocumentPath=a.SchDoc\n").issues
    issues += read_outjob(b"[OutputJobFile]\n[OutputGroup1]\nOutputName1=x\n").issues
    issues += read_rule_file(b"RULEKIND=Width|NAME=a\nNAME=b\n").issues
    issues += map_rules([[("RuleKind", "Width")]], origin="o", summary=True).issues
    issues += read_stackup(b"|STACKUPVERSION=1|LAYER_V7_0COPTHICK=x|LAYER_V8_0COPTHICK=y").issues
    (tmp_path / "bad.RUL").write_bytes(b"hello")
    project = tmp_path / "p.PrjPcb"
    project.write_bytes(b"[Design]\n[Document1]\nDocumentPath=gone.SchDoc\n[Document2]\nDocumentPath=..\\x.RUL\n"
                        b"[Document3]\nDocumentPath=bad.RUL\n")  # fmt: skip
    issues += load_project(project).issues
    return issues


def test_produced_codes_are_in_the_table(tmp_path: Path) -> None:
    issues = _every_issue(tmp_path)
    assert {issue.code for issue in issues} == set(TEXT_READ_CODES)
    for issue in issues:
        assert issue.severity == TEXT_READ_CODES[issue.code], issue.code
