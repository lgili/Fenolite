# Provenance of `fenolite.roles`

The net roles name what a net does on a power board and judge its copper through the analyses of
`fenolite.analysis`. The default limits of the role profile (`profile.py`) are recorded one by one in
`docs/roles.md`, "Default limits", each with the id of a source listed in `docs/evidence/sources.md` or the
`H-G-ROLE-` hypothesis that measures a Fenolite heuristic. The inference rules, the classes, the placement
bound, the Kelvin and gate-return walks and every other rule of the package are Fenolite's own. The sources
were read for facts only; no text, figure or table of them is copied, and the spacing tables that S-0854
reproduces from standards are not used. No creepage or clearance value, temperature rise, copper thickness
or current is shipped.

| fact-or-area | public source | licence of source | date | how used |
|---|---|---|---|---|
| the sense lines of a low-value shunt joined inside its mounting pads, not outside them, so that the pads' copper and solder resistance stays out of the measurement (the inner-edge rule of the Kelvin attachment) | S-0850 | © 2026 ROHM Co., Ltd.; read for facts only, no text, figure or value table copied | 2026-10-28 | facts only |
| a power trace of at least 15 mils (0.381 mm) per ampere on a standard board; one standard via per 200 mA at a layer change (the rule of thumb of the current checks) | S-0851 | © 1999–2013 Texas Instruments Incorporated; read for facts only, nothing copied | 2026-10-28 | facts only |
| the shunt's sense signals as a tightly coupled pair to the amplifier; the high-side gate trace close to the switch node; the switch node and the high-current loop kept short (the pair, gate-return and switching-distance checks) | S-0852 | © 2021 Texas Instruments Incorporated; read for facts only; its via current table is not used | 2026-10-28 | facts only |
| the gate drive loop and its return add parasitic inductance; a driver next to the switch keeps the loop small (the gate loop and gate-return checks) | S-0853 | © 2017–2018 Texas Instruments Incorporated; read for facts only, nothing copied | 2026-10-28 | facts only |
| creepage dimensioned by working voltage, pollution degree and material group, clearance by transients, pollution degree and altitude (why no distance ships, and the hint of `roles.limit-missing`) | S-0854 | Texas Instruments seminar material, all rights reserved; read for definitions only, its tables not used | 2026-10-28 | facts only |
| the gate-drive loops are critical loops whose area is minimised, beside the switching power loop (why `plan_critical` routes gate loops first, with the area cost of `routing.roleroute`) | S-0890 | Copyright © 2016, Texas Instruments Incorporated (stated on the last page), all rights reserved; read for facts only, no text, figure or value copied | 2026-10-29 | facts only |
| the gate-drive inductance grows with the area between the drive and return traces; the return runs beside the drive, or in its shadow on an adjacent layer through a via; a low-side return may take a ground plane (the gate return's width, its side-by-side, stacked and plane forms, and the area cost) | S-0891 | Copyright © 2023 Texas Instruments Incorporated (stated on each page); read for facts only, no text or figure copied | 2026-10-29 | facts only |
| the sense lines routed as a differential pair; a pour or plane joined to a sense trace is a frequent fault; a polygon keep-out along the sense trace, on all layers around a via, keeps pours off it (the isolation of a branch and its corridor `role.corridor.<group>.<net>`) | S-0892 | Copyright © 2023 Texas Instruments Incorporated (stated on each page); read for facts only, no text or figure copied | 2026-10-29 | facts only |

The critical routes (`routes.py`, change c0244) plan from these facts and c0222's walks; the shapes, the
corridor outline and every rule of the plan are Fenolite's own, and no router's code was read.
