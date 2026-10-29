# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The buck reference board of the net roles (change c0222; ``docs/roles.md``, "Reference boards"), shared
by ``good.py``, ``bad.py`` and ``open.py``.

A synchronous buck on a 60 mm by 40 mm two-layer board: the input terminal ``J1`` and the input capacitor
``C1``, the switches ``Q1`` (high side) and ``Q2`` (low side) with their driver ``U1``, the inductor ``L1``,
the output shunt ``R12`` sensed by the amplifier ``U3``, the output capacitor ``C3`` and the output
terminal ``J2``. The power copper is ordinary zones of the script (``zone()``), so both build targets build
the same file.

- ``good``: ``C1`` stands across the switch pair; the switch node is a compact pour; ``R12`` is sensed from
  the inner halves of its pads as a pair; every power net is a pour.
- ``bad``: ``C1`` stands 15 mm away and its return runs apart from its supply, so the hot loop encloses
  about 180 mm²; one sense line leaves the outer end of ``R12``'s pad and the other leaves the output pour;
  the output path narrows to a 0.3 mm track.
- ``open`` (change c0244): ``bad`` without its critical copper, the two sense lines, for the critical routes
  of ``fenolite route --roles critical`` to draw; the hot loop and the narrow output track stay, since they
  are power copper (phase 1).

