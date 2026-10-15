# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic written for a public document passes KiCad's ERC without a connection error and its
netlist equals the circuit that was written at level 2 (``H-K-CONV-A2K-SCH``; change c0161, task 4.3).

Each public PCB document holds its circuit; the generated schematic draws it with generic symbols. A
document whose circuit the generator refuses has no schematic, and its report names the schematic lost."""

from __future__ import annotations

import _a2kcases as a2k
import pytest

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus]


@pytest.mark.parametrize("row", a2k.DOCUMENTS)
def test_schematic_erc_and_netlist(row: str) -> None:
    from _probes import major

    found = a2k.schematic_run(row, major())
    if found is None:
        pytest.skip(f"{row}: the generator refused the circuit; the report names the schematic lost")
    print(f"{row} t{major()}: erc {found.erc}, differences {found.differences}")
    assert found.erc is not None
    assert not [entry for entry in found.erc if entry.split("=")[0] not in a2k.SCHEMATIC_TYPES_OK]
    assert found.differences == ()


def test_probe() -> None:
    from _probes import run

    assert run("convert-a2k-sch") == "equal"
