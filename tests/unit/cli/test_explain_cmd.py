# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite explain`` and its table (capability cli-contract, "Explain command"; change c0066)."""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest
from _checkcli import run

import fenolite
from fenolite.cli import explain
from fenolite.cli.errors import REGISTRY

SRC = Path(fenolite.__file__).resolve().parent
CONTRACT = SRC.parents[1] / "docs" / "cli-contract.md"


def _tables_in_source() -> set[tuple[str, str]]:
    """Every module-level name of ``src/fenolite`` that ends in ``ISSUE_CODES``."""
    found: set[tuple[str, str]] = set()
    for path in sorted(SRC.rglob("*.py")):
        module = ".".join(path.relative_to(SRC.parent).with_suffix("").parts)
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            targets = node.targets if isinstance(node, ast.Assign) else []
            if isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id.endswith("ISSUE_CODES"):
                    found.add((module, target.id))
    return found


def _headings() -> set[str]:
    page = CONTRACT.read_text(encoding="utf-8")
    return {m.group(1).strip().strip("`") for m in re.finditer(r"^## (.+)$", page, re.MULTILINE)}


def test_tables_name_every_issue_code_mapping() -> None:
    assert set(explain.TABLES) == _tables_in_source()
    assert list(explain.TABLES) == sorted(explain.TABLES)
    for module, name in explain.TABLES:
        assert getattr(importlib.import_module(module), name)


def test_tables_give_every_code_with_its_severities() -> None:
    codes = explain.all_codes()
    assert set(REGISTRY) <= set(codes) and codes["FEN-4001"] == ()
    assert codes["check.read-refused"] == ("error",)
    assert codes["copper.clearance"] == ("error", "warning")
    assert codes["kicad.drc.rules-not-loaded"] == ("error", "info")
    assert codes["kicad.drc.*"] == ("error", "warning", "info")
    assert not [code for code in codes if "<" in code]
    assert codes["zone.fill-stale"] == ("warning",)  # named by three tables


def test_table_is_complete() -> None:
    codes, entries = explain.all_codes(), explain.entries()
    assert sorted(set(codes) - set(entries)) == [], "codes without an entry in explain.toml"
    assert sorted(set(entries) - set(codes)) == [], "entries whose code is in no table"
    headings = _headings()
    for code, entry in entries.items():
        assert set(entry) == {"meaning", "fix", "see"}, code
        for key in ("meaning", "fix"):
            assert 0 < len(entry[key]) <= 400 and entry[key] == entry[key].strip(), (code, key)
        assert entry["see"] in headings, (code, entry["see"])


def test_family_and_unknown_codes() -> None:
    own = explain.explain("kicad.drc.rules-not-loaded")
    assert own is not None and own.family == "" and own.kind == "issue"
    family = explain.explain("kicad.drc.clearance")
    assert family is not None and family.family == "kicad.drc.*" and family.see == "check"
    assert explain.explain("kicad.drc.*") == explain.Explanation(
        "kicad.drc.*", "issue", family.meaning, family.fix, "check", "kicad.drc.*"
    )
    assert explain.explain("check.read-refuse") is None and explain.explain("kicad.drc") is None
    error = explain.explain("FEN-4001")
    assert error is not None and error.kind == "error" and "--confirm" in error.fix


def test_an_error_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "explain", "FEN-4001")
    result = env["result"]
    assert code == 0 and result["kind"] == "error" and result["exit_code"] == 4
    assert "--confirm" in result["fix"] and result["see"] == "Writing files"
    assert set(result) == {"code", "kind", "exit_code", "severities", "meaning", "fix", "see", "family"}
    assert result["severities"] == [] and result["family"] is None
    assert env["input"] is None and env["issues"] == []


def test_an_issue_code_of_a_family(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "explain", "kicad.drc.clearance")
    result = env["result"]
    assert code == 0 and result["kind"] == "issue" and result["family"] == "kicad.drc.*"
    assert result["exit_code"] is None and result["severities"] == ["error", "warning", "info"]
    code, env, _, _ = run(monkeypatch, tmp_path, "explain", "copper.clearance")
    assert env["result"]["family"] is None and env["result"]["severities"] == ["error", "warning"]


def test_unknown_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err, _ = run(monkeypatch, tmp_path, "explain", "check.read-refuse")
    assert code == 2 and err["code"] == "FEN-2001" and env["ok"] is False
    assert "check.read-refused" in err["hint"]
    code, _, err, _ = run(monkeypatch, tmp_path, "explain", "zzz")
    assert code == 2 and "fenolite capabilities" in err["hint"]


def test_every_code_is_explained_by_the_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in ("fmt.would-change", "roundtrip.failed", "FEN-1001", "place.locked"):
        code, env, _, _ = run(monkeypatch, tmp_path, "explain", name)
        assert code == 0 and env["result"]["code"] == name and env["result"]["meaning"]
