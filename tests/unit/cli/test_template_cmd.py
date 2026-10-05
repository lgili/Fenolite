# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``template build`` command (capability sheet-templates, "Template build command" and scenario
"Malformed input exit code"; change c0012; scenario "Unknown action", change c0046)."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.templates import example_path

EXAMPLE = str(example_path("iso5457_generic"))
HEADER = '(kicad_wks\n\t(version 20231118)\n\t(generator "fenolite")\n'


def run(monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str) -> tuple[int, dict, dict]:  # type: ignore[type-arg]
    monkeypatch.chdir(cwd)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["template", *args, "--json"])
    return code, json.loads(out.getvalue() or "{}"), json.loads(err.getvalue() or "{}")


def test_confirmation_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err = run(monkeypatch, tmp_path, "build", EXAMPLE, "--target", "kicad", "--out", "out.kicad_wks")
    assert code == 4 and err["code"] == "FEN-4001"
    assert not (tmp_path / "out.kicad_wks").exists()


def test_dry_run_predicts_the_drawing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = ("build", EXAMPLE, "--target", "kicad", "--out", "out.kicad_wks", "--dry-run")
    code, env, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0 and not (tmp_path / "out.kicad_wks").exists()
    result = env["result"]
    assert [w["path"] for w in result["plan"]] == ["out.kicad_wks"]
    assert set(result["drawn"]) == {"A4", "A3"}
    assert result["drawn"]["A4"]["texts"] > 0 and "1" in result["drawn"]["A4"]["resolved"]
    assert result["sheet"]["name"] == "iso5457_generic" and "title" in result["sheet"]["tokens"]
    assert result["target"] == "kicad" and result["kicad_version"] == 10
    assert env["evidence"] == {"level": "INFERRED", "oracle": None, "hypotheses": ["H-K-WKS-CORNER"]}


def test_confirmed_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    code, env, _ = run(monkeypatch, first, "build", EXAMPLE, "--target", "kicad", "--out", "out.kicad_wks",
                       "--confirm")  # fmt: skip
    assert code == 0 and "plan" not in env["result"]
    data = (first / "out.kicad_wks").read_bytes()
    assert env["receipt"]["written"][0]["sha256"] == hashlib.sha256(data).hexdigest()
    assert data.decode("utf-8").startswith(HEADER)
    code, _, _ = run(monkeypatch, second, "build", EXAMPLE, "--target", "kicad", "-o", "out.kicad_wks",
                     "--confirm", "--kicad-version", "9")  # fmt: skip
    assert code == 0 and (second / "out.kicad_wks").read_bytes() == data


def test_unknown_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, _ = run(
        monkeypatch, tmp_path, "build", EXAMPLE, "--target", "other", "--out", "o.kicad_wks", "--dry-run"
    )
    assert code == 2


def test_unknown_action(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, _ = run(
        monkeypatch, tmp_path, "export", "x", "--target", "kicad", "--out", "out.kicad_wks", "--dry-run"
    )
    assert code == 2 and not (tmp_path / "out.kicad_wks").exists()


def test_malformed_input_exit_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bad = tmp_path / "bad.sheet.toml"
    bad.write_text(Path(EXAMPLE).read_text(encoding="utf-8").replace("[margins]", "colour = 1\n[margins]"))
    code, env, err = run(monkeypatch, tmp_path, "build", "bad.sheet.toml", "--target", "kicad", "--out",
                         "out.kicad_wks", "--dry-run")  # fmt: skip
    assert code == 3 and err["code"] == "FEN-3004"
    assert err["where"] == "bad.sheet.toml:sheet.colour"
    assert [(i["code"], i["where"]) for i in env["issues"]] == [("template.unknown-key", "sheet.colour")]


def test_missing_specification(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err = run(monkeypatch, tmp_path, "build", "nope.sheet.toml", "--target", "kicad", "--out", "o",
                       "--dry-run")  # fmt: skip
    assert code == 3 and err["code"] == "FEN-3001"


def test_listed_in_capabilities(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    assert cli_main.main(["capabilities", "--json", "--no-tools"]) == 0
    commands = {c["name"]: c for c in json.loads(out.getvalue())["result"]["commands"]}
    assert commands["template"]["mutates"] is True