Every value is a round illustrative number, not a design recommendation. Positions are millimetres in the
frame of ``place()``.
"""

from fenolite.dsl import Design, Net, Part, Power, amp, connect, mm, via_step

VIA = {"diameter": mm("0.6"), "drill": mm("0.3")}


def p(x: float, y: float) -> tuple[int, int]:
    """A point in millimetres."""
    return (mm(str(x)), mm(str(y)))


def ring(*points: tuple[float, float]) -> tuple[tuple[int, int], ...]:
    return tuple(p(x, y) for x, y in points)


def make(design: Design, variant: str) -> Design:
    """Draws the ``variant`` board (``good``, ``bad`` or ``open``) into ``design``, which the variant script
    makes."""
    if variant not in ("good", "bad", "open"):
        raise ValueError(f"unknown variant {variant!r}")
    good = variant == "good"
    design.board(mm(60), mm(40))
    j1 = Part("J1", "Fenolite:Connector_2", footprint="Roles:Roles_Terminal_2P", value="VIN 12V")
    c1 = Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_1206", value="10uF")
    q1 = Part("Q1", "Roles:Roles_NMOS", value="NMOS")
    q2 = Part("Q2", "Roles:Roles_NMOS", value="NMOS")
    l1 = Part("L1", "Fenolite:Inductor", footprint="Roles:Roles_Inductor_7x7", value="4.7uH")
    r12 = Part("R12", "Fenolite:Resistor", footprint="Roles:Roles_Shunt_2512", value="5m")
    c3 = Part("C3", "Fenolite:Capacitor", footprint="Fenolite:Chip_1206", value="22uF")
    j2 = Part("J2", "Fenolite:Connector_2", footprint="Roles:Roles_Terminal_2P", value="VOUT 5V")
    u1 = Part("U1", "Roles:Roles_HalfBridge_Driver", footprint="Fenolite:SOIC_8", value="DRIVER")
    u3 = Part("U3", "Roles:Roles_Sense_Amplifier", footprint="Fenolite:SOT23_5", value="AMP")
    j3 = Part("J3", "Fenolite:Connector_4", footprint="Fenolite:Header_1x4_P2.54", value="CONTROL")
    c4 = Part("C4", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="1uF")
    c5 = Part("C5", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="100nF")
    c6 = Part("C6", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="100nF")
    design.add(j1, c1, q1, q2, l1, r12, c3, j2, u1, u3, j3, c4, c5, c6)
    vin, gnd, sw, vl, vout = Net("VIN"), Net("GND"), Net("SW"), Net("VL"), Net("VOUT")
    gh, gl, vb, vdrv, isns = Net("GH"), Net("GL"), Net("VB"), Net("VDRV"), Net("ISNS")
    pwm_h, pwm_l = Net("PWM_H"), Net("PWM_L")
    connect(vin, j1[1], c1[1], q1["D"])
    connect(gnd, j1[2], c1[2], q2["S"], c3[2], j2[2], u1["COM"], u3["GND"], c4[2], c5[2])
    connect(sw, q1["S"], q2["D"], l1[1], u1["HS"], c6[2])
    connect(vl, l1[2], r12[1], u3["IN+"])
    connect(vout, r12[2], c3[1], j2[1], u3["IN-"])
    connect(gh, u1["HO"], q1["G"])
    connect(gl, u1["LO"], q2["G"])
    connect(vb, u1["VB"], c6[1])
    connect(vdrv, j3[1], u1["VCC"], u3["VCC"], c4[1], c5[1])
    connect(pwm_h, j3[2], u1["HIN"])
    connect(pwm_l, j3[3], u1["LIN"])
    connect(isns, j3[4], u3["OUT"])
    design.add(Power(vin, gnd), Power(vout, gnd, name="VOUT/GND"))
    # the roles the script knows: the currents (illustrative); everything else is inferred
    design.net_role(vin, "power", current=amp(1))
    design.net_role(sw, "switch_node", current=amp(2))
    design.net_role(vl, "power", current=amp(2))
    design.net_role(vout, "power", current=amp(2))
    design.rules.netclass("POWER", clearance=mm("0.3"), track_width=mm(1), nets=(vin, gnd, sw, vl, vout))
    design.rules.netclass(
        "SIGNAL",
        clearance=mm("0.2"),
        track_width=mm("0.25"),
        via_diameter=mm("0.6"),
        via_drill=mm("0.3"),
        nets=(gh, gl, vb, vdrv, isns, pwm_h, pwm_l),
    )

    def zone(net: Net, name: str, *points: tuple[float, float], layer: str = "F.Cu") -> None:
        design.zone(
            net, layers=(layer,), name=name, outline=ring(*points), clearance=mm("0.3"), connection="solid"
        )

    # --- placement and copper shared by both variants
    q2.place(mm(18), mm(12), rot=270)  # low side: source up, gate at the upper left, drain tab down
    q1.place(mm(27), mm(12), rot=90)  # high side: drain tab up, source down, gate at the lower right
    u1.place(mm(8), mm(24))
    c6.place(mm(12), mm(28))
    c6.field("Reference", outside="bottom")
    c4.place(mm(3), mm(21), rot=90)
    j3.place(mm(10), mm(37), rot=90)
    l1.place(mm(22), mm("21.5"), rot=270)
    r12.place(mm(30), mm(26))
    u3.place(mm(30), mm(31))
    c5.place(mm("25.8"), mm("32.5"), rot=90)
    c3.place(mm(44), mm(26), rot=90)
    j2.place(mm(54), mm(26), rot=90)
    zone(sw, "SW", (15.4, 10.5), (20.6, 10.5), (20.6, 13.85), (28.15, 13.85), (28.15, 19.6), (15.4, 19.6))
    # the low side's gate: up and left of the switches, then down to LO; its return runs under it on B.Cu
    design.track("gl", q2.pad(2), p(11.6, 9.2), p(11.6, 22.095), u1.pad(5), width=mm("0.25"))
    # the signal ground hangs from the source pad of the low side through a via in that pad, so no power
    # current shares it; it runs under the low side's gate on B.Cu
    design.via("gnd_q2", *p(17.6, 9.2), net=gnd, **VIA)
    design.track(
        "gnd_gl",
        p(17.6, 9.2),
        p(11.6, 9.2),
        p(11.6, 21.0),
        p(5.3, 21.0),
        layer="B.Cu",
        net=gnd,
        width=mm("0.4"),
    )
    design.via("gnd_com", *p(5.3, 21.0), net=gnd, **VIA)
    # the high side's gate: under the switch node on B.Cu, then beside the HS track to HO
    design.track(
        "gh", q1.pad(2), via_step(*p(28.9, 17.2), to="B.Cu", **VIA), p(14.2, 17.2),
        via_step(*p(14.2, 24.635), to="F.Cu", **VIA), u1.pad(7), width=mm("0.25"),
    )  # fmt: skip
    design.track("hs", p(15.6, 19.0), p(15.6, 23.365), u1.pad(6), width=mm("0.4"))
    design.track("hs_boot", p(15.6, 23.365), p(15.6, 28.0), c6.pad(2), width=mm("0.4"))
    design.track("vb", u1.pad(8), p(11.2, 26.6), c6.pad(1), width=mm("0.25"))
    # the driver's supply, ground and inputs
    design.track("vdrv_u1", c4.pad(1), p(3, 25.905), u1.pad(1), width=mm("0.4"))
    design.track("vdrv_j3", p(3, 25.905), p(3, 30), p(13.81, 30), p(13.81, 34.6), j3.pad(1), width=mm("0.4"))
    design.track("vdrv_u3", p(13.81, 34.6), p(25.8, 34.6), p(31.3, 34.6), u3.pad(5), width=mm("0.4"))
    design.track("vdrv_c5", c5.pad(1), p(25.8, 34.6), width=mm("0.4"))
    design.track("gnd_c4", c4.pad(2), p(5.3, 20.2), u1.pad(4), width=mm("0.4"))
    design.track(
        "pwm_l", j3.pad(3), p(8.73, 32), p(6.6, 29.87), via_step(*p(6.6, 23.365), to="F.Cu", **VIA),
        u1.pad(3), layer="B.Cu", width=mm("0.25"),
    )  # fmt: skip
    design.track(
        "pwm_h", j3.pad(2), p(11.27, 32), p(7.6, 28.33), via_step(*p(7.6, 24.635), to="F.Cu", **VIA),
        u1.pad(2), layer="B.Cu", width=mm("0.25"),
    )  # fmt: skip
    # the amplifier's ground and output
    design.track("gnd_u3", u3.pad(2), p(27.4, 31.0), p(26.9, 31.0), p(26.9, 31.7), c5.pad(2), width=mm("0.4"))
    design.via("gnd_u3v", *p(27.4, 31.0), net=gnd, **VIA)
    design.track("gnd_b", p(27.4, 31.0), p(12.5, 31.0), p(12.5, 21.0), p(11.6, 21.0), layer="B.Cu", net=gnd,
                 width=mm("0.4"))  # fmt: skip
    design.track(
        "isns", u3.pad(1), via_step(*p(28.7, 33.4), to="B.Cu", **VIA), p(28.7, 38.6), p(6.19, 38.6),
        j3.pad(4), width=mm("0.25"),
    )  # fmt: skip
    design.via("gnd_out", *p(41, 15), net=gnd, **VIA)
    if good:
        _good(design, j1, c1, r12, u3, vin, gnd, vl, vout, zone)
    else:
        _bad(design, j1, c1, r12, u3, vin, gnd, vl, vout, zone, sense=variant == "bad")
    return design


def _good(design, j1, c1, r12, u3, vin, gnd, vl, vout, zone):  # type: ignore[no-untyped-def]
    """``C1`` across the switch pair, pours for every power net, the shunt sensed from its inner halves."""
    j1.place(mm(10), mm(5))
    c1.place(mm("22.5"), mm(6), rot=180)
    zone(gnd, "GND_OUT", (40, 14), (57.5, 14), (57.5, 25.1), (43.1, 25.1), (43.1, 23.4), (40, 23.4))
    zone(vin, "VIN", (1.5, 1.0), (31.6, 1.0), (31.6, 13.45), (23.0, 13.45), (23.0, 2.1), (8.5, 2.1),
         (8.5, 8.0), (1.5, 8.0))  # fmt: skip
    zone(gnd, "GND", (12.0, 2.5), (22.6, 2.5), (22.6, 10.05), (16.85, 10.05), (16.85, 8.0), (12.0, 8.0))
    # the output ground joins the switches' ground on B.Cu, apart from the signal ground
    design.via("gnd_in", *p(22.0, 4.1), net=gnd, **VIA)
    design.track("gnd_top", p(22.0, 4.1), p(41, 4.1), p(41, 15), layer="B.Cu", net=gnd, width=mm(1))
    zone(vl, "VL", (19.4, 23.2), (27.1, 23.2), (27.1, 28.2), (19.4, 28.2))
    zone(vout, "VOUT", (32.9, 23.8), (42.7, 23.8), (42.7, 25.5), (57.5, 25.5), (57.5, 36.5), (35.0, 36.5),
         (35.0, 28.3), (32.9, 28.3))  # fmt: skip
    # the sense pair: from the inner half of each shunt pad, converging to the amplifier
    design.track(
        "sense_p", r12.pad(1).at(mm("0.5")), p(27.6, 28.6), p(28.7, 29.7), u3.pad(3), width=mm("0.25")
    )
    design.track(
        "sense_n", r12.pad(2).at(mm("-0.5")), p(32.4, 28.6), p(31.3, 29.7), u3.pad(4), width=mm("0.25")
    )


def _bad(design, j1, c1, r12, u3, vin, gnd, vl, vout, zone, sense=True):  # type: ignore[no-untyped-def]
    """``C1`` 15 mm away with its supply and its return apart, the sense lines from the outer end of one pad
    and from the output pour (left out without ``sense``), and the output path through a 0.3 mm track."""
    j1.place(mm(44), mm(6))
    c1.place(mm("4.5"), mm(9), rot=270)
    zone(vin, "VIN", (23.0, 1.2), (41.6, 1.2), (41.6, 13.45), (23.0, 13.45))
    zone(gnd, "GND", (16.85, 7.2), (22.6, 7.2), (22.6, 10.05), (16.85, 10.05))
    zone(gnd, "GND_OUT", (42, 1.2), (57.5, 1.2), (57.5, 25.1), (43.1, 25.1), (43.1, 23.4), (40, 23.4),
         (40, 14), (42, 14))  # fmt: skip
    design.track("vin_c1", c1.pad(1), p(4.5, 1.8), p(23.5, 1.8), width=mm(1))
    design.via("gnd_in", *p(22.0, 7.6), net=gnd, **VIA)
    design.track(
        "gnd_top", p(22.0, 7.6), p(35, 7.6), p(35, 15), p(41, 15), layer="B.Cu", net=gnd, width=mm(1)
    )
    design.track("gnd_c1", p(17.5, 7.6), p(8.5, 7.6), p(8.5, 10.45), c1.pad(2), width=mm(1))
    zone(vl, "VL", (19.4, 23.2), (26.3, 23.2), (26.3, 28.2), (19.4, 28.2))
    zone(vout, "VOUT", (36.5, 23.8), (42.7, 23.8), (42.7, 25.5), (57.5, 25.5), (57.5, 36.5), (33.2, 36.5),
         (33.2, 28.4), (36.5, 28.4))  # fmt: skip
    design.track("vout_narrow", r12.pad(2), p(37.0, 26.0), width=mm("0.3"))
    if not sense:
        return
    # the sense lines: one from the outer end of R12's pad 1, the other from the output pour
    design.track(
        "sense_p", r12.pad(1).at(mm("-0.55")), p(26.55, 29.2), p(27.2, 29.7), u3.pad(3),
        width=mm("0.25"),
    )  # fmt: skip
    design.track("sense_n", p(33.6, 29.0), p(32.0, 29.0), u3.pad(4), width=mm("0.25"))
