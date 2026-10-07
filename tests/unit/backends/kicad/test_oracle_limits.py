# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``KicadOracle.report_limits`` with a fake ``kicad-cli`` (capability backend-protocol, "DRC report limits
of an oracle"; change c0141). Hermetic."""

from __future__ import annotations

from pathlib import Path

import pytest
from _fakecli import fake_kicad_cli
from _resources import posix_tools

from fenolite.backends.base import DrcLimits, LimitedOracle
from fenolite.backends.kicad import canary
from fenolite.backends.kicad import drc as drcmod
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.oracle import KicadOracle

pytestmark = pytest.mark.skipif(not posix_tools(), reason="the fake kicad-cli is a POSIX script")


def _oracle(tmp_path: Path, version: str) -> KicadOracle:
    return KicadOracle(KicadCli(fake_kicad_cli(tmp_path / "bin", version=version), timeout=60.0))


@pytest.mark.parametrize("version", ["10.0.6", "9.0.9"])
def test_the_oracle_states_its_limits(tmp_path: Path, version: str) -> None:
    oracle = _oracle(tmp_path, version)
    assert isinstance(oracle, LimitedOracle)
    limits = oracle.report_limits()
    assert limits is drcmod.REPORT_LIMITS[oracle.major()]
    assert limits.limit("clearance") == 499
    assert limits.limit("unconnected_items") == 499
    assert limits.limit("track_dangling") == 199
    assert canary.CLEARANCE_REPORT_LIMIT == limits.limit("clearance")


def test_the_table_holds_the_two_measured_majors() -> None:
    expected = DrcLimits({"clearance": 499, "unconnected_items": 499}, others=199)
    assert dict(drcmod.REPORT_LIMITS) == {9: expected, 10: expected}


def test_a_major_nobody_measured_has_no_limits(tmp_path: Path) -> None:
    oracle = _oracle(tmp_path, "11.0.0")
    with pytest.raises(ValueError, match="unsupported KiCad 11"):
        oracle.report_limits()
