# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Two converters agree: Fenolite's conversion of each public PCB document and ``kicad-cli pcb import`` of
the same document at level 5 under the profile ``kicad-import`` (capability design-conversion, scenario
"Two converters agree"; ``H-K-CONV-A2K-IMPORT``; change c0161, task 4.2)."""

from __future__ import annotations

import _a2kcases as a2k
import pytest

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus, pytest.mark.kicad_min_major(10)]


@pytest.mark.parametrize("row", a2k.DOCUMENTS)
def test_two_converters_agree(row: str) -> None:
    found = a2k.agreement(row)
    if found.skipped:
        pytest.skip(f"{row}: {found.skipped} (recorded)")
    assert found.report is not None and found.report.levels[-1].level == 5
    print(f"{row}: explained {sorted({(d.kind, kind) for d, kind in found.explained})}")
    assert found.unexplained == (), [(d.level, d.kind, d.where, d.a, d.b) for d in found.unexplained][:10]


def test_probe() -> None:
    from _probes import run

    assert run("convert-a2k-import") == "equal"
