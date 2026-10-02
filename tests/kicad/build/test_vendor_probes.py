# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes first (c0027 Decision 16; hypotheses H-K-VENDOR-GLOBAL, -SHADOW, -PROPS and -DUPNAME): vendored
blink builds and the property board, made without this change's build code. Outcomes are the
``vendor-*`` probes; the stop rules hold when ``vendor-global`` and ``vendor-props`` are ``equal``."""

from __future__ import annotations

import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]


@pytest.mark.parametrize("target", TARGETS)
def test_global(target: int) -> None:
    assert run(f"vendor-global-t{target}") == "equal"


@pytest.mark.parametrize("target", TARGETS)
def test_shadow(target: int) -> None:
    outcome = run(f"vendor-shadow-t{target}")
    print(f"KiCad {major()}: vendor-shadow-t{target} {outcome}")
    assert outcome != "inconclusive", "the D_alt control gave no lib_footprint_mismatch"


@pytest.mark.parametrize("target", TARGETS)
def test_hide(target: int) -> None:
    outcome = run(f"vendor-hide-t{target}")
    print(f"KiCad {major()}: vendor-hide-t{target} {outcome}")
    assert outcome != "inconclusive", "the D control gave a library violation"


@pytest.mark.parametrize("target", TARGETS)
def test_props(target: int) -> None:
    assert run(f"vendor-props-t{target}") == "equal"


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("target", [10, 9], ids=["t10", "t9"])
def test_resave(target: int) -> None:
    print(f"KiCad {major()}: vendor-resave-t{target} {run(f'vendor-resave-t{target}')}")


@pytest.mark.kicad_min_major(10)
def test_dupname() -> None:
    print(f"KiCad {major()}: vendor-dupname-t10 {run('vendor-dupname-t10')}")
