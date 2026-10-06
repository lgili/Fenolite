# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``design.rules.rule()`` through ``fenolite build`` (capability design-dsl, "Rule constructor in the DSL";
rules-model, "Kind support by major"; change c0071). Each test builds a blink variant into ``tmp_path``,
in-process."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _rulesdesign import BOARD_RULES, CREEPAGE_RULE, NEW_KIND_NAMES, script

import fenolite.cli.main as cli_main


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def codes(envelope: dict[str, object]) -> list[str]:
    return [issue["code"] for issue in envelope.get("issues", [])]  # type: ignore[union-attr,index]


def test_six_kinds_built_for_kicad_10(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, out = script(tmp_path, BOARD_RULES + CREEPAGE_RULE), tmp_path / "B"
    code, envelope, err = run(
        monkeypatch, "--kicad-version", "10", "build", str(path), "--out", str(out), "--confirm"
    )
    assert code == 0, err
    text = (out / "blink.kicad_dru").read_text(encoding="utf-8")
    for name in NEW_KIND_NAMES:
        assert f'(rule "fenolite_0_{name}"' in text
    assert "(constraint courtyard_clearance (min 0mm))" in text
    assert "(condition \"(A.Reference == 'U1' || A.Reference == 'R1')\")" in text
    assert "(condition \"A.NetName == 'VIN' && B.NetName == 'GND'\")" in text
    assert "(severity warning)" in text
    model = json.loads((out / ".fenolite" / "rules.json").read_text(encoding="utf-8"))
    assert {"mains", "pitch", "silk"} <= {rule["name"] for rule in model["rules"]}
    assert not any(c.startswith("rules.") for c in codes(envelope))


def test_five_kinds_built_for_kicad_9(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, out = script(tmp_path, BOARD_RULES), tmp_path / "B"
    code, _, err = run(
        monkeypatch, "--kicad-version", "9", "build", str(path), "--out", str(out), "--confirm"
    )
    assert code == 0, err
    assert (out / "blink.kicad_dru").read_text(encoding="utf-8").count("(rule ") == 5


def test_creepage_refused_for_kicad_9(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, out = script(tmp_path, BOARD_RULES + CREEPAGE_RULE), tmp_path / "B"
    args = ("--kicad-version", "9", "build", str(path), "--out", str(out), "--dry-run")
    code, _, err = run(monkeypatch, *args)
    assert code == 7 and "FEN-7001" in err
    assert "does not check creepage rules" in err and "--allow-lossy" in err
    assert not out.exists()
    code, envelope, err = run(monkeypatch, "--allow-lossy", *args)
    assert code == 0, err
    assert "rules.dropped-for-target" in codes(envelope)
