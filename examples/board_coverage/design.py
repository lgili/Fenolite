# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Board coverage: one of each board item of change c0277 on the blink circuit, on a four-layer board.

Copper art (a knockout text on ``F.Cu`` and a ``GND`` heat spreader), user layers, a radial dimension, a
leader and a centre mark, a zone whose outline has an arc, a placement rule area, a group, a board image
read from ``logo.png`` beside this script, teardrops on the power class and on one via, a free via, a part
not populated, a footprint with a trapezoid, a chamfered, a rounded and a custom pad, the overrides and an
edited pad of one instance, a bold reference, a 3D model by name, and verbatim items for what no call
says. Every value is a round number chosen for this example.

Build it with ``fenolite build examples/board_coverage/design.py --out build/coverage --confirm``.
"""

from fenolite.dsl import Design, Footprint, Net, Part, Power, arc_to, connect, mm, select, teardrop
from fenolite.dsl.footprint import circle, poly, segment

design = Design("coverage")
design.board(mm(50), mm(30), copper=4)
design.user_layers(2, names={"User.2": "Notes"})

pads = Footprint("Local", "Shaped_Pads", kind="smd")
pads.pad("1", at=(mm(-3), mm(0)), size=(mm(1), mm(2)), shape="trapezoid", delta=(mm("0.2"), mm(0)))
pads.pad("2", at=(mm(-1), mm(0)), size=(mm(1), mm(1)), shape="rect", chamfer=250_000, corners=("top_left",))
pads.pad("3", at=(mm(1), mm(0)), size=(mm(1), mm(1)), shape="roundrect", radius_ratio=200_000)
pads.pad(
    "4",
    at=(mm(3), mm(0)),
    size=(mm("0.5"), mm("0.5")),
    shape="custom",
    anchor="circle",
    primitives=(
        poly(((mm("-0.4"), mm("-0.4")), (mm("0.4"), mm("-0.4")), (mm("0.4"), mm("0.4")))),
        segment((mm(0), mm(0)), (mm("0.6"), mm(0)), width=mm("0.2")),
        circle((mm("0.6"), mm(0)), mm("0.15")),
    ),
)
pads.rect((mm(-4), mm(-1.5)), (mm(4), mm(1.5)), layer="F.CrtYd", width=mm("0.05"))
design.add_footprint(pads)

u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")
d1 = Part("D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED")
r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="10k", dnp=True)
j1 = Part("J1", "Mini:Mini_R", footprint=pads.lib_id, value="PADS")
design.add(u1, r1, d1, r2, j1)

vin, gnd, led_drv, led_a = Net("VIN"), Net("GND"), Net("LED_DRV"), Net("LED_A")
connect(vin, u1[9], r2[1])
connect(gnd, u1[10], d1[1], r2[2], j1[2])
connect(led_drv, u1[1], r1[1])
connect(led_a, r1[2], d1[2])
connect(vin, j1[1])
u1.unused_no_connect()
design.add(Power(vin, gnd))
design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))

u1.place(mm(14), mm(15), locked=True)
r1.place(mm(32), mm(9))
d1.place(mm(38), mm(20), side="bottom")
r2.place(mm(32), mm(4))
j1.place(mm(25), mm(26))

# instance settings
u1.field("Reference", dx=mm(0), dy=mm(-6), bold=True, face="KiCad Font")
u1.model(
    "${KICAD10_3DMODEL_DIR}/Package_QFP.3dshapes/LQFP-32_7x7mm_P0.8mm.step", offset=(mm(0), mm(0), mm("0.1"))
)
j1.override(clearance=mm("0.15"), paste_ratio=-100_000)
j1.edit_pad("3", size=(mm("1.2"), mm("1.2")))

# copper art, drawings and dimensions
design.text("art/rev", "REV A", (mm(44), mm(27)), layer="F.Cu", knockout=True)
design.polygon("art/spreader", [(mm(4), mm(24)), (mm(9), mm(24)), (mm(9), mm(28)), (mm(4), mm(28))],
               layer="B.Cu", width=None, fill=True, net=gnd)  # fmt: skip
design.line("notes/line", (mm(1), mm(1)), (mm(10), mm(1)), layer="User.2", width=mm("0.1"))
design.radial_dimension("dim/radius", (mm(46), mm(4)), (mm(48), mm(4)), leader_length=mm(3))
design.leader("dim/note", (mm(20), mm(3)), (mm(23), mm(1)), text="NO PARTS", frame="rect")
design.center_mark("dim/centre", (mm(46), mm(4)), (mm(47), mm(4)))
design.image("art/logo", "logo.png", (mm(44), mm(22)), scale="0.5")

# zones, areas and the group
design.zone(
    gnd,
    layers=("In1.Cu",),
    outline=[(mm(1), mm(1)), (mm(49), mm(1)), arc_to((mm(48), mm(15)), (mm(49), mm(29))), (mm(1), mm(29))],
)
AREA = [(mm(28), mm(2)), (mm(36), mm(2)), (mm(36), mm(12)), (mm(28), mm(12))]
design.rule_area("auto-placement-area-/driver/", AREA, placement="/driver/")
design.group("art", "art/rev", "art/spreader", "art/logo")

# vias and teardrops
design.via(
    "tv", mm(5), mm(26), net=gnd, diameter=mm("0.6"), drill=mm("0.3"), teardrop=teardrop(max_length=mm(1))
)
design.via("stitch", mm(10), mm(26), net=gnd, diameter=mm("0.6"), drill=mm("0.3"), free=True)
design.teardrops(where=select.netclass("PWR"), length_ratio=500_000)

# what no call says: a fiducial target and a custom rule
design.verbatim("art/target", '(target plus (at 148 102) (size 2) (width 0.1) (layer "Edge.Cuts"))')
design.verbatim("rule/edge", '(rule "edge" (constraint edge_clearance (min 0.4mm)))', target="kicad_dru")
