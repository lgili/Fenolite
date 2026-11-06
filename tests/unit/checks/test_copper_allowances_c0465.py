# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Change c0465: allowed shorts in the copper check (copper-check, "Allowed shorts"), on an authored bench."""

from __future__ import annotations

import dataclasses
import hashlib
import json

from _coppercheck import Copper, mm

from fenolite.checks.copper import CopperReport, check_copper
from fenolite.core.coords import Point
from fenolite.model.rules import Selector

PINNED = "a10a567203d8bc6d97fb2d0c728b66e61e3d744179929c75a527a95a6fe3961b"
"""The SHA-256 of ``_text`` of the bench without ``short`` rules, as the code before task 3.2 of change c0465
(commit b63165505) gave it."""


def _p(x: float, y: float) -> Point:
    return Point(mm(x), mm(y))


def _bench() -> Copper:
    """Copper of ``AGND`` touching ``DGND``, of ``VIN`` touching ``DGND``, and ``SIG`` too close to
    ``VIN``."""
    bench = Copper()
    bench.rule("clr", mm(0.2))
    bench.track("AGND", _p(0, 0), _p(2, 0))
    bench.track("DGND", _p(1, -1), _p(1, 1))
    bench.track("VIN", _p(5, 0), _p(7, 0))
    bench.track("DGND", _p(6, -1), _p(6, 1))
    bench.track("SIG", _p(0, 3), _p(2, 3))
    bench.track("VIN", _p(0, 3.3), _p(2, 3.3))
    return bench


def _text(report: CopperReport) -> str:
    return (
        json.dumps(
            {
                "issues": [dataclasses.asdict(i) for i in report.issues],
                "summary": report.summary,
                "evidence": str(report.evidence),
            },
            indent=1,
            sort_keys=True,
            default=str,
        )
        + "\n"
    )


def _shorts(report: CopperReport) -> dict[str, tuple[str, str]]:
    """``"<net>-<net>"`` → the severity and message of each short."""
    found: dict[str, tuple[str, str]] = {}
    for issue in report.issues:
        if issue.code == "copper.short":
            nets = issue.message.split(" touches")[0].removeprefix("copper of ").replace(" and ", "-")
            found[nets] = (issue.severity, issue.message)
    return found


def test_an_existing_report_keeps_its_bytes() -> None:
    report = check_copper(_bench().build(), pads=())
    text = _text(report)
    assert "allowed" not in report.summary
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == PINNED


def test_two_grounds_joined() -> None:
    bench = _bench()
    bench.rule(
        "GND_JOIN", None, Selector("net", "AGND"), Selector("net", "DGND"), severity="ignore", kind="short"
    )
    report = check_copper(bench.build(), pads=())
    shorts = _shorts(report)
    assert shorts["AGND-DGND"][0] == "info" and shorts["AGND-DGND"][1].endswith(" (allowed by rule GND_JOIN)")
    assert shorts["VIN-DGND"] == ("error", "copper of VIN and DGND touches on F.Cu at (6, 0) mm")
    assert report.summary["allowed"] == {"copper.short": 1} and report.summary["shorts"] == 2
    assert [i.severity for i in report.issues if i.code == "copper.clearance"] == ["error"]  # not a short


def test_a_narrower_rule_forbids_again() -> None:
    bench = _bench()
    bench.rule(
        "join_all", None, Selector("all"), Selector("all"), severity="ignore", priority=2, kind="short"
    )
    bench.rule("vin_apart", None, Selector("net", "VIN"), Selector("all"), priority=1, kind="short")
    shorts = _shorts(check_copper(bench.build(), pads=()))
    assert shorts["AGND-DGND"][0] == "info" and shorts["VIN-DGND"][0] == "error"
    assert shorts["VIN-DGND"][1].endswith(" mm")  # an error rule adds nothing


def test_a_warning_rule_relaxes_without_allowing() -> None:
    bench = _bench()
    bench.rule(
        "gnd_warn", None, Selector("net", "DGND"), Selector("net", "AGND"), severity="warning", kind="short"
    )
    report = check_copper(bench.build(), pads=())
    severity, message = _shorts(report)["AGND-DGND"]
    assert severity == "warning" and message.endswith(" (allowed by rule gnd_warn)")
    assert "allowed" not in report.summary


def test_given_allowances_replace_the_design_rules() -> None:
    bench = _bench()
    rule = bench.rule("GND_JOIN", None, Selector("net", "AGND"), Selector("net", "DGND"), severity="ignore",
                      kind="short")  # fmt: skip
    design = bench.build()
    assert _shorts(check_copper(design, pads=(), allowances=()))["AGND-DGND"][0] == "error"
    bench.rules.remove(rule)
    bare = bench.build()
    assert _shorts(check_copper(bare, pads=(), allowances=(rule,)))["AGND-DGND"][0] == "info"
