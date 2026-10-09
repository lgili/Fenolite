# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``KicadOracle.report_limits`` with a fake ``kicad-cli`` (capability backend-protocol, "DRC report limits
of an oracle"; change c0141). Hermetic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _fakecli import fake_kicad_cli
from _resources import posix_tools

from fenolite.backends.base import DrcLimits, LimitedOracle
from fenolite.backends.kicad import canary
from fenolite.backends.kicad import drc as drcmod
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.oracle import KicadOracle

needs_posix = pytest.mark.skipif(not posix_tools(), reason="the fake kicad-cli is a POSIX script")
PROBES = Path(__file__).resolve().parents[4] / "docs" / "evidence" / "kicad" / "probes"
RECORDED = {9: "9.0.9", 10: "10.0.6"}
"""The probe file of each major of the table."""


def _oracle(tmp_path: Path, version: str) -> KicadOracle:
    return KicadOracle(KicadCli(fake_kicad_cli(tmp_path / "bin", version=version), timeout=60.0))


@needs_posix
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


def test_each_major_has_its_own_row() -> None:
    """One row per major, so that a major's limit can be corrected alone; today their numbers are equal."""
    assert drcmod.REPORT_LIMITS[9] is not drcmod.REPORT_LIMITS[10]
    assert set(drcmod.MEASURED_TYPES) == set(drcmod.REPORT_LIMITS) == set(RECORDED)


@pytest.mark.parametrize("major", sorted(RECORDED))
def test_the_measured_types_follow_the_probe_files(major: int) -> None:
    """``MEASURED_TYPES[major]`` holds exactly the types whose probe ``drc-limit-<type>`` is ``equal`` in the
    committed probe file of that major (capability kicad-oracle, "DRC report limits are probed": the table
    holds only values that its probes record). ``below``, ``all-track-errors`` and ``keys`` are not types."""
    probes: dict[str, str] = json.loads((PROBES / f"{RECORDED[major]}.json").read_text(encoding="utf-8"))[
        "probes"
    ]
    prefix, others = "drc-limit-", {"below", "all-track-errors", "keys"}
    found = {pid[len(prefix) :]: outcome for pid, outcome in probes.items() if pid.startswith(prefix)}
    types = {type_: outcome for type_, outcome in found.items() if type_ not in others}
    assert len(types) == 13
    assert drcmod.MEASURED_TYPES[major] == {type_ for type_, outcome in types.items() if outcome == "equal"}
    assert set(drcmod.REPORT_LIMITS[major].per_type) <= drcmod.MEASURED_TYPES[major]


def test_hole_clearance_is_not_measured_on_9() -> None:
    """9.0.9 reports no ``hole_clearance`` entry for the bench's construct, so that type alone separates the
    two majors; its limit on 9 is the assumed ``others``."""
    assert drcmod.MEASURED_TYPES[10] - drcmod.MEASURED_TYPES[9] == {"hole_clearance"}
    assert drcmod.MEASURED_TYPES[9] < drcmod.MEASURED_TYPES[10]
    assert drcmod.REPORT_LIMITS[9].limit("hole_clearance") == drcmod.REPORT_LIMITS[9].others == 199


@needs_posix
def test_a_major_nobody_measured_has_no_limits(tmp_path: Path) -> None:
    oracle = _oracle(tmp_path, "11.0.0")
    with pytest.raises(ValueError, match="unsupported KiCad 11"):
        oracle.report_limits()
