# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check --exclude`` without a tool (change c0209; capability kicad-oracle, "DRC exclusions
written"): the argument forms, the usage errors and the missing tool. The writes themselves are proved
against ``kicad-cli`` in ``tests/kicad/check/test_exclusions_write.py``."""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkcli import hide_kicad, run
from _projects import authored_project

from fenolite.backends.base import DrcItem, DrcViolation
from fenolite.cli._exclude import matches, parse_exclude
from fenolite.cli.errors import CliError
from fenolite.core.coords import Point


def entry(kind: str, *uuids: str) -> DrcViolation:
    return DrcViolation(kind, kind, "error", tuple(DrcItem(u, "item", Point(0, 0)) for u in uuids))


def test_parse_exclude() -> None:
    spec = parse_exclude("kicad.drc.unconnected-items:R1-1:R2-1")
    assert (spec.kind, spec.items, spec.text) == ("kicad.drc.unconnected-items", ("R1-1", "R2-1"), spec.text)
    assert parse_exclude("via_dangling:abc").items == ("abc",)
    for bad in ("clearance", "clearance::b", "a:b:c:d", ":a:b"):
        with pytest.raises(CliError) as caught:
            parse_exclude(bad)
        assert caught.value.code == "FEN-2001"


def test_matches_by_type_or_code_uuid_or_name_in_either_order() -> None:
    found = entry("unconnected_items", "AA", "bb")
    names = ("R1-1", "R2-1")
    assert matches(parse_exclude("unconnected_items:R2-1:R1-1"), found, names)
    assert matches(parse_exclude("kicad.drc.unconnected-items:aa:BB"), found, names)
    assert not matches(parse_exclude("clearance:aa:bb"), found, names)
    assert not matches(parse_exclude("unconnected_items:aa"), found, names)
    assert matches(parse_exclude("via_dangling:R3"), entry("via_dangling", "cc"), ("R3",))


@pytest.fixture
def board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    hide_kicad(monkeypatch, tmp_path)
    return authored_project(tmp_path, major=10) / "board.kicad_pcb"


@pytest.mark.parametrize(
    "args",
    [
        ("--reason", "x"),
        ("--exclude", "clearance:a:b"),
        ("--exclude", "clearance:a:b", "--reason", " "),
        ("--exclude", "clearance:a:b", "--reason", "x", "--stages", "drc.kicad"),
        ("--exclude", "clearance", "--reason", "x"),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, board: Path, args: tuple[str, ...]) -> None:
    before = sorted(p.name for p in board.parent.iterdir())
    code, _, error, _ = run(monkeypatch, board.parent, "check", str(board), *args, "--confirm")
    assert code == 2 and error["code"] == "FEN-2001"
    assert sorted(p.name for p in board.parent.iterdir()) == before


def test_without_kicad_cli_exits_6(monkeypatch: pytest.MonkeyPatch, board: Path) -> None:
    project = board.with_suffix(".kicad_pro")
    before = project.read_bytes() if project.exists() else None
    code, _, error, _ = run(monkeypatch, board.parent, "check", str(board), "--exclude", "clearance:a:b",
                            "--reason", "x", "--confirm")  # fmt: skip
    assert code == 6 and error["code"].startswith("FEN-600")
    assert (project.read_bytes() if project.exists() else None) == before


def test_without_exclude_check_plans_nothing(monkeypatch: pytest.MonkeyPatch, board: Path) -> None:
    for protocol in ((), ("--dry-run",), ("--confirm",)):
        args = ("check", str(board), "--stages", "model.validate", *protocol)
        code, envelope, _, _ = run(monkeypatch, board.parent, *args)
        assert code == 0 and "plan" not in envelope["result"] and envelope["receipt"] is None
