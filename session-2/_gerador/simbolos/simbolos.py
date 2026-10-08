# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
"""The five symbols of change c0134, placed on one sheet for a look in Altium Designer (session 2).

``BJT_NPN``, ``Comparator``, ``Operational_Amplifier`` and ``Linear_Regulator`` come from Fenolite's
catalog, ``CONN2`` from the example library ``FenoliteDemo.kicad_sym`` (a copy of
``examples/altium_kicad/FenoliteDemo.kicad_sym`` of the repository, found through this folder's
``sym-lib-table``). Only symbols: no board, no footprint. Authored for this pack; nothing here comes from
any other project.

Build: ``fenolite build simbolos.py --target altium --out DIR --seed 0 --timestamp 2026-01-01T00:00:00Z
--confirm``.
"""

from fenolite.dsl import Design, Part

design = Design("simbolos")

q1 = Part("Q1", "Fenolite:BJT_NPN", value="BJT_NPN")
u1 = Part("U1", "Fenolite:Comparator", value="Comparator")
u2 = Part("U2", "Fenolite:Operational_Amplifier", value="Operational_Amplifier")
u3 = Part("U3", "Fenolite:Linear_Regulator", value="Linear_Regulator")
j1 = Part("J1", "FenoliteDemo:CONN2", value="CONN2")
design.add(q1, u1, u2, u3, j1)
