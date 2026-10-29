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
| the input capacitor joined first to the switches by short, wide copper; the switch node's copper kept small because it couples noise; vias of the input and output away from the critical connections; a solid ground plane (the role copper's hot-loop legs first, its switch node without widening, its via patches away from the hot loop) | S-0860 | © 2015 Texas Instruments Incorporated; read for facts only, no text or figure copied | 2026-10-29 | facts only |
| a thermal relief eases soldering and adds negligible inductance (why ground zones relieve through-hole pads) | S-0861 | © 2026 LearnEMC, LLC; read for facts only, nothing copied | 2026-10-29 | facts only |
| a relief gives a joint a high thermal resistance, which is not wanted where heat or current must flow (why power zones join their pads solid) | S-0862 | © 1997–2018 Texas Instruments Incorporated; read for facts only, nothing copied | 2026-10-29 | facts only |
| a stitching pitch of at most one twentieth of the wavelength at the highest significant frequency, and many vias across a pour boundary (the method in `docs/roles.md`, "Role copper", and at least two stitching vias per overlap) | S-0863 | © 2026 JLCPCB.COM; a fabricator's blog, read for the method only, nothing copied | 2026-10-29 | facts only |
