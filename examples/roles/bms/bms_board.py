# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""The battery-management reference board of the net roles (change c0222; ``docs/roles.md``, "Reference
boards"), shared by ``good.py``, ``bad.py`` and ``open.py``.

A three-cell battery protector on an 80 mm by 40 mm two-layer board: the battery terminal ``J1``, the pack
terminal ``J3`` and the cell-tap header ``J2``; the pack current runs from the battery's negative through
the four-pad shunt ``R1`` and the back-to-back switches ``Q1`` (discharge) and ``Q2`` (charge), whose
sources meet, to the pack's negative. The cell monitor ``U1`` senses the shunt on its own pads, drives both
gates against its ``COM`` pin on the common source, and reads the cell taps over a ground plane on
``B.Cu``.

- ``good``: the shunt sensed on its sense pads; each gate trace with its return beside it from the
  Kelvin-source pad; the pack path on pours.
- ``bad``: the monitor senses the shunt on its force pads; the pack's negative narrows to a 1 mm track; a
  slot in the ground plane runs under the cell tap ``TAP0``.
- ``open`` (change c0244): ``bad`` without its critical copper, for ``fenolite route --roles critical`` to
  draw: the sense lines are left out, and the monitor's sense inputs are on the sense pads' nets, as in
  ``good`` (a netlist fault is not copper). The narrow pack neck and the slot stay, since they are power
  and ground copper (phase 1).

