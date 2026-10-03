# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Two seeded faults located by ``fenolite check``, and c0018's overlapping rules as the permanent
positive control (capability verification-loop, "Negative tests and a positive control"), on 9.0.9 and
10.0.6. The projects are written into ``tmp_path`` by ``_fixtures``; nothing is committed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import _fixtures as fx
import _rulebench as rb
import _rulecases
import pytest
from _checkrun import check, stage
from _probes import major
from _projects import STEM, authored_project

from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.drc_json import item_locations

pytestmark = pytest.mark.needs_kicad


def _errors(env: dict[str, Any], code: str) -> list[dict[str, Any]]:
    return [i for i in env["issues"] if i["code"] == code and i["severity"] == "error"]


def test_reassigned(tmp_path: Path) -> None:
    code, env, _, err = check(fx.reassigned(tmp_path, major=major()))
    assert env, err
    found = _errors(env, "netlist.assignment-differs")
    assert code == 5 and [i["where"] for i in found] == ["R1-2"]
    assert "in the model" in found[0]["message"] and "GND in the board" in found[0]["message"]
    pairs = stage(env, "netlist.assignment_compare")["summary"]["pairs"]
    assert [(p["a"], p["b"], p["differences"]) for p in pairs] == [
        ("model", "board", 1),
        ("board", "export", 0),
    ]


def test_bridging(tmp_path: Path) -> None:
    code, env, _, err = check(fx.bridging(tmp_path, major=major()))
    assert env, err
    shorts = _errors(env, "kicad.drc.shorting-items")
    assert code == 5 and shorts and all("R1-2" in i["where"].split(", ") for i in shorts)
    assert stage(env, "drc.kicad")["summary"]["types"]["kicad.drc.shorting-items"] == "shorting_items"


@pytest.mark.parametrize("direction", ["forward", "reverse"])
def test_overlap(tmp_path: Path, direction: str) -> None:
    # c0018's own report of the bench first: the canary fired, and the later rule governs.
    reference = _rulecases.order(direction)
    bench = reference.bench
    report = rb.require_canary(reference.report, bench)
    between = rb.violations_between(report, bench.uuids("ord_a"), bench.uuids("ord_b"), "clearance")
    assert len(between) == (1 if direction == "forward" else 0)
    # then the check output, judged by item: the bench carries the canary pair, so counts would mislead.
    root = fx.overlap_bench(tmp_path, major=major(), reverse=direction == "reverse")
    _, env, _, err = check(root)
    assert env, err
    name = f"{STEM}.kicad_pcb"
    locations = item_locations(read_board((root / name).read_text(encoding="utf-8"), file=name), "kicad")
    where = {label: locations[bench.uuids(label)[0]] for label in ("ord_a", "ord_b", "canary_a", "canary_b")}
    clearances = [set(i["where"].split(", ")) for i in _errors(env, "kicad.drc.clearance")]
    if {where["canary_a"], where["canary_b"]} not in clearances:
        pytest.fail(
            "rules file not loaded: the canary finding is absent from the check output", pytrace=False
        )
    assert clearances.count({where["canary_a"], where["canary_b"]}) == 1
    ord_pair = {where["ord_a"], where["ord_b"]}
    if direction == "forward":
        assert clearances.count(ord_pair) == 1
    assert sum(1 for c in clearances if c & ord_pair) == (1 if direction == "forward" else 0)
    assert stage(env, "drc.kicad")["summary"]["canary"] == "fired"


def test_clean(tmp_path: Path) -> None:
    _, env, _, err = check(authored_project(tmp_path, major=major(), built=True))
    assert env, err
    codes = {i["code"] for i in env["issues"]}
    assert "netlist.assignment-differs" not in codes and "kicad.drc.shorting-items" not in codes
