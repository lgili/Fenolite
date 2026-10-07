# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reference solution of the task ``custom-footprint``: a part the catalog lacks, authored here.

Authored for Fenolite's agent evaluation. ``U1`` is an invented three-pin part with four pads: its
symbol and its footprint are written in this script from the dimensions the task gives, which are round
values chosen for the task and belong to no product. Pin 2 takes the pads 2 and 4. The header comes
from the built-in catalog, and all copper is written here, so no router is needed.
"""

from fenolite.dsl import Design, Footprint, Net, Part, Symbol, connect, mm

design = Design("board")
design.board(mm(30), mm(20))
design.rules.minimum(
    clearance=mm(0.2), track_width=mm(0.2), via_diameter=mm(0.6), via_drill=mm(0.3), edge_clearance=mm(0.3)
)

# The footprint: three small pads in a column on the left, one large pad on the right.
land = Footprint("Local", "Sensor4", kind="smd")
land.pad("1", at=(mm(-2), mm(-1.5)), size=(mm(1.2), mm(0.8)))
land.pad("2", at=(mm(-2), mm(0)), size=(mm(1.2), mm(0.8)))
land.pad("3", at=(mm(-2), mm(1.5)), size=(mm(1.2), mm(0.8)))
land.pad("4", at=(mm(1.5), mm(0)), size=(mm(2), mm(3.6)))
land.rect((mm(-3), mm(-2.3)), (mm(3), mm(2.3)), layer="F.CrtYd", width=mm(0.05))
land.rect((mm(-1), mm(-2.1)), (mm(0.2), mm(2.1)), layer="F.SilkS", width=mm(0.12))
design.add_footprint(land)

# The symbol: three passive pins.
sensor = Symbol("Local", "Sensor", reference="U", footprint=land.lib_id)
sensor.pin("1", "VDD", etype="passive", at=(mm(-7.62), mm(2.54)), length=mm(2.54))
sensor.pin("2", "GND", etype="passive", at=(mm(-7.62), mm(0)), length=mm(2.54))
sensor.pin("3", "OUT", etype="passive", at=(mm(-7.62), mm(-2.54)), length=mm(2.54))
sensor.rect((mm(-5.08), mm(-5.08)), (mm(5.08), mm(5.08)))

j1 = Part("J1", "Fenolite:Connector_3", footprint="Fenolite:Header_1x3_P2.54", value="SENSOR")
# Pin 2 is bonded to the pad 2 and to the large pad 4; the pins 1 and 3 take the pads of their number.
u1 = Part("U1", sensor.lib_id, value="SENSOR", pad_map={"2": ("2", "4")})
design.add(sensor, j1, u1)

vdd, gnd, out = Net("VDD"), Net("GND"), Net("OUT")
connect(vdd, j1[1], u1[1])
connect(gnd, j1[2], u1[2])
connect(out, j1[3], u1[3])

j1.place(mm(6), mm(10), rot=180)
u1.place(mm(18), mm(10))

design.track("vdd", j1.pad(1), u1.pad(1), width=mm(0.25))
design.track("gnd", j1.pad(2), u1.pad(2), u1.pad(4), width=mm(0.25))
design.track("out", j1.pad(3), u1.pad(3), width=mm(0.25))
