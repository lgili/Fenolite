# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite fmt`` (capability cli-contract, "Fmt command"; change c0066). Hermetic."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from _checkcli import run
from _cliexamples import folder_snapshot

from fenolite.backends.kicad import sexpr
from fenolite.backends.kicad.sexpr import Atom, Node, canonical, parse, tree_equal

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
PROJECT = DATA / "kicad" / "project" / "empty_10.kicad_pro"
FILES = [
    TWO_LAYER,
    DATA / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod",
    DATA / "libs" / "Mini.kicad_sym",
    DATA / "kicad" / "sheets" / "all_items.kicad_wks",
    DATA / "kicad" / "tokens" / "old" / "old.kicad_sch",
]


def _canonical_copy(tmp_path: Path) -> tuple[Path, str]:
    text = canonical(TWO_LAYER.read_text(encoding="utf-8"))
    target = tmp_path / "board.kicad_pcb"
    target.write_bytes(text.encode("utf-8"))
    return target, text


def test_canonical_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target, text = _canonical_copy(tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "fmt", str(target), "--check")
    assert code == 0 and env["issues"] == []
    assert env["result"] == {
        "kind": "kicad_pcb",
        "formatted": True,
        "lines": len(text.splitlines()),
        "first_difference": None,
    }
    assert (
        env["evidence"]["hypotheses"] == ["H-K-FMT-IDEMPOTENT"] and env["input"]["path"] == "board.kicad_pcb"
    )


def test_file_that_would_change_then_formatting_twice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target, text = _canonical_copy(tmp_path)
    loose = text.replace("(kicad_pcb\n", "(kicad_pcb  \n", 1)
    target.write_bytes(loose.encode("utf-8"))
    before = folder_snapshot(tmp_path)

    code, env, err, _ = run(monkeypatch, tmp_path, "fmt", "board.kicad_pcb", "--check")
    assert code == 5 and err["code"] == "FEN-5001" and env["result"]["formatted"] is False
    assert [(i["code"], i["severity"], i["where"]) for i in env["issues"]] == [
        ("fmt.would-change", "error", "board.kicad_pcb:1")
    ]
    assert env["result"]["first_difference"] == 1 and "plan" not in env["result"]
    assert folder_snapshot(tmp_path) == before
    # --check plans nothing, so it never asks for a confirmation and never writes with one
    assert run(monkeypatch, tmp_path, "fmt", "board.kicad_pcb", "--check", "--confirm")[0] == 5
    assert folder_snapshot(tmp_path) == before

    code, env, err, _ = run(monkeypatch, tmp_path, "fmt", "board.kicad_pcb")
    assert code == 4 and err["code"] == "FEN-4001" and folder_snapshot(tmp_path) == before
    assert [(p["path"], p["kind"], p["overwrite"]) for p in env["result"]["plan"]] == [
        ("board.kicad_pcb", "kicad_pcb", True)
    ]

    code, env, _, _ = run(monkeypatch, tmp_path, "fmt", "board.kicad_pcb", "--confirm")
    assert code == 0 and env["result"]["formatted"] is False
    assert target.read_bytes() == text.encode("utf-8")
    assert (tmp_path / "board.kicad_pcb.bak").read_bytes() == loose.encode("utf-8")
    assert env["receipt"]["backup"] == ["board.kicad_pcb.bak"]
    assert tree_equal(parse(target.read_text(encoding="utf-8")), parse(loose))

    code, env, _, _ = run(monkeypatch, tmp_path, "fmt", "board.kicad_pcb", "--confirm")
    assert code == 0 and env["result"]["formatted"] is True
    assert env["receipt"] is None and "plan" not in env["result"]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.suffix[1:])
def test_every_kind_is_formatted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    target = tmp_path / path.name
    target.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    code, env, _, _ = run(monkeypatch, tmp_path, "fmt", path.name, "--confirm")
    assert code == 0 and env["result"]["kind"] == path.suffix[1:], env
    assert target.read_bytes() == canonical(text).encode("utf-8")
    assert run(monkeypatch, tmp_path, "fmt", path.name, "--check")[0] == 0


def test_refused_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", str(PROJECT), "--check")
    assert code == 2 and err["code"] == "FEN-2001" and "byte for byte" in err["hint"]
    rules = tmp_path / "x.kicad_dru"
    rules.write_text("(version 1)\n", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", str(rules), "--check")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", "missing.kicad_pcb", "--check")
    assert code == 3 and err["code"] == "FEN-3001"
    unbalanced = DATA / "kicad" / "sexpr" / "mirror" / "unbalanced.kicad_pcb"
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", str(unbalanced), "--check")
    assert code == 3 and err["code"] == "FEN-3004"


def test_comments_below_the_root_are_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target, _ = _canonical_copy(tmp_path)
    nested = Node(Atom.symbol("kicad_pcb"), (replace(parse("(b 1)"), comments=("# x",)),))
    monkeypatch.setattr("fenolite.cli.cmd_fmt.parse_bytes", lambda data, file="": nested)
    before = folder_snapshot(tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "fmt", str(target), "--confirm")
    assert code == 7 and err["code"] == "FEN-7001" and folder_snapshot(tmp_path) == before
    assert sexpr.first_line_difference("a", "a") is None
