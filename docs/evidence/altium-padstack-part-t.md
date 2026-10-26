# Full Stack layer association: native Part T follow-up

Date: 2026-10-13. Altium Designer Professional 26.5.0. Change c0160,
`H-A-CONV-PADSTACK`; public format sources S-0002 and S-0161.

The case is authored for Fenolite: the committed four-layer padstack fixture is
adapted in a runtime copy to custom mode, with In1 circular 1.2 x 1.2 mm and In2
rectangular 1.4 x 1.1 mm. No private project or vendor artifact is included here.

Before the correction, the generated PCB and a footprint placed from its PcbLib
both showed In1 and In2 as round 1.2 x 1.2 mm. Internal readback shared the wrong
table association and reported no unexplained differences.

After the correction, the agent performed the following operations in the native
Altium interface on the maintainer's licensed PC, using Windows UI Automation:

1. Open a uniquely named disposable copy of the regenerated PCB and inspect pad 1.
2. Clear all objects from a separate disposable four-layer PCB, retaining its stack.
3. Open the regenerated PcbLib and use the PCB Library panel's Place button to place
   Mini_Padstack into that empty PCB.
4. Inspect the placed pad and save the disposable PCB.

Both inspections showed Full Stack selected and the following values:

| Layer | Shape | X (mil) | Y (mil) | Approximate mm |
|---|---|---|---|---|
| Top | Round | 66.929 | 66.929 | 1.7 x 1.7 |
| Mid-Layer 1 | Round | 47.244 | 47.244 | 1.2 x 1.2 |
| Mid-Layer 2 | Rectangle | 55.118 | 43.307 | 1.4 x 1.1 |
| Bottom | Rectangle | 59.055 | 59.055 | 1.5 x 1.5 |

Placement succeeded without an error. **ALTIUM-VERIFIED(author-report)** applies
to this authored four-layer Full Stack case and its library placement. It does
not approve connector masks, other pad shapes, the thirtieth inner layer, or the
remaining Part T projects. The thirty-layer association remains inferred from
the public source fields and covered by unit regression tests.

Local evidence stays in ignored `build/altium-part-t-ready/fixed/`:
`T6-generated-pad-properties.png`, `T6-placed-pad-properties.png`, the regenerated
project, and its conversion report. The Altium-saved scratch PCB stays under the
runtime work directory. Neither native binaries nor screenshots are committed.

A separate KiCad 10.0.6 import shows In2 round 1.2 x 0 mm before the fix and
rectangle 1.4 x 0 mm afterwards. The zero-height compatibility finding predates
this correction and remains unresolved. Neither import is a passing Full Stack
oracle; positive extended Y values were retained as confirmed by native inspection.
