# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite build`` with an unused-pin request and parts used through their ends (capability design-dsl,
"Unused pins resolved in a build", "Must-connect pins", "Two-pin parts checked in a build"; change c0247):
the command passes the script's side channels to both targets."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _buildhelp import blink_variant

import fenolite.cli.main as cli_main

REQUEST = "u1.unused_no_connect()\n"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object]]:
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}


def issues(env: dict[str, object], code: str) -> list[dict[str, str]]:
    return [i for i in env.get("issues", []) if i["code"] == code]  # type: ignore[union-attr, index]


def test_build_marks_the_open_pins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src", append=REQUEST, marks=False)
    out = tmp_path / "B"
    code, _ = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 0
    circuit = json.loads((out / ".fenolite" / "circuit.json").read_text(encoding="utf-8"))
    assert len(circuit["no_connects"]) == 29
    assert (out / "blink.kicad_sch").read_text(encoding="utf-8").count("(no_connect") == 29


def test_build_open_supply_pin_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src", "connect(vin, u1[9])\n", "", append=REQUEST, marks=False)
    out = tmp_path / "B"
    code, env = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 5 and not out.exists()
    (found,) = issues(env, "build.must-connect-unconnected")
    assert found["severity"] == "error" and "U1" in found["message"] and "9" in found["message"]


def test_build_kept_supply_pin_is_not_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_variant(
        tmp_path / "src", "connect(vin, u1[9])\n", "", append="u1.unused_no_connect(keep=(9,))\n", marks=False
    )
    out = tmp_path / "B"
    code, env = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 0 and not issues(env, "build.must-connect-unconnected")


def test_build_three_pin_part_used_through_its_ends(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src", append="connect(Net('SPARE'), u1.b)\n", marks=False)
    out = tmp_path / "B"
    code, env = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 5 and not out.exists()
    (found,) = issues(env, "build.not-two-terminal")
    assert "U1" in found["message"] and "32" in found["message"]


def test_build_altium_target_resolves_the_request(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src", "connect(vin, u1[9])\n", "", append=REQUEST, marks=False)
    out = tmp_path / "B"
    code, env = run(monkeypatch, str(script), "--out", str(out), "--target", "altium", "--confirm")
    assert code == 5 and issues(env, "build.must-connect-unconnected")
