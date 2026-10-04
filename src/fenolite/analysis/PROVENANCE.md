# Provenance of `fenolite.analysis`

The capacity analysis uses one published fit. Its constants, its units and the range in which its source
calls it valid are recorded one by one in `docs/analyses.md`, table "Capacity fit", each with the id of a
source listed in `docs/evidence/sources.md`. The source attributes the fit to a standard; Fenolite did not
consult that standard and reproduces none of its charts, tables or figures. The distance analyses are
Fenolite's own geometry and take no figure from any source. No requirement value is shipped.

| fact-or-area | public source | licence of source | date | how used |
|---|---|---|---|---|
| the fit `I = K · ΔT^b · A^c`: the two constants `K`, the two exponents, the units (amperes, kelvin of rise, square mils) | S-0269 | GPL-3.0-or-later help text; read for facts, nothing copied | 2026-10-03 | facts only |
| the range in which the source calls the fit valid: current per layer kind, temperature rise, width | S-0269 | GPL-3.0-or-later help text; read for facts, nothing copied | 2026-10-03 | facts only |
| a via's barrel cross-section `π · (finished hole + plating) · plating`, used with the outer constant | S-0270 | GPL-3.0-or-later; one fact, nothing transcribed or followed | 2026-10-03 | facts only |
| the fit and `π` computed with `decimal`, identical on every platform | S-0012 | PSF License Version 2 | 2026-10-01 | facts only |
| the requirements file parsed with `tomllib` | S-0273 | PSF License Version 2 | 2026-10-03 | facts only |
