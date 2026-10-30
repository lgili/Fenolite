# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The requirement table of the stage ``circuit.rules`` (change c0253; capability electrical-contracts,
"Requirement table")."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _contracts import built_sensor, cli


def test_rows_of_the_bad_sensor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Rows of the bad sensor"."""
    out = built_sensor(monkeypatch, tmp_path, "bad")
    code, env = cli(monkeypatch, "check", str(out), "--stages", "circuit.rules")
    (stage,) = env["result"]["stages"]
    rows = stage["summary"]["requirements"]
    assert [r["id"] for r in rows] == sorted(r["id"] for r in rows)
    (cap,) = [r for r in rows if r["id"] == "circuit.rating-voltage:C1:voltage"]
    assert cap["value"]["range"]["unit"] == "volt"
    assert cap["value"]["range"]["high"] == {"m": 132, "e": -1}
    assert (cap["value"]["source"], cap["value"]["basis"].split(";")[0]) == ("user", "rig bench")
    assert cap["limit"]["range"]["high"] == {"m": 8, "e": 0}
    assert (cap["limit"]["source"], cap["limit"]["kind"], cap["status"]) == ("policy", "abs_max", "fail")
    model = json.loads((out / ".fenolite" / "circuit.json").read_text(encoding="utf-8"))
    ids = {c["ref"]: c["id"] for c in model["components"]}
    nets = {n["name"]: n["id"] for n in model["nets"]}
    assert {ids["C1"], nets["V12"]} <= set(cap["entities"])
    assert {row["source"] for r in rows for row in (r["value"] or {"source": "user"}, r["limit"])} <= {
        "device", "role", "policy", "user",
    }  # fmt: skip

    def floats(value: object) -> bool:
        if isinstance(value, float):
            return True
        if isinstance(value, dict):
            return any(floats(v) for v in value.values())
        return isinstance(value, list) and any(floats(v) for v in value)

    assert not floats(env) and code == 5
