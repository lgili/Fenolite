# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The half-bridge reference board of the net roles (change c0222; ``docs/roles.md``, "Reference boards"),
shared by ``good.py`` and ``bad.py``.

A half-bridge on a 70 mm by 50 mm four-layer board: the bus terminal ``J1`` and the bus capacitor ``C1``,
the switches ``Q1`` (high side) and ``Q2`` (low side) in a package with a Kelvin source, their driver ``U2``
with its bootstrap capacitor ``C2``, the low-side shunt ``R1`` sensed by the amplifier ``U3``, the output
terminal ``J2`` and the control header ``J3``. The power copper is ordinary zones of the script; the ground
is a plane on ``B.Cu``.

- ``good``: each gate goes out on ``F.Cu`` and returns on ``In1.Cu`` under it from the Kelvin-source pad;
  the shunt is sensed by a coupled pair; the bus carries 20 A on a pour.
- ``bad``: the high side's gate return leaves from the source pour; the low side's gate trace takes a detour
  that encloses over three times its placement bound; the sense pair crosses a pour of the switch node on
  ``In1.Cu``; the bus reaches the high side through one via.

Every value is a round illustrative number, not a design recommendation. Positions are millimetres in the
frame of ``place()``.
"""

from fenolite.dsl import Design, Net, Part, Power, amp, connect, mm, via_step, volt

VIA = {"diameter": mm("0.6"), "drill": mm("0.3")}
BLIND = {"diameter": mm("0.6"), "drill": mm("0.3"), "kind": "blind"}


def p(x: float, y: float) -> tuple[int, int]:
    """A point in millimetres."""
    return (mm(str(x)), mm(str(y)))


def ring(*points: tuple[float, float]) -> tuple[tuple[int, int], ...]:
    return tuple(p(x, y) for x, y in points)


def make(design: Design, variant: str, *, power: bool = True) -> Design:
    """Draws the ``variant`` board into ``design``, which the variant script makes. With ``power=False`` the
    power, switch-node, ground and high-voltage copper is left out (the role-copper scripts, change c0243,
    call ``design.role_copper()`` instead); the signal, gate and Kelvin copper stays."""
    good = variant == "good"
    design.board(mm(70), mm(50), copper=4)
    j1 = Part("J1", "Fenolite:Connector_2", footprint="Roles:Roles_Terminal_2P", value="BUS 400V")
    c1 = Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_1812_TDK_CGA8", value="1uF")
    q1 = Part("Q1", "Roles:Roles_NMOS_Kelvin", value="NMOS")
    q2 = Part("Q2", "Roles:Roles_NMOS_Kelvin", value="NMOS")
    r1 = Part("R1", "Fenolite:Resistor", footprint="Roles:Roles_Shunt_2512", value="10m")
    u2 = Part("U2", "Roles:Roles_HalfBridge_Driver", footprint="Fenolite:SOIC_8", value="DRIVER")
    c2 = Part("C2", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="100nF")
    u3 = Part("U3", "Roles:Roles_Sense_Amplifier", footprint="Fenolite:SOT23_5", value="AMP")
    c4 = Part("C4", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="100nF")
    j2 = Part("J2", "Fenolite:Connector_2", footprint="Roles:Roles_Terminal_2P", value="PHASE")
    j3 = Part("J3", "Fenolite:Connector_4", footprint="Fenolite:Header_1x4_P2.54", value="CONTROL")
    design.add(j1, c1, q1, q2, r1, u2, c2, u3, c4, j2, j3)
    vbus, gnd, sw, src = Net("VBUS"), Net("GND"), Net("SW"), Net("SRC")
    gh, gl, vboot, vdrv, isns, pwm_h, pwm_l = (
        Net("GH"), Net("GL"), Net("VBOOT"), Net("VDRV"), Net("ISNS"), Net("PWM_H"), Net("PWM_L"),
    )  # fmt: skip
    connect(vbus, j1[1], c1[1], q1["D"])
    connect(gnd, j1[2], c1[2], r1[2], j2[2], u3["GND"], c4[2])
    connect(sw, q1["S"], q1["KS"], q2["D"], u2["HS"], c2[2], j2[1])
    connect(src, q2["S"], q2["KS"], r1[1], u2["COM"], u3["IN+"])
    connect(gnd, u3["IN-"])
    connect(gh, u2["HO"], q1["G"])
    connect(gl, u2["LO"], q2["G"])
    connect(vboot, u2["VB"], c2[1])
    connect(vdrv, j3[1], u2["VCC"], u3["VCC"], c4[1])
    connect(pwm_h, j3[2], u2["HIN"])
    connect(pwm_l, j3[3], u2["LIN"])
    connect(isns, j3[4], u3["OUT"])
    design.add(Power(vbus, gnd))
    # the bus: 20 A at 400 V (illustrative), and the current of one of its vias (an illustrative via size)
    design.net_role(vbus, "power", current=amp(20), voltage=volt(400))
    design.role_limits(net=vbus, milliamps_per_via=amp(4))
    design.rules.netclass("BUS", clearance=mm("1.5"), track_width=mm(1), nets=(vbus,))
    design.rules.netclass("POWER", clearance=mm("0.3"), track_width=mm(1), nets=(gnd, sw, src))
    design.rules.netclass(
        "SIGNAL",
        clearance=mm("0.2"),
        track_width=mm("0.25"),
        via_diameter=mm("0.6"),
        via_drill=mm("0.3"),
        nets=(gh, gl, vboot, vdrv, isns, pwm_h, pwm_l),
    )

    def zone(net: Net, name: str, *points: tuple[float, float], layer: str = "F.Cu") -> None:
        if not power:
            return  # every zone of this board is power, switch-node or ground copper
        design.zone(
            net, layers=(layer,), name=name, outline=ring(*points), clearance=mm("0.3"), connection="solid"
        )

    q1.place(mm(22), mm(14), rot=180)  # drain tab left; gate, Kelvin source and source on the right
    q2.place(mm(22), mm(34), rot=180)
    r1.place(mm("35.5"), mm(36))
    u2.place(mm(46), mm(20), rot=180)  # VB, HO, HS and LO face the switches
    c2.place(mm("43.2"), mm("15.6"))
    u3.place(mm("35.5"), mm(43))
    c4.place(mm(40), mm(44), rot=90)
    j1.place(mm(12), mm("4.5"))
    j1.field("Reference", outside="bottom")
    j2.place(mm(6), mm(33), rot=90)
    j3.place(mm(64), mm(30), rot=180)
    c1.place(mm(11), mm(21), rot=270)
    # the ground plane on B.Cu, clear of the bus terminal by more than the bus clearance
    zone(gnd, "GND_PLANE", (11.2, 1), (69, 1), (69, 24.9), (62.6, 24.9), (62.6, 35.1), (69, 35.1), (69, 49),
         (1, 49), (1, 40.9), (8.9, 40.9), (8.9, 35.1), (1, 35.1), (1, 8.7), (11.2, 8.7),
         layer="B.Cu")  # fmt: skip
    zone(gnd, "GND_SHUNT", (38.4, 33.9), (42.6, 33.9), (42.6, 38.1), (38.4, 38.1))
    zone(src, "SRC", (27.2, 31.85), (28.3, 31.85), (28.3, 33.3), (32.6, 33.3), (32.6, 41.4), (27.2, 41.4))
    if power:
        design.via("gnd_shunt", *p(41.8, 36.0), net=gnd, **VIA)
        design.via("gnd_c1", *p(11, 24.6), net=gnd, **VIA)
        design.track("gnd_c1t", c1.pad(2), p(11, 24.6), width=mm("0.6"))
    # the driver: bootstrap, supply and inputs
    design.track("vb", u2.pad(8), p(42.4, 18.095), p(42.4, 15.6), c2.pad(1), width=mm("0.25"))
    design.track("hs_boot", c2.pad(2), p(45.5, 15.6), p(45.5, 20.635), u2.pad(6), width=mm("0.4"))
    design.track("vcc", u2.pad(1), p(56.5, 18.095), p(56.5, 26.19), j3.pad(1), width=mm("0.4"))
    design.track("hin", u2.pad(2), p(55, 19.365), p(55, 28.73), j3.pad(2), width=mm("0.25"))
    design.track("lin", u2.pad(3), p(54, 20.635), p(54, 31.27), j3.pad(3), width=mm("0.25"))
    design.track("isns", u3.pad(1), p(34.2, 48.0), p(62.5, 48.0), p(62.5, 33.81), j3.pad(4), width=mm("0.25"))
    design.track("vdrv_u3", u3.pad(5), p(38.5, 43.95), c4.pad(1), width=mm("0.4"))
    design.track(
        "vdrv_c4", c4.pad(1), via_step(*p(41.5, 44.8), to="In2.Cu", **BLIND), p(58.5, 44.8), p(58.5, 26.19),
        j3.pad(1), width=mm("0.4"),
    )  # fmt: skip
    design.via("gnd_u3", *p(32.8, 43.0), net=gnd, **VIA)
    design.track("gnd_u3t", u3.pad(2), p(32.8, 43.0), width=mm("0.4"))
    design.via("gnd_c4", *p(41.4, 43.2), net=gnd, **VIA)
    design.track("gnd_c4t", c4.pad(2), p(41.4, 43.2), width=mm("0.4"))
    # the high side's gate out on F.Cu
    design.track("gh", u2.pad(7), p(38.0, 19.365), p(38.0, 11.0), q1.pad(1), width=mm("0.25"))
    # the low side's gate out on F.Cu and its return under it on In1.Cu, from the Kelvin-source pad
    design.track(
        "gl_ret", q2.pad(2), via_step(*p(30.6, 32.5), to="In1.Cu", **BLIND), p(30.6, 31.0), p(37.0, 31.0),
        p(37.0, 21.905), p(44.5, 21.905), p(44.5, 23.4), via_step(*p(48.7, 23.4), to="F.Cu", **BLIND),
        u2.pad(4), width=mm("0.25"),
    )  # fmt: skip
    zone(sw, "SW", (25.7, 11.85), (28.3, 11.85), (28.3, 13.4), (29.9, 13.4), (29.9, 14.0), (33.5, 14.0),
         (33.5, 30.0), (26.8, 30.0), (26.8, 41.6), (3.0, 41.6), (3.0, 33.6), (13.6, 33.6), (13.6, 22.2),
         (25.7, 22.2))  # fmt: skip
    # the sense pair from the inner halves of the shunt's pads
    design.track(
        "sense_p", r1.pad(1).at(mm("0.5")), p(33.1, 38.5), p(34.2, 39.6), u3.pad(3), width=mm("0.25")
    )
    design.track(
        "sense_n", r1.pad(2).at(mm("-0.5")), p(37.9, 38.5), p(36.8, 39.6), u3.pad(4), width=mm("0.25")
    )
    if good:
        _good(design, q1, q2, u2, vbus, zone)
    else:
        _bad(design, j1, q1, q2, u2, vbus, sw, zone, power)
    return design


def _good(design, q1, q2, u2, vbus, zone):  # type: ignore[no-untyped-def]
    """The bus on one pour; each gate trace with its return under it from the Kelvin-source pad."""
    zone(vbus, "VBUS", (1.5, 1.5), (12.8, 1.5), (12.8, 8.5), (24.1, 8.5), (24.1, 20.6), (1.5, 20.6))
    design.track(
        "gh_ret", q1.pad(2), via_step(*p(30.6, 12.5), to="In1.Cu", **BLIND), p(30.6, 11.0), p(38.0, 11.0),
        p(38.0, 20.635), via_step(*p(39.6, 20.635), to="F.Cu", **BLIND), u2.pad(6), width=mm("0.25"),
    )  # fmt: skip
    design.track("gl", u2.pad(5), p(37.0, 21.905), p(37.0, 31.0), q2.pad(1), width=mm("0.25"))


def _bad(design, j1, q1, q2, u2, vbus, sw, zone, power):  # type: ignore[no-untyped-def]
    """The bus reaches the high side's pour through one via; the high side's Kelvin-source pad is tied to the
    source pour and its gate return leaves from that pour; the low side's gate trace takes a detour; a pour
    of the switch node on ``In1.Cu`` lies under the sense pair."""
    zone(vbus, "VBUS", (1.5, 9.5), (24.1, 9.5), (24.1, 20.6), (1.5, 20.6))
    if power:
        design.track("vbus_in", j1.pad(1), p(7.0, 6.0), p(7.0, 14.0), layer="In2.Cu", width=mm(8), net=vbus)
        design.via("vbus_via", *p(7.0, 14.0), net=vbus, **BLIND, layers=("F.Cu", "In2.Cu"))
        design.track("vbus_top", p(7.0, 14.0), p(7.0, 12.0), width=mm(8), net=vbus)
    design.track("ks_tie", q1.pad(2), p(27.0, 12.5), width=mm("0.25"))
    design.via("gh_ret_via", *p(31.0, 14.6), net=sw, **BLIND, layers=("F.Cu", "In1.Cu"))
    design.track(
        "gh_ret", p(31.0, 14.6), p(31.0, 11.0), p(38.0, 11.0), p(38.0, 20.635),
        via_step(*p(39.6, 20.635), to="F.Cu", **BLIND), u2.pad(6), layer="In1.Cu", width=mm("0.25"),
    )  # fmt: skip
    design.track(
        "gl", u2.pad(5), p(42.0, 21.905), p(42.0, 26.0), p(52.0, 26.0), p(52.0, 33.0), p(37.0, 33.0),
        p(37.0, 31.0), q2.pad(1), width=mm("0.25"),
    )  # fmt: skip
    zone(sw, "SW_UNDER", (25.4, 37.6), (39.5, 37.6), (39.5, 41.4), (25.4, 41.4), layer="In1.Cu")
    if power:
        design.via("sw_under", *p(25.8, 40.5), net=sw, **BLIND, layers=("F.Cu", "In1.Cu"))