Every value is a round illustrative number, not a design recommendation. Positions are millimetres in the
frame of ``place()``.
"""

from fenolite.dsl import Design, Net, Part, amp, connect, mm

VIA = {"diameter": mm("0.6"), "drill": mm("0.3")}


def p(x: float, y: float) -> tuple[int, int]:
    """A point in millimetres."""
    return (mm(str(x)), mm(str(y)))


def ring(*points: tuple[float, float]) -> tuple[tuple[int, int], ...]:
    return tuple(p(x, y) for x, y in points)


def make(design: Design, variant: str, *, power: bool = True) -> Design:
    """Draws the ``variant`` board (``good``, ``bad`` or ``open``) into ``design``, which the variant script
    makes. With ``power=False`` the power and ground copper is left out (the role-copper scripts, change
    c0243, call ``design.role_copper()`` instead); the signal, gate and Kelvin copper stays."""
    if variant not in ("good", "bad", "open"):
        raise ValueError(f"unknown variant {variant!r}")
    good = variant == "good"
    sensed = variant != "bad"  # the monitor senses the shunt on its sense pads
    design.board(mm(80), mm(40))
    j1 = Part("J1", "Fenolite:Connector_2", footprint="Roles:Roles_Terminal_2P", value="BATTERY")
    j2 = Part("J2", "Fenolite:Connector_4", footprint="Fenolite:Header_1x4_P2.54", value="TAPS")
    j3 = Part("J3", "Fenolite:Connector_2", footprint="Roles:Roles_Terminal_2P", value="PACK")
    r1 = Part("R1", "Roles:Roles_Shunt_4T", value="1m")
    q1 = Part("Q1", "Roles:Roles_NMOS_Kelvin", value="NMOS")
    q2 = Part("Q2", "Roles:Roles_NMOS_Kelvin", value="NMOS")
    u1 = Part("U1", "Roles:Roles_Cell_Monitor", footprint="Fenolite:SOIC14_TI_D0014A", value="MONITOR")
    design.add(j1, j2, j3, r1, q1, q2, u1)
    bat_p, gnd, shunt_n, fet_s, pack_n = Net("BAT_P"), Net("GND"), Net("SHUNT_N"), Net("FET_S"), Net("PACK_N")
    chg_g, dsg_g = Net("CHG_G"), Net("DSG_G")
    sense = (Net("SNS_P"), Net("SNS_N")) if sensed else ()
    tap3, tap2, tap1, tap0 = Net("TAP3"), Net("TAP2"), Net("TAP1"), Net("TAP0")
    connect(bat_p, j1[1], j3[1], u1["BAT"])
    connect(gnd, j1[2], r1[1], u1["VSS"])
    connect(shunt_n, r1[4], q1["D"])
    connect(fet_s, q1["S"], q1["KS"], q2["S"], q2["KS"], u1["COM"])
    connect(pack_n, q2["D"], j3[2])
    if sensed:
        connect(sense[0], r1[2], u1["SRP"])
        connect(sense[1], r1[3], u1["SRN"])
    else:  # the monitor senses the shunt on its force pads
        connect(gnd, u1["SRP"])
        connect(shunt_n, u1["SRN"])
    connect(dsg_g, u1["DSG"], q1["G"])
    connect(chg_g, u1["CHG"], q2["G"])
    connect(tap3, j2[1], u1["VC3"])
    connect(tap2, j2[2], u1["VC2"])
    connect(tap1, j2[3], u1["VC1"])
    connect(tap0, j2[4], u1["VC0"])
    # the pack current (illustrative) and the cell taps, whose returns are judged
    for net in (bat_p, pack_n, shunt_n):
        design.net_role(net, "power", current=amp(20))
    design.net_role(gnd, "ground", current=amp(20))
    for net in (tap3, tap2, tap1, tap0):
        design.net_role(net, "signal", sensitive=True)
    design.rules.netclass(
        "PACK", clearance=mm("0.3"), track_width=mm(1), nets=(bat_p, gnd, shunt_n, fet_s, pack_n)
    )
    design.rules.netclass(
        "SIGNAL", clearance=mm("0.2"), track_width=mm("0.25"), via_diameter=mm("0.6"), via_drill=mm("0.3"),
        nets=(*sense, chg_g, dsg_g, tap3, tap2, tap1, tap0),
    )  # fmt: skip

    def zone(net: Net, name: str, *points: tuple[float, float], layer: str = "F.Cu") -> None:
        if not power:
            return  # every zone of this board is power or ground copper
        design.zone(
            net, layers=(layer,), name=name, outline=ring(*points), clearance=mm("0.3"), connection="solid"
        )

    j3.place(mm(8), mm(25), rot=90)
    j1.place(mm(72), mm(25), rot=90)
    q2.place(mm(24), mm(20), rot=180)  # drain left, gate, Kelvin source and source right
    q1.place(mm(42), mm(20))  # source, Kelvin source and gate left, drain right
    r1.place(mm(60), mm(20), rot=180)  # force pads 4 (left) and 1 (right), sense pads 3 and 2 above
    u1.place(mm(60), mm(7), rot=180)  # sense pins below, gate pins left, cell taps right
    j2.place(mm(72), mm(5), rot=270)
    # the pack path: pack negative, switches, shunt, battery negative; the positive along the bottom
    zone(fet_s, "FET_S", (29.2, 19.2), (31.3, 19.2), (31.3, 17.9), (31.8, 17.9), (31.8, 15.2), (36.8, 15.2),
         (36.8, 20.8), (35.2, 20.8), (35.2, 21.9), (34.2, 21.9), (34.2, 24.8), (29.2, 24.8))  # fmt: skip
    zone(
        shunt_n, "SHUNT_N", (39.7, 15.2), (56.8, 15.2), (56.8, 16.3), (57.2, 16.3), (57.2, 24.8), (39.7, 24.8)
    )
    zone(gnd, "GND", (63.2, 15.0), (78.0, 15.0), (78.0, 24.8), (62.8, 24.8), (62.8, 16.3), (63.2, 16.3))
    zone(bat_p, "BAT_P", (2.0, 26.0), (78.0, 26.0), (78.0, 36.0), (2.0, 36.0))
    design.track("bat", u1.pad(1), p(64.2, 3.19), p(64.2, 2.2), p(79.0, 2.2), p(79.0, 27.0), p(77.5, 27.0),
                 width=mm("0.25"))  # fmt: skip
    design.via("gnd_vss", *p(64.6, 9.54), net=gnd, **VIA)
    if power:
        design.via("gnd_plane", *p(64.6, 15.6), net=gnd, **VIA)  # the plane joins the battery negative's pour
    design.track("gnd_vss_t", u1.pad(6), p(64.6, 9.54), width=mm("0.25"))
    # the cell taps, over the ground plane on B.Cu
    design.track("tap3", j2.pad(1), p(68.19, 4.46), u1.pad(2), width=mm("0.25"))
    design.track("tap2", j2.pad(2), p(70.73, 6.3), p(64.4, 6.3), u1.pad(3), width=mm("0.25"))
    design.track("tap1", j2.pad(3), p(73.27, 7.0), u1.pad(4), width=mm("0.25"))
    design.track("tap0", j2.pad(4), p(75.81, 8.27), u1.pad(5), width=mm("0.25"))
    # each gate out on F.Cu, its return on B.Cu under it from the Kelvin-source pad to COM
    design.via("com", *p(55.4, 8.27), net=fet_s, **VIA)
    design.track("com_t", u1.pad(10), p(55.4, 8.27), width=mm("0.25"))
    design.track("dsg", u1.pad(9), p(38.2, 9.54), p(38.2, 23.0), q1.pad(1), width=mm("0.25"))
    design.via("ks1", *p(37.2, 21.5), net=fet_s, **VIA)
    design.track("ks1_t", q1.pad(2), p(37.2, 21.5), width=mm("0.25"))
    design.track(
        "dsg_ret", p(37.2, 21.5), p(38.2, 21.5), p(38.2, 9.54), p(55.4, 9.54), p(55.4, 8.27), layer="B.Cu",
        width=mm("0.25"), net=fet_s,
    )  # fmt: skip
    design.track("chg", u1.pad(11), p(30.5, 7.0), q2.pad(1), width=mm("0.25"))
    design.via("ks2", *p(28.6, 18.5), net=fet_s, **VIA)
    design.track("ks2_t", q2.pad(2), p(28.6, 18.5), width=mm("0.25"))
    design.track(
        "chg_ret", p(28.6, 18.5), p(28.6, 7.0), p(55.4, 7.0), p(55.4, 8.27), layer="B.Cu", width=mm("0.25"),
        net=fet_s,
    )  # fmt: skip
    if good:
        _good(design, gnd, pack_n, zone, r1, u1)
    else:
        _bad(design, gnd, pack_n, zone, u1, power, sense=variant == "bad")
    return design


def _good(design, gnd, pack_n, zone, r1, u1):  # type: ignore[no-untyped-def]
    """The shunt sensed on its sense pads, the pack's negative on one pour, an unbroken ground plane."""
    zone(gnd, "GND_PLANE", (56.2, 1.0), (66.9, 1.0), (66.9, 13.6), (65.3, 13.6), (65.3, 17.5), (63.4, 17.5),
         (63.4, 13.6), (56.2, 13.6), layer="B.Cu")  # fmt: skip
    zone(pack_n, "PACK_N", (2.0, 15.0), (26.3, 15.0), (26.3, 24.8), (2.0, 24.8))
    design.track("sns_p", r1.pad(2), p(62.7, 12.6), u1.pad(7), width=mm("0.25"))
    design.track("sns_n", r1.pad(3), p(57.3, 12.6), u1.pad(8), width=mm("0.25"))


