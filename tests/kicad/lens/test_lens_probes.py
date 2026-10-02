# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes first (c0019 Decision 20; hypothesis H-K-LENS-KEEP), run before the lens code: a re-save keeps
the matching keys of a moved footprint, and Fenolite's rewrite of an edited board keeps its DRC report.
Stop rules: ``absent`` stops the change until the matching keys are revised; ``different`` until the
changed types are explained in ``docs/formats/kicad/drc.md``."""

from __future__ import annotations

import pytest
from _probes import run

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]


@pytest.mark.kicad_min_major(10)
def test_resave_keeps_the_keys() -> None:
    assert run("lens-resave-t10") == "present"


@pytest.mark.parametrize("target", TARGETS)
def test_rewrite_keeps_the_drc_report(target: int) -> None:
    assert run(f"lens-rewrite-t{target}") == "equal"
