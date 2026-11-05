# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Wired sheets pass KiCad's ERC and its netlist export equals Fenolite's own netlist (capability
kicad-schematic, "Wired sheet layout" and "Power symbols on a generated sheet"; change c0406). Each
authored design of ``tests/_wireddesigns.py`` is built wired for the running major; the readable build of
the same design is the baseline of the ERC: the wired sheet adds no violation."""

from __future__ import annotations

import _erc
import _netlistcases as cases
import _probes
import pytest
from _wireddesigns import DESIGNS, build_authored

from fenolite.lens.build import BuildOutput

pytestmark = pytest.mark.needs_kicad


def erc(output: BuildOutput) -> list[str]:
    files = cases.project_files(output)
    name = cases.schematic_of(output)
    report = _erc.run_erc(_probes.runner(), name, files)
    return sorted(str(v.get("type", "")) for v in _erc.violations(report))


@pytest.mark.parametrize("name", list(DESIGNS))
def test_wired_sheet_adds_no_erc_violation(name: str) -> None:
    wired = build_authored(DESIGNS[name](), "wired", _probes.major())
    readable = build_authored(DESIGNS[name](), "readable", _probes.major())
    found = erc(wired)
    print(f"erc-wired-{name}: {len(found)} violation(s) on kicad-cli {_probes.version()}")
    assert found == [] or sorted(found) == sorted(erc(readable)), found


@pytest.mark.parametrize("name", list(DESIGNS))
def test_wired_netlist_equals_kicad_export(name: str) -> None:
    output = build_authored(DESIGNS[name](), "wired", _probes.major())
    assert cases.own_differences(output) == ()
    nets = _erc.netlist(_probes.runner(), cases.schematic_of(output), cases.project_files(output))
    # every net keeps the name the design gave it: no Net-(…) and no /sheet/ prefix
    assert not [n for n in nets if n.startswith(("Net-(", "/"))], sorted(nets)
    assert "GND" in nets
