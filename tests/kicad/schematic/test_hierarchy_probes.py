# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What a hierarchy and a wire mean to the running ``kicad-cli``, measured before the generator writes a
child sheet or a wire (capability kicad-oracle, "Hierarchy and wire facts are probed"; hypotheses
``H-K-SCH-HIER-FILE`` and ``H-K-SCH-WIRE-END``; change c0070). The sheets are written by hand in
``_hiercases.py``."""

from __future__ import annotations

import _erc
import _hiercases as hier
import _probes
import pytest

pytestmark = pytest.mark.needs_kicad


def test_sheet_files() -> None:
    """A child's file is found from the folder of the sheet that names it; a name that resolves to nothing
    drops the sheet in silence; global labels join the sheets."""
    made, export, report = hier.tree_export("b.kicad_sch")
    print(f"parent tree: sheet paths {dict(export.sheets)}; nets {sorted(export.nets)}")
    print(f"  ERC: {dict(_erc.types(_erc.violations(report)))}")
    assert _probes.run("sch-hier-file-parent") == "present"
    _, dropped, silent = hier.tree_export("sheets/b.kicad_sch")
    print(f"project tree: sheet paths {dict(dropped.sheets)}")
    print(f"  exit: netlist {dropped.returncode}, ERC {silent.returncode}")
    assert _probes.run("sch-hier-file-project") == "absent"
    assert _probes.run("sch-hier-global") == "equal"
    assert hier.findings(report) == {} and hier.findings(silent) == {}
    assert export.sheets["R1"][1] == "/"
    assert export.sheets["R3"] == ("/a/b/", f"/{made.a}/{made.b}/")


def test_wire_ends() -> None:
    """A wire joins the pins at its two ends, under the one label of the pair, and no pin in its middle."""
    export, report = hier.wire_export(False)
    print(f"wire: nets {{name: sorted(nodes)}} = { {n: sorted(v) for n, v in export.nets.items()} }")
    print(f"  ERC: {dict(_erc.types(_erc.violations(report)))}")
    assert _probes.run("sch-wire-ends") == "equal"
    middle, found = hier.wire_export(True)
    print(f"middle: R3 pin 1 is on {[n for n, v in middle.nets.items() if ('R3', '1') in v]}")
    print(f"  ERC: {dict(_erc.types(_erc.violations(found)))}")
    assert _probes.run("sch-wire-middle") == "absent"
