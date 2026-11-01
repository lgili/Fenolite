# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Adopted boards (capability layout-lens, "Adopted boards"; change c0275): the source board stamped with
the identities a build of the emitted code derives, so a build over it matches every footprint and changes
nothing. The source here is the authored board as another tool would hold it (``foreign``): no
``fenolite.path``, and uuids no build derives."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest
from _importcode import PROJECT, STAMP, foreign, imported

from fenolite.api import read_board, run
from fenolite.checks.equivalence import compare_designs

UUID = re.compile(r'\(uuid "[0-9a-f-]{36}"\)')
PATH_BLOCK = re.compile(r'\n\t+\(property "fenolite\.path" "[^"]*"(?:\n\t\t\t.*)*?\n\t\t\)', re.MULTILINE)


def _adopted(tmp_path: Path) -> tuple[Path, Path]:
    source = foreign(tmp_path)
    reply = imported(tmp_path, source, "--adopt", "--confirm")
    assert reply.exit_code == 0, reply.error
    adopted = reply.result["adopted"]
    assert adopted["board"] == "adopted/foreign.kicad_pcb" and adopted["unmatched"] == {}
    assert adopted["paths"] == 5 and adopted["rewritten"]["footprint"] == 5
    return source, tmp_path / "out"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_build_over_an_adopted_board_changes_nothing(tmp_path: Path) -> None:
    _, out = _adopted(tmp_path)
    first = run("build", "design.py", "--out", "adopted", "--confirm", cwd=out, timestamp=STAMP)
    assert first.exit_code == 0, first.error
    kept = first.result["preserved"]
    assert kept["board"] is True and sorted(kept["kept"]) == ["D101", "D201", "J1", "R101", "R201"]
    assert kept["orphans"] == [] and kept["board_only"] == [] and kept["replaced"] == []
    codes = {i["code"] for i in (first.envelope or {})["issues"]}
    assert not codes & {"kicad.copper.regenerated", "kicad.copper.stale"}
    board = out / "adopted" / "foreign.kicad_pcb"
    once = _digest(board)
    second = run("build", "design.py", "--out", "adopted", "--confirm", cwd=out, timestamp=STAMP)
    assert second.exit_code == 0, second.error
    assert _digest(board) == once


def test_only_identities_change(tmp_path: Path) -> None:
    source, out = _adopted(tmp_path)
    adopted = out / "adopted" / "foreign.kicad_pcb"
    a, b = read_board(source).design, read_board(adopted).design
    report = compare_designs(a, b, level=5)
    assert [d for level in report.levels for d in level.differences] == []
    plain = UUID.sub("(uuid U)", source.read_text(encoding="utf-8"))
    stamped = UUID.sub("(uuid U)", PATH_BLOCK.sub("", adopted.read_text(encoding="utf-8")))
    assert plain == stamped
    assert adopted.read_text(encoding="utf-8").count('(property "fenolite.path"') == 5
    assert (out / "adopted" / "foreign.kicad_pro").exists() is False


def test_adopt_needs_the_self_check(tmp_path: Path) -> None:
    reply = imported(tmp_path, PROJECT, "--adopt", "--no-verify")
    assert reply.exit_code == 2
    assert reply.error is not None and reply.error["code"] == "FEN-2001"


@pytest.mark.parametrize("folder", ["two_sheet"])
def test_adopted_project_file_is_copied(tmp_path: Path, folder: str) -> None:
    reply = imported(tmp_path, PROJECT, "--adopt", "--confirm")
    assert reply.exit_code == 0, reply.error
    assert (tmp_path / "out" / "adopted" / "two_sheet.kicad_pro").read_bytes() == PROJECT.read_bytes()
