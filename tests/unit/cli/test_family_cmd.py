# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite family`` (change c0263; cli-contract, "Family command"; passive-families, "Encode", "Decode",
"Validity matrix", "Fields and code attributes", "Prefix-free fields")."""

from __future__ import annotations

import shutil
import socket
import subprocess
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.cli.api import discover

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ("--project", "examples/families")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("family started a subprocess or opened a socket")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(socket, "socket", refuse)


def test_registered_read_only() -> None:
    command = discover()["family"]
    assert not command.mutates and command.default_limit == 20


def test_list_and_show(monkeypatch: pytest.MonkeyPatch) -> None:
    code, env, err, _ = run(monkeypatch, ROOT, "family", "list", *PROJECT)
    assert code == 0, err
    assert [item["id"] for item in env["result"]["families"]] == [
        "Example:EX_CHIP_R", "Example:EX_MF_R", "Example:EX_MLCC"
    ]  # fmt: skip
    assert {item["errors"] for item in env["result"]["families"]} == {0}
    code, env, err, _ = run(monkeypatch, ROOT, "family", "show", "Example:EX_MLCC", *PROJECT)
    assert code == 0, err
    shown = env["result"]["family"]
    assert shown["pattern"] == "EX{size}{dielectric}{value}{tolerance}{voltage}{packing}"
    assert shown["fields"]["value"] == {"scheme": "eia3", "unit": "pF", "series": "E12"}
    assert shown["valid"][1]["value"] == {"min": "10pF", "max": "1nF"} and shown["combinations"] == 1568
    code, _, err, _ = run(monkeypatch, ROOT, "family", "show", "Example:NOPE", *PROJECT)
    assert code == 2 and err["code"] == "FEN-2001"


def test_a_query_gives_an_exact_mpn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A query gives an exact MPN"."""
    query = "capacitor(100nF, rating>=25V, case=0603, dielectric=X7R)"
    code, env, err, _ = run(monkeypatch, ROOT, "family", "encode", query, *PROJECT)
    assert code == 0, err
    first = env["result"]["candidates"][0]
    assert first["mpn"] == "EX03R104KAT" and first["device"] == "Example:EX_MLCC@EX03R104KAT"
    assert first["manufacturer"] == "Example Passive" and env["result"]["matches"] == 2
    code, env, _, _ = run(monkeypatch, ROOT, "family", "encode", "capacitor(3.3F)", *PROJECT)
    assert code == 5 and [item["code"] for item in env["issues"]] == ["pick.no-match"]


def test_an_excluded_combination(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "An excluded combination"."""
    code, env, err, _ = run(monkeypatch, ROOT, "family", "decode", "EX03R104KBT", *PROJECT)
    assert code == 0, err
    assert [item["in_matrix"] for item in env["result"]["decoded"]] == [False]
    assert [item["code"] for item in env["issues"]] == ["family.decode-outside-matrix"]


def test_a_decode_names_where_it_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A decode names where it failed"."""
    code, env, _, _ = run(monkeypatch, ROOT, "family", "decode", "EX07C471JBT", *PROJECT)
    assert code == 5
    assert env["result"]["failures"] == [
        {"mpn": "EX07C471JBT", "family": "Example:EX_MLCC", "position": 2, "field": "size"}
    ]
    assert [item["code"] for item in env["issues"]] == ["family.decode-no-match"]


def test_a_tail_is_unverified(monkeypatch: pytest.MonkeyPatch) -> None:
    code, env, err, _ = run(monkeypatch, ROOT, "family", "decode", "EXR06F1002T-Q1", *PROJECT)
    assert code == 0, err
    assert env["result"]["decoded"][0]["suffix"] == "-Q1" and env["evidence"]["level"] == "UNVERIFIED"


def test_expand_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    code, env, err, _ = run(
        monkeypatch, ROOT, "family", "expand", "Example:EX_MLCC", *PROJECT, "--limit", "5"
    )
    assert code == 0, err
    result = env["result"]
    assert [item["mpn"] for item in result["candidates"]] == [
        "EX03R101JAB", "EX03R101JAT", "EX03R101JBB", "EX03R101JBT", "EX03R101KAB"
    ]  # fmt: skip
    assert result["truncated"] is True and result["page"]["total"] == 326


def _grammar(tmp_path: Path, old: str, new: str) -> Path:
    path = tmp_path / "grammar.toml"
    text = (ROOT / "examples/families/devices/example_mlcc.toml").read_text(encoding="utf-8")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return path


def test_a_field_without_a_placeholder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A field without a placeholder"."""
    path = _grammar(
        tmp_path, "[fields.packing]", '[fields.grade]\ncodes.A = { packing = "tray" }\n\n[fields.packing]'
    )
    code, env, _, _ = run(monkeypatch, tmp_path, "family", "lint", path.name)
    assert code == 5
    found = [item for item in env["issues"] if item["code"] == "family.pattern-field"]
    assert len(found) == 1 and "grade" in found[0]["message"]


def test_an_ambiguous_field(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "An ambiguous field"."""
    path = _grammar(tmp_path, 'codes."05"', 'codes."0"')
    code, env, _, _ = run(monkeypatch, tmp_path, "family", "lint", path.name)
    assert code == 5
    found = [item for item in env["issues"] if item["code"] == "family.ambiguous-code"]
    assert len(found) == 1 and all(part in found[0]["message"] for part in ("size", "code 0 ", "03"))


def test_a_clean_lint_and_a_malformed_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err, _ = run(
        monkeypatch, ROOT, "family", "lint", "examples/families/devices/example_mlcc.toml"
    )
    assert code == 0 and env["issues"] == [], err
    path = _grammar(tmp_path, 'licence = "CC0-1.0"', 'licence = "CC0-1.0"\nprice = "0.01"')
    code, _, err, _ = run(monkeypatch, tmp_path, "family", "lint", path.name)
    assert code == 3 and err["code"] == "FEN-3004" and "price" in err["message"]


def test_families_folder_and_duplicate_ids(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "more"
    shutil.copytree(ROOT / "examples/families/devices", folder)
    code, env, err, _ = run(monkeypatch, tmp_path, "family", "list", "--families", "more")
    assert code == 0 and len(env["result"]["families"]) == 3, err
    code, _, err, _ = run(
        monkeypatch, ROOT, "family", "list", *PROJECT, "--families", str(folder)
    )  # fmt: skip
    assert code == 3 and "is defined in" in err["message"]
