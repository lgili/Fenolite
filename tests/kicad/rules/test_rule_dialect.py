# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rules dialect in KiCad (capability kicad-file-backend, "Dialect fixtures load in KiCad", and
kicad-oracle, "Silent disable reproduced"; hypotheses H-K-DRU-DIALECT and H-K-DRU-QUOTE; change c0018).
"""

from __future__ import annotations

import _rulebench as rb
import _rulecases as rc
import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("name", ["comments", "units", "selectors"])
def test_dialect_loads(name: str) -> None:
    result = rc.dialect(name)
    rb.require_canary(result.report, result.bench)
    assert run(f"dru-dialect-{name}") == "load"
    if name == "units":
        assert result.types_of("mil") == ("track_width",) and result.types_of("inch") == ("track_width",)
        assert run("dru-dialect-units-mil") == "present" and run("dru-dialect-units-in") == "present"


def test_broken_is_silent() -> None:
    """``broken.kicad_dru`` (the canary and a single-quoted name) loads with exit 0 and no canary."""
    result = rc.broken()
    assert result.report is not None, "DRC wrote no report"
    assert not result.canary, f"KiCad {major()} loaded a rules file with a single-quoted name"
    assert run("dru-broken-silent") == "absent"
