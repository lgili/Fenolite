# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Role rows in the requirement table (change c0253; capability net-roles, "Role rows in the requirement
table" and "Sources of role rows")."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from _contracts import cli
from _roleboards import EXAMPLES, build_script


def _checked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, limits: str = "") -> dict[str, Any]:
    folder = (
        tmp_path / "examples" / "roles" / "buck_shunt"
    )  # its library tables name ../../../tests/data/libs
    shutil.copytree(EXAMPLES / "buck_shunt", folder, ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / "tests" / "data").mkdir(parents=True)
    (tmp_path / "tests" / "data" / "libs").symlink_to(EXAMPLES.parents[1] / "tests" / "data" / "libs")
    script = folder / "table.py"
    script.write_text(
        "from buck_shunt_board import make\n\nfrom fenolite.dsl import Design\n\n"
        f'design = make(Design("buck_shunt_bad"), "bad")\n{limits}',
        encoding="utf-8",
    )
    built = build_script(script, tmp_path / "out")
    code, env = cli(monkeypatch, "roles", str(built.out), "--accept-all", "--confirm")
    assert code == 0, env
    code, env = cli(monkeypatch, "roles", str(built.out), "--check")
    assert code in (0, 5), env
    return env


def test_the_bad_bucks_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "The bad buck's rows": a failing ``roles.loop-area`` row for the hot loop, and the findings
    are the role checks' own."""
    env = _checked(monkeypatch, tmp_path)
    rows = env["result"]["requirements"]
    loops = [r for r in rows if r["id"].startswith("roles.loop-area:")]
    assert loops and any(r["status"] == "fail" for r in loops)
    assert env["result"]["summary"]["requirements"] == rows  # the board was not built with contracts
    assert any(i["code"] == "roles.loop-area" for i in env["issues"])
    assert all(side["source"] in ("device", "role", "policy", "user") for r in rows for side in (r["limit"],))


def test_sources_profile_and_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Profile and override sources"."""
    rows = _checked(monkeypatch, tmp_path / "a")["result"]["requirements"]
    (ratio,) = [
        r for r in rows if r["id"].startswith("roles.loop-area:") and r["id"].endswith(":loop_ratio_max")
    ]
    assert ratio["limit"]["source"] == "policy"
    assert "loop_ratio_max" in ratio["limit"]["basis"] and "H-G-ROLE-LOOP-RATIO" in ratio["limit"]["basis"]
    rows = _checked(monkeypatch, tmp_path / "b", 'design.role_limits(loop_max="60mm2")\n')["result"][
        "requirements"
    ]
    (largest,) = [r for r in rows if r["id"].startswith("roles.loop-area:") and r["id"].endswith(":loop_max")]
    assert (largest["limit"]["source"], largest["limit"]["basis"]) == ("user", "role_limits")
