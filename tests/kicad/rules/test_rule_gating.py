# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Target gating in KiCad (capability kicad-file-backend, "Custom rules files are read and written";
change c0018): ``ten_only.kicad_dru`` holds the canary and a 10.0-only constraint."""

from __future__ import annotations

import _rulebench as rb
import _rulecases as rc
import pytest
from _probes import run

from fenolite.backends.kicad.dru import RulesLossError, read_rules, write_rules

pytestmark = pytest.mark.needs_kicad


def test_target_9_refused() -> None:
    with pytest.raises(RulesLossError):
        write_rules(read_rules((rb.RULES / "ten_only.kicad_dru").read_text(encoding="utf-8")), target=9)


def test_target_9_lossy_loads() -> None:
    result = rc.gating(9)
    rb.require_canary(result.report, result.bench)
    assert run("dru-gating-lossy-9") == "load"


@pytest.mark.kicad_min_major(10)
def test_target_10_loads() -> None:
    result = rc.gating(10)
    rb.require_canary(result.report, result.bench)
    assert run("dru-gating-ten") == "load"
