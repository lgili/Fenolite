# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A ranged part value changes no written KiCad file (capability design-model, "Value ranges stay out of
backend files"; change c0246). Needs no ``kicad-cli``: CI's KiCad job runs ERC and DRC on the blink."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from _buildhelp import blink_variant

import fenolite.cli.main as cli_main

OLD = 'value="330")'
FLAGS = ("--seed", "5", "--timestamp", "2026-10-29T00:00:00Z")


def _build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, value: str
) -> tuple[dict[str, Any], Path]:
    script = blink_variant(tmp_path / f"src-{name}", OLD, f"value={value})")
    text = script.read_text(encoding="utf-8")
    script.write_text(text.replace("from fenolite.dsl import ", "from fenolite.dsl import ohm, "), "utf-8")
    out = tmp_path / f"out-{name}"
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    code = cli_main.main(["build", str(script), "--out", str(out), "--confirm", "--json", *FLAGS])
    envelope = json.loads(stdout.getvalue())
    assert code == 0, envelope.get("issues")
    return envelope, out


def _hashes(envelope: dict[str, Any], out: Path) -> dict[str, str]:
    files = envelope["receipt"]["written"]
    return {Path(f["path"]).resolve().relative_to(out.resolve()).as_posix(): f["sha256"] for f in files}


def test_written_kicad_files_do_not_change(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    exact_env, exact_out = _build(monkeypatch, tmp_path, "exact", 'ohm("330")')
    ranged_env, ranged_out = _build(monkeypatch, tmp_path, "ranged", 'ohm("330").pct(5)')
    exact, ranged = _hashes(exact_env, exact_out), _hashes(ranged_env, ranged_out)
    assert set(exact) == set(ranged) and any(path.endswith(".kicad_sch") for path in exact)
    differ = sorted(path for path in exact if exact[path] != ranged[path])
    assert differ == [".fenolite/circuit.json"]
    circuits = [
        json.loads((out / ".fenolite" / "circuit.json").read_text("utf-8")) for out in (exact_out, ranged_out)
    ]
    by_ref = [{c["ref"]: c for c in circuit["components"]} for circuit in circuits]
    assert "value_range" not in by_ref[0]["R1"]
    assert by_ref[1]["R1"].pop("value_range") == {
        "unit": "ohm",
        "low": {"m": 3135, "e": -1},
        "nominal": {"m": 33, "e": 1},
        "high": {"m": 3465, "e": -1},
    }
    assert circuits[0] == circuits[1]
