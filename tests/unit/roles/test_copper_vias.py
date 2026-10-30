# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Via arrays where role copper changes layer (change c0243, decision 6; capability net-roles, "Via arrays
at layer changes", scenario "Five vias for one ampere")."""

from __future__ import annotations

from pathlib import Path

from _roleboards import EXAMPLES
from _rolecopper import board, build_role, outcome

from fenolite.geometry import Location, point_in_ring

SCRIPT = """\
# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as a test board; no file, value, name or layout comes from any other project.
from fenolite.dsl import Design, Net, Part, amp, connect, mm

design = Design("via_array")
design.board(mm(40), mm(24))
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_1206", value="1")
r2 = Part("R2", "Fenolite:Resistor", footprint="Fenolite:Chip_1206", value="1")
design.add(r1, r2)
p, q = Net("P"), Net("Q")
connect(p, r1[1], r2[1])
connect(q, r1[2], r2[2])
design.net_role(p, "power", current=amp(1))
design.rules.netclass("POWER", clearance=mm("0.2"), track_width=mm("0.4"), via_diameter=mm("0.6"),
                      via_drill=mm("0.3"), nets=(p,))
r1.place(mm(10), mm(12))
r2.place(mm(30), mm(12), side="bottom")
design.role_copper(kinds=("power",))
"""


def _tables(tmp: Path) -> None:
    libs = (EXAMPLES.parents[1] / "tests" / "data" / "libs").as_posix()
    for table in ("sym-lib-table", "fp-lib-table"):
        text = (EXAMPLES / "buck_shunt" / table).read_text(encoding="utf-8")
        (tmp / table).write_text(text.replace("${KIPRJMOD}/../../../tests/data/libs", libs), encoding="utf-8")


def test_five_vias_for_one_ampere(tmp_path: Path) -> None:
    _tables(tmp_path)
    script = tmp_path / "via_array.py"
    script.write_text(SCRIPT, encoding="utf-8")
    built = build_role(script, tmp_path / "out")
    held = board(built)
    found = held.design.board
    assert found is not None
    net = next(n.id for n in held.design.circuit.nets if n.name == "P")
    zones = {
        layer: z for z in found.zones if z.net_id == net and z.name.startswith("role.") for layer in z.layers
    }
    assert set(zones) == {"F.Cu", "B.Cu"}
    vias = [v.position for v in found.vias if v.net_id == net]
    inside = [
        v for v in vias if all(point_in_ring(v, zone.outline) is Location.INSIDE for zone in zones.values())
    ]
    assert len(inside) >= 5
    done = outcome(built)
    (plan,) = [n for n in done.plan.nets if n.net == "P"]
    assert plan.vias == 5 and plan.layers == ("F.Cu", "B.Cu")
    assert not [i for i in done.issues if i.code in ("kicad.generate.stitch-short", "roles.copper-blocked")]
