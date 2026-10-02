# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Boards Fenolite refuses and KiCad reads (``H-K-SEXPR-STRICT``; capability verification-loop, "Inputs
Fenolite cannot read"). Outcomes of the fixtures follow ``tests/data/kicad/sexpr/EXPECT.toml``."""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkcases import refused_board
from _checkrun import check, stage
from _probes import major, run
from _projects import STEM

pytestmark = pytest.mark.needs_kicad
LOCATED = ("list-starting-with-list", "cr-in-string")
TEN_ONLY = ("list-starting-with-list", "cr-in-string", "invalid-utf8")


def _folder(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    root.mkdir()
    (root / f"{STEM}.kicad_pcb").write_bytes(refused_board(f"{name}.kicad_pcb", major()))
    return root


@pytest.mark.parametrize("name", ["trailing-content", *TEN_ONLY])
def test_kicad_reads_what_fenolite_refuses(tmp_path: Path, name: str) -> None:
    if name in TEN_ONLY and major() < 10:
        pytest.skip("recorded on 10.0.6 only (EXPECT.toml)")
    root = _folder(tmp_path, name)
    code, env, _, err = check(root)
    refused = [i for i in env["issues"] if i["code"] == "check.read-refused"]
    assert code == 5, err
    assert len(refused) == 1 and refused[0]["message"].startswith("FEN-3004: ")
    where = refused[0]["where"]
    assert where.startswith(f"{STEM}.kicad_pcb:") and "@" in where
    assert ("/" in where.split(":")[1]) == (name in LOCATED)
    for skipped in ("model.validate", "roundtrip"):
        assert (stage(env, skipped)["status"], stage(env, skipped)["reason"]) == ("skipped", "read-refused")
    assert "check.oracle-failed" not in [i["code"] for i in env["issues"]]
    assert run("check-unparsed-drc") == "present"


def test_both_tools_refuse(tmp_path: Path) -> None:
    root = _folder(tmp_path, "empty-list")
    code, env, _, err = check(root)
    assert code == 3 and '"FEN-3004"' in err
    assert [i["code"] for i in env["issues"]] == ["check.read-refused", "check.oracle-failed"]
