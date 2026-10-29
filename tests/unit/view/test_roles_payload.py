# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The data of the Net Roles workspace (change c0245, roles-workspace, "Roles payload")."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

import fenolite.cli.main as cli_main
from fenolite.view import roles as roles_view
from fenolite.view.export import embedded

ROOT = Path(__file__).resolve().parents[3]
BUCK = ROOT / "examples" / "roles" / "buck_shunt" / "bad.py"


def run(monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str) -> tuple[int, dict[str, Any], str, str]:
    """``fenolite ARGS --json`` in this process: the exit code, the envelope, stderr and stdout."""
    monkeypatch.chdir(cwd)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue() or "{}"), err.getvalue(), out.getvalue()


@pytest.fixture
def buck(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    code, _, _, _ = run(
        monkeypatch, tmp_path, "build", str(BUCK), "--out", str(tmp_path / "build"), "--confirm", "--json"
    )
    assert code == 0
    return tmp_path / "build"


def test_the_numbers_are_the_commands(buck: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "The numbers are the command's": the exported page's roles data holds the reply of
    `fenolite roles --check` unchanged."""
    board = buck / "buck_shunt_bad.kicad_pcb"
    code, reply, _, _ = run(monkeypatch, tmp_path, "roles", str(board), "--check")
    assert code == 0
    page = tmp_path / "view.html"
    code, _, _, _ = run(
        monkeypatch, tmp_path, "view", str(buck / "buck_shunt_bad.kicad_pro"), "--workspace", "roles",
        "--no-models", "--cache", "off", "--export", str(page), "--confirm",
    )  # fmt: skip
    assert code == 0
    data = embedded(page.read_text(encoding="utf-8"))
    assert data is not None
    (payload,) = data["roles"].values()
    result = reply["result"]
    assert payload["schema"] == roles_view.SCHEMA and payload["document"] == board.name
    assert [{k: v for k, v in row.items() if k != "state"} for row in payload["roles"]] == result["roles"]
    for key in ("loops", "kelvins", "gates", "classes", "measures", "limits", "summary"):
        assert payload[key] == result[key], key
    assert payload["issues"] == reply["issues"]
    assert payload["evidence"]["level"] == "INFERRED"
    assert payload["counts"]["roles"] == {"confirmed": 0, "declared": 4, "inferred": 8}
    assert set(payload["explain"]) <= {issue["code"] for issue in reply["issues"]} and payload["explain"]
    assert payload["locked"] == {"tracks": [], "arcs": [], "vias": []}


def test_limits_name_their_source(buck: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Change c0245: `roles --check` replies with each limit in force and where it came from."""
    code, reply, _, _ = run(
        monkeypatch, tmp_path, "roles", str(buck / "buck_shunt_bad.kicad_pcb"), "--check", "--json"
    )
    assert code == 0
    limits = reply["result"]["limits"]
    hot = {lim["key"]: lim for lim in limits if lim["group"] == "hot_SW"}
    assert hot["loop_ratio_max"] == {
        "net": None, "group": "hot_SW", "kind": "hot", "key": "loop_ratio_max", "value": 2000,
        "unit": "per mille", "origin": "profile", "source": "H-G-ROLE-LOOP-RATIO", "label": "INFERRED",
    }  # fmt: skip
    assert hot["loop_max"]["value"] is None and hot["loop_max"]["source"] == "user"
    gh = {lim["key"]: lim for lim in limits if lim["net"] == "GH"}
    assert gh["switching_distance_nm"]["value"] == 1_000_000


def test_summary_and_states() -> None:
    reply = {
        "result": {
            "roles": [{"net": "A", "source": "confirmed"}, {"net": "B", "source": "inferred"}],
            "loops": [],
        },
        "issues": [{"code": "roles.x", "severity": "warning"}],
        "evidence": {"level": "INFERRED", "hypotheses": ["H-G-ROLE-INFER"]},
    }
    data = roles_view.payload(reply, document="b.kicad_pcb", sha256="0", locked={"tracks": [3, 1]})
    assert [r["state"] for r in data["roles"]] == ["confirmed", "inferred"]
    assert data["locked"] == {"tracks": [1, 3]}
    assert roles_view.summary(data) == {
        "document": "b.kicad_pcb",
        "counts": {"confirmed": 1, "declared": 0, "inferred": 1},
        "findings": {"error": 0, "warning": 1, "info": 0},
        "groups": 0,
        "locked": 2,
    }
