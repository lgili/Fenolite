# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A built design with ``design.rules.rule()`` calls loads its rules in KiCad (capability kicad-oracle,
"New rule kinds are enforced by kicad-cli"; change c0071). The blink variant of ``tests/_rulesdesign.py`` is
built for the running major; the rules file it writes, with the scoped canary added to a copy, is run on the
bench of the kinds, where each rule kind is checked by KiCad."""

from __future__ import annotations

import io
import json
from pathlib import Path

import _kindcases as kc
import _rulebench as rb
import _rulecases as rc
import pytest
from _rulesdesign import BOARD_RULES, CREEPAGE_RULE, script

import fenolite.cli.main as cli_main

pytestmark = pytest.mark.needs_kicad


def test_built_rules_file_loads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    major = kc.target()
    append = BOARD_RULES + (CREEPAGE_RULE if major >= 10 else "")
    path, out = script(tmp_path, append), tmp_path / "B"
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    args = ["--kicad-version", str(major), "build", str(path), "--out", str(out), "--confirm", "--json"]
    assert cli_main.main(args) == 0, json.loads(stdout.getvalue() or "{}")
    text = (out / "blink.kicad_dru").read_text(encoding="utf-8")
    assert text.count("(rule ") == (6 if major >= 10 else 5)
    # KiCad drops a rules file whole for one bad rule: the canary of a copy proves that every rule loaded
    result = kc.Run(
        kc.board_bench(), rb.drc(rc.runner(), kc.board_bench(), rb.with_scoped_canary(text), major), {}
    )
    rb.require_canary(result.report, result.bench)
    # the file's board-wide hole rule is 0.3 mm, and the bench's holes are 0.7 mm apart
    assert not result.between("hole_to_hole_control", kc.VIOLATION_TYPES["hole_to_hole"])
