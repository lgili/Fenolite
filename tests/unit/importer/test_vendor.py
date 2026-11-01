# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The vendored library of an import (capability board-to-code, "Vendored library of an import")."""

from __future__ import annotations

from pathlib import Path

import pytest
from _importcode import PROJECT, build, edited, imported


def test_build_uses_only_the_vendored_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert imported(tmp_path, PROJECT, "--confirm").exit_code == 0
    out = tmp_path / "out"
    table = (out / "fp-lib-table").read_text(encoding="utf-8")
    assert '(uri "${KIPRJMOD}/lib/Mini.pretty")' in table
    assert '(uri "${KIPRJMOD}/lib/Mini.kicad_sym")' in (out / "sym-lib-table").read_text(encoding="utf-8")
    empty = tmp_path / "config"
    empty.mkdir()
    for name in ("KICAD_CONFIG_HOME", "KICAD10_FOOTPRINT_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(empty))
    reply = build(out)
    assert reply.exit_code == 0, reply.error
    assert set(reply.result["libraries"].values()) == {"project"}


def test_edited_instance(tmp_path: Path) -> None:
    reply = imported(tmp_path, edited(tmp_path), "--confirm")
    assert reply.exit_code == 0, reply.error
    pretty = tmp_path / "out" / "lib" / "Mini.pretty"
    assert sorted(p.name for p in pretty.iterdir()) == [
        "Mini_LED_THT_3mm.kicad_mod",
        "Mini_R_0603.kicad_mod",
        "Mini_R_0603_2.kicad_mod",
    ]
    text = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert 'Part("R201", "Mini:Mini_R_0603_2", footprint="Mini:Mini_R_0603_2"' in text
    codes = [i["code"] for i in (reply.envelope or {})["issues"]]
    assert codes.count("import.footprint-variant") == 1
    assert reply.result["equivalence"]["equivalent"] is True
