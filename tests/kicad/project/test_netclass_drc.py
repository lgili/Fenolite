# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net classes written by Fenolite are enforced by kicad-cli (capability kicad-oracle, "Net-class rules
are enforced by kicad-cli"; hypotheses H-K-PRO-VERSION, -MIN, -NETCLASS, -PATTERNS and -FLOOR; change
c0010). On 10.0 the target-10 and target-9 sets run; on 9.0 the target-9 set. Every case asserts on its
``pro-*`` probe; a missing canary fails with "rules file not loaded"."""

from __future__ import annotations

import _netclass_bench as nb
import _procases as pc
import pytest
from _probes import major, run

from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber
from fenolite.backends.kicad.pro import update_project
from fenolite.core.errors import Issue

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]


def check(name: str, target: int, expected: str) -> None:
    found = pc.outcome(name, target)
    nb.assert_loaded(found, name)
    assert found == expected, f"{name} (target {target}) on KiCad {major()}: {found}"
    assert run(f"pro-{name}-t{target}") == expected


@pytest.mark.parametrize("target", TARGETS)
def test_full_set(target: int) -> None:
    check("full", target, "present")


@pytest.mark.parametrize("target", TARGETS)
def test_three_way(target: int) -> None:
    check("full", target, "present")
    check("noproject", target, "absent")
    check("noclass", target, "absent")


@pytest.mark.parametrize("target", TARGETS)
def test_minimal_project(target: int) -> None:
    check("minimal", target, "equal")


@pytest.mark.parametrize("target", TARGETS)
def test_patterns(target: int) -> None:
    check("patterns", target, "present")
    check("decoys", target, "present")
    check("anchor", target, "absent")


@pytest.mark.parametrize("target", TARGETS)
def test_floor(target: int) -> None:
    check("floor-template", target, "absent")
    check("floor-raised", target, "present")
    low = nb.bench_design(target=target, hv_clearance=500_000)
    data = _json.loads(pc._files(low, target)[pc.PROJECT])  # noqa: SLF001
    data["board"]["design_settings"]["rules"]["min_clearance"] = JsonNumber("1.5")
    found: list[Issue] = []
    update_project(_json.dumps(data), low, target=target, issues=found)
    assert any(i.code == "kicad.project.below-floor" and "HV" in i.message for i in found)
