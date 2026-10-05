# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What ``kicad-cli sch erc`` writes, on the running major (capability kicad-oracle, "ERC facts proved per
major"; ``H-K-ERC-JSON``, ``H-K-ERC-POS`` and ``H-K-ERC-TYPES``; change c0062).

Every outcome is a probe of ``_probes.PROBES``, pinned per version by ``tests/kicad/test_probe_results.py``.
"""

from __future__ import annotations

import _erccases as cases
import pytest
from _probes import major, run

from fenolite.backends.kicad import erc

pytestmark = pytest.mark.needs_kicad


def test_report_shape() -> None:
    assert run("erc-report-keys") == "equal"
    assert run("erc-ignored-checks") == ("present" if major() >= 10 else "absent")
    clean = cases.clean()
    assert clean.report is not None and clean.run.returncode == 0
    assert clean.report.violations == () and clean.report.sheets == ("/",)
    assert (clean.report.ignored_checks != ()) is (major() >= 10)
    assert clean.report.coordinate_units == "mm"


def test_shape_of_a_schematic_that_does_not_load() -> None:
    assert run("erc-unloadable") == "absent"
    failed = cases.unloadable_run()
    assert failed.report is None and failed.run.returncode == 3
    assert "Failed to load schematic" in failed.run.stderr


def test_shape_of_what_the_run_writes() -> None:
    """The run writes its report, and local settings beside its input on 10.0 only (recorded per major);
    the oracle names whatever it wrote in ``tool_writes``."""
    assert run("erc-writes-prl") in ("present", "absent")
    assert run("erc-writes-prl") == ("present" if major() >= 10 else "absent")


def test_positions() -> None:
    assert run("erc-position-scale") == "equal"
    report, expected = cases.open_pins()
    assert report is not None and len(expected) == len(cases.POSITION_PINS) == 5
    found = cases.reported_pins(report, cases.blink_files(major()))
    assert found == {f"{ref}-{pin}": point for (ref, pin), point in expected.items()}
    assert len({(p.x, p.y) for p in found.values()}) == 5  # five different points, so the scale is tested


def test_positions_scale_is_the_proved_one() -> None:
    """``POSITION_SCALE`` holds the running major exactly when its probe is ``equal``."""
    assert (major() in erc.POSITION_SCALE) is (run("erc-position-scale") == "equal")
    assert erc.POSITION_SCALE[major()] == 100


@pytest.mark.parametrize("control", cases.CONTROL_TYPES)
def test_types(control: str) -> None:
    kind = cases.control_type(control)
    name = "single-pin-label" if control == "single_pin_label" else control.replace("_", "-")
    assert run(f"erc-type-{kind.replace('_', '-')}") == "present"
    assert run(f"erc-type-{name}-ignored") == "absent"
    assert run(f"erc-sev-{name}-warning") == "equal"
    report = cases.control_report(control)
    assert report is not None
    assert {v.severity for v in report.of_type(kind)} <= {"error", "warning"}


def test_types_of_the_single_pin_label_differ_by_major() -> None:
    mine = cases.SINGLE_PIN_LABEL[major()]
    for kind in set(cases.SINGLE_PIN_LABEL.values()):
        expected = "present" if kind == mine else "absent"
        assert run(f"erc-type-{kind.replace('_', '-')}") == expected


def test_types_default_severities() -> None:
    errors = ("pin_not_connected", "pin_not_driven", "power_pin_not_driven")
    for control in cases.CONTROL_TYPES:
        report = cases.control_report(control)
        assert report is not None
        found = report.of_type(cases.control_type(control))
        assert found and {v.severity for v in found} == {"error" if control in errors else "warning"}


def test_types_ignored_check_is_listed_on_10() -> None:
    report = cases.control_report("pin_not_connected", "ignore")
    assert report is not None
    assert ("pin_not_connected" in report.ignored_checks) is (major() >= 10)
