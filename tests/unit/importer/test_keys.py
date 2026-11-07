# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Keys and lock of imported code (capability board-to-code, "Keys and lock of imported code")."""

from __future__ import annotations

from pathlib import Path

from _importcode import PROJECT, build, imported

from fenolite.dsl.lock import read_lock


def test_frozen_build_of_the_import(tmp_path: Path) -> None:
    assert imported(tmp_path, PROJECT, "--confirm").exit_code == 0
    out = tmp_path / "out"
    lock = read_lock((out / "design.lock").read_text(encoding="utf-8"), file="design.lock")
    assert dict(lock.refs) == {
        "J1": "J1",
        "ch1/D101": "D101",
        "ch1/R101": "R101",
        "ch2/D101": "D201",
        "ch2/R101": "R201",
    }
    reply = build(out, "--frozen", "--dry-run")
    assert reply.exit_code not in (7,), reply.error
    assert reply.result["lock"]["changes"] == []


def test_keys_of_unnamed_items(tmp_path: Path) -> None:
    assert imported(tmp_path, PROJECT, "--confirm").exit_code == 0
    text = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert 'design.line("F.SilkS/line/1",' in text
    assert '"F.SilkS/text/1",' in text
