# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placed crossing connections authored solely for Fenolite's atomic decision proofs."""

from dataclasses import replace

from _search_project import SEARCH, bench, cli

NEGOTIATE = (*SEARCH, "--router-option", "negotiate=on", "--router-option", "negotiate-max-rounds=5")


def project(folder, *, layers=2, major=10, pair=False, locked=False, third=False, high=False):
    body = """
from fenolite.dsl import Design, Net, Part, connect, mm

design=Design("negotiated")
design.board(mm(24),mm(20))
parts=[Part(f"R{i}","Fenolite:Resistor",footprint="Fenolite:Chip_0603",value="1k") for i in range(1,5)]
design.add(*parts)
a,b=Net("SIG"),Net("SECOND")
connect(a,parts[0][1],parts[1][1])
connect(b,parts[2][1],parts[3][1])
design.rules.netclass("SIGNAL",clearance=mm("0.2"),track_width=mm("0.25"),
                      via_diameter=mm("0.6"),via_drill=mm("0.3"),nets=(a,b))
for part,(x,y) in zip(parts,((4,10),(20,10),(12,4),(12,16))):
    part.place(mm(x),mm(y),rot=90)
design.net_role(a,"signal")
design.net_role(b,"signal")
"""
    body = body.replace("design.board(mm(24),mm(20))", f"design.board(mm(24),mm(20),copper={layers})")
    if third:
        body += (
            "\n"
            'r5=Part("R5","Fenolite:Resistor",footprint="Fenolite:Chip_0603",value="1k")\n'
            'r6=Part("R6","Fenolite:Resistor",footprint="Fenolite:Chip_0603",value="1k")\n'
            "design.add(r5,r6)\n"
            'extra=Net("EXTRA")\n'
            "connect(extra,r5[1],r6[1])\n"
            "r5.place(mm(4),mm(18),rot=90)\n"
            "r6.place(mm(20),mm(18),rot=90)\n"
        )
    if high:
        body += (
            '\nbus=Net("HV_REF")\ndesign.add(bus)\n'
            'design.net_role(bus,"high_voltage")\n'
            'design.track("known_bus",(mm(1),mm(1)),(mm(2),mm(1)),'
            'width=mm("0.25"),net=bus,locked=True)\n'
        )
    if pair:
        body = body.replace('Net("SIG")', 'Net("DP")').replace('Net("SECOND")', 'Net("DN")')
    if locked:
        body += (
            '\nblock=Net("BLOCK")\ndesign.add(block)\n'
            'design.track("locked_barrier",(mm(11),mm("0.75")),(mm(11),mm("19.25")),'
            'width=mm("0.25"),net=block,locked=True)\n'
        )
    built = bench(folder, "negotiated", body)
    if major != 10:
        out = folder / "oracle"
        code, _, err = cli(
            "build",
            str(folder / "negotiated.py"),
            "--out",
            str(out),
            "--kicad-version",
            str(major),
            "--confirm",
        )
        assert code == 0, err
        built = replace(built, out=out, board=out / built.board.name)
    return built
