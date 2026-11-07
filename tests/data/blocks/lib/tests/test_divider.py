# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite as test data (change c0270).
"""Plain assertions shipped beside the authored block; no pytest required."""

import runpy
from pathlib import Path

from fenolite.dsl import volt
from fenolite.testing import instantiate, stimulus

divider = runpy.run_path(str(Path(__file__).resolve().parents[1] / "divider.py"))["divider"]


def test_ratio_and_connectivity():
    with instantiate(divider, stimulus=stimulus(HI=volt(12).pct(2), LO=volt(0))) as design:
        assert design.requirements("dut/*")[0].status == "pass"
        assert design.connected(design.ref("dut/top")[2], design.ref("dut/bot")[1])
        assert design.ref("dut/top").at == (10_000_000, 10_000_000)
