# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad board that ``fenolite convert --to kicad`` writes from each public PCB document loads and its
DRC runs to a report (capability design-conversion, scenario "KiCad loads the converted board";
``H-K-CONV-A2K-LOAD``; change c0161, task 4.1)."""

from __future__ import annotations

import _a2kcases as a2k
import pytest

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus]


@pytest.mark.parametrize("row", a2k.DOCUMENTS)
def test_written_board_loads(row: str) -> None:
    from _probes import major

    found = a2k.load(row, major())
    print(f"{row} t{major()}: loaded {found.loaded}, drc {found.drc} {found.message}")
    assert found.loaded, found.message
    assert found.drc is not None


def test_probe() -> None:
    from _probes import run

    assert run("convert-a2k-load") == "equal"