def _bad(design, gnd, pack_n, zone, u1, power, sense=True):  # type: ignore[no-untyped-def]
    """The monitor senses the shunt on its force pads (the lines left out without ``sense``); the pack's
    negative narrows to a 1 mm track between two pours; a slot in the ground plane runs under the tap
    ``TAP0``."""
    zone(gnd, "GND_PLANE", (56.2, 1.0), (66.9, 1.0), (66.9, 13.6), (66.4, 13.6), (66.4, 7.65), (65.6, 7.65),
         (65.6, 13.6), (65.3, 13.6), (65.3, 17.5), (63.4, 17.5), (63.4, 13.6), (56.2, 13.6),
         layer="B.Cu")  # fmt: skip
    zone(pack_n, "PACK_IN", (2.0, 15.0), (11.6, 15.0), (11.6, 24.8), (2.0, 24.8))
    zone(pack_n, "PACK_N", (16.7, 15.0), (26.3, 15.0), (26.3, 24.8), (16.7, 24.8))
    if power:
        design.track("pack_neck", p(9.5, 20.0), p(17.5, 20.0), width=mm(1), net=pack_n)
    if not sense:
        return
    design.track("sns_p", p(64.5, 17.0), p(62.7, 13.0), u1.pad(7), width=mm("0.25"))
    design.track("sns_n", p(55.5, 17.0), p(57.3, 13.0), u1.pad(8), width=mm("0.25"))
