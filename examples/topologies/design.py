# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite; every geometry, timing and loss number is an illustrative user input.
"""An ordered clock through a series terminator and a protocol-constrained USB pair.

The catalog connectors stand for the signal endpoints. No protocol or stack-up default is implied.
"""

from fenolite.dsl import USB2, Design, Net, connect, db, fs, hertz, mdb, mm, protocol, ps

design = Design("topologies")
design.board(mm(55), mm(28))
loads = [design.part(f"U{i}", device="Fenolite:Conn_1x2_P2.54") for i in range(1, 5)]
r1 = design.part("R1", device="Fenolite:R_0402", value="33")
u1, u2, u3, u4 = loads
connect(Net("CLK_A"), u1[1], r1[1])
connect(Net("CLK_B"), r1[2], u2[1], u3[1], u4[1])
connect(Net("GND"), *(part[2] for part in loads))
design.bridge(r1, 1, 2, delay=fs(25), loss=mdb(2))

clk = design.topology("clk", u1[1] >> r1[1], r1[2] >> u2[1] >> u3[1] >> u4[1])
clk.delay(u1[1], u4[1], max=ps(900))
clk.skew(u2[1], u3[1], u4[1], max=ps(150))
clk.loss(u1[1], u4[1], max=db("1.5"))
clk.stub(max=mm(2))
clk.order()

j1 = design.part("J1", device="Fenolite:Conn_1x2_P2.54")
j2 = design.part("J2", device="Fenolite:Conn_1x2_P2.54")
usb = USB2(Net("USB_P"), Net("USB_N"), name="usb")
usb.attach(j1, dp=1, dn=2)
usb.attach(j2, dp=1, dn=2)
design.constrain(usb, protocol.Usb2(skew_max=ps(10), delay_max=ps(1_500), loss_max=db("1.5")))

# Illustrative inputs only: obtain real propagation and loss from the user's stack-up and frequency.
design.propagation("F.Cu", per_mm=fs(5_900))
design.propagation(via=fs(10_000))
design.loss("F.Cu", per_mm=mdb(4), at=hertz("1G"))
design.loss(via=mdb(2), at=hertz("1G"))

for part, x in zip(loads, (5, 25, 35, 45), strict=True):
    part.place(mm(x), mm(5))
r1.place(mm(15), mm(5))
j1.place(mm(5), mm(18))
j2.place(mm(45), mm(18))
for index, (a, b) in enumerate(
    ((u1.pad(1), r1.pad(1)), (r1.pad(2), u2.pad(1)), (u2.pad(1), u3.pad(1)), (u3.pad(1), u4.pad(1)))
):
    design.track(f"clock-{index}", a, b, width=mm("0.25"))
design.track("usb-p", j1.pad(1), j2.pad(1), width=mm("0.25"))
design.track("usb-n", j1.pad(2), j2.pad(2), width=mm("0.25"))
