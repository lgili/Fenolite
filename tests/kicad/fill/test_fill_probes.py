# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pinned refill behaviour for authored boards."""

from __future__ import annotations

import pytest
from _probes import run

pytestmark = pytest.mark.needs_kicad


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("target", (9, 10))
def test_save(target: int) -> None:
    assert run(f"fill-save-t{target}") == "present"


@pytest.mark.kicad_min_major(10)
def test_repeat() -> None:
    assert run("fill-repeat") == "equal"


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("target", (9, 10))
def test_lift(target: int) -> None:
    assert run(f"fill-lift-t{target}") == "equal"


def test_load9() -> None:
    from _probes import major

    if major() != 9:
        pytest.skip("requires KiCad 9")
    assert run("fill-load9") == "load"
