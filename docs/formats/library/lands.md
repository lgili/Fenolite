# Land constants and drawing conventions of the footprint generators

Change c0260. The generators of `fenolite.catalog.footprints` draw a footprint from a package record. When
the record gives the manufacturer's land (`[land]` with a cited source) that land is used unchanged. Otherwise
the worst-case calculator below computes it from the record's toleranced dimensions and the constants of a
versioned table, `lands/<n>` (`fenolite.catalog.footprints.lands.LANDS`). Every constant on this page is
Fenolite's own and labelled `INFERRED` (hypothesis `H-G-LAND-CALC`).

**No IPC table, formula text or calculator is used.** IPC-7351 is a paywalled standard; nothing of it was
read for this page. Some manufacturer documents present their land patterns as following IPC-7351 or IEC
61188-5; Fenolite uses only the numbers each manufacturer publishes for its own package, cited one by one
(open question 2 of c0260, answered by its recommended default on 2026-10-30).

## The calculator

For two facing land rows with lead-tip span `L`, lead or terminal length `T` and lead width `W` (each an
exact range of nanometres), and the goals `toe`, `heel` and `side` of the land class:

```
Z = L.max + 2 toe            outer extent of the two lands, rounded up to the grid
G = L.min - 2 T.max - 2 heel inner gap between the lands, rounded down to the grid
X = W.max + 2 side           land width, rounded up to the grid
pad length = (Z - G) / 2     row centre distance = (Z + G) / 2
```

The arithmetic is worst case and exact (integers, no square root of a sum of squared tolerances): the
interval arithmetic of c0246. `L` is the body length for a chip and the body across the rows, less twice
the terminal pull-back, for a no-lead package. A pitch that leaves less than `pad_gap` between neighbouring
lands narrows them to `pitch - pad_gap` (warning `package.pads-clipped`); quad corner lands and lands next
to an exposed pad are shortened from their inner end to keep `pad_gap`. Through-hole drills are the lead's
diagonal (`isqrt(w.max² + t.max²)`, rounded up) plus `hole_clearance`, rounded up to the grid; the pad
diameter is the drill plus twice `annular_ring`. A grid-array land is the ball's nominal diameter times
`ball_ratio` for its pad kind, rounded to the grid.

## Land classes

| class | packages |
|---|---|
| `chip` | two-terminal chips (`chip` family) |
| `molded` | molded two-terminals (`molded` family) |
| `gullwing` | gull-wing leads at a pitch of 0.65 mm or more |
| `gullwing-fine` | gull-wing leads at a pitch below 0.65 mm |
| `nolead` | no-lead terminals (`nolead` family) |
| `smd-tab` | the tab of a gull-wing package and the leads and tab of an SMD `to` package |

## The table `lands/1`

Goals are back-solved from each calibration record's manufacturer land (`toe = (Z - L.max) / 2`,
`heel = (L.min - 2 T.max - G) / 2`, `side = (X - W.max) / 2`, floored to the nanometre), and the lower
median per class is rounded to 10 µm, half away from zero, by `tools/calibrate_lands.py` from the records
of `tests/data/packages/calibration`. A class with fewer than three records has no goals: `smd-tab` and the
grid-array ball ratios have none in `lands/1`, so such a package needs its `[land]` (`package.no-goals`).
Negative goals are allowed: a heel goal below zero means the manufacturers' lands start outside the worst-case
inner end of the leads.

| constant | value | label | derivation |
|---|---|---|---|
| `chip.toe` | 0.3 mm | `INFERRED` | lower median of the 7 values back-solved from the records of the class (0.15 mm, 0.25 mm, 0.3 mm, 0.3 mm, 0.35 mm, 0.575 mm, 0.625 mm), rounded to 10 µm |
| `chip.heel` | -0.1 mm | `INFERRED` | lower median of the 7 values back-solved from the records of the class (-0.125 mm, -0.125 mm, -0.125 mm, -0.1 mm, -0.05 mm, 0 mm, 0.1 mm), rounded to 10 µm |
| `chip.side` | 0.03 mm | `INFERRED` | lower median of the 7 values back-solved from the records of the class (0.025 mm, 0.025 mm, 0.025 mm, 0.025 mm, 0.05 mm, 0.075 mm, 0.1 mm), rounded to 10 µm |
| `molded.toe` | 0.1 mm | `INFERRED` | lower median of the 4 values back-solved from the records of the class (0 mm, 0.1 mm, 0.1 mm, 0.175 mm), rounded to 10 µm |
| `molded.heel` | -0.01 mm | `INFERRED` | lower median of the 4 values back-solved from the records of the class (-0.15 mm, -0.01 mm, 0.075 mm, 0.25 mm), rounded to 10 µm |
| `molded.side` | 0.08 mm | `INFERRED` | lower median of the 4 values back-solved from the records of the class (0.05 mm, 0.075 mm, 0.165 mm, 0.18 mm), rounded to 10 µm |
| `gullwing.toe` | 0.38 mm | `INFERRED` | lower median of the 8 values back-solved from the records of the class (0.35 mm, 0.35 mm, 0.35 mm, 0.375 mm, 0.375 mm, 0.375 mm, 0.38 mm, 0.41 mm), rounded to 10 µm |
| `gullwing.heel` | -0.19 mm | `INFERRED` | lower median of the 8 values back-solved from the records of the class (-0.36 mm, -0.295 mm, -0.295 mm, -0.185 mm, -0.05 mm, 0.175 mm, 0.2 mm, 0.2 mm), rounded to 10 µm |
| `gullwing.side` | 0.05 mm | `INFERRED` | lower median of the 8 values back-solved from the records of the class (0.035 mm, 0.035 mm, 0.045 mm, 0.045 mm, 0.045 mm, 0.05 mm, 0.075 mm, 0.075 mm), rounded to 10 µm |
| `gullwing-fine.toe` | 0.35 mm | `INFERRED` | lower median of the 4 values back-solved from the records of the class (0.3 mm, 0.345 mm, 0.35 mm, 0.4 mm), rounded to 10 µm |
| `gullwing-fine.heel` | 0.2 mm | `INFERRED` | lower median of the 4 values back-solved from the records of the class (-0.025 mm, 0.2 mm, 0.2 mm, 0.35 mm), rounded to 10 µm |
| `gullwing-fine.side` | 0.02 mm | `INFERRED` | lower median of the 4 values back-solved from the records of the class (0 mm, 0.015 mm, 0.015 mm, 0.015 mm), rounded to 10 µm |
| `nolead.toe` | 0.15 mm | `INFERRED` | lower median of the 4 values back-solved from the records of the class (0.125 mm, 0.15 mm, 0.15 mm, 0.175 mm), rounded to 10 µm |
| `nolead.heel` | -0.15 mm | `INFERRED` | lower median of the 4 values back-solved from the records of the class (-0.175 mm, -0.15 mm, -0.1 mm, -0.075 mm), rounded to 10 µm |
| `nolead.side` | -0.03 mm | `INFERRED` | lower median of the 4 values back-solved from the records of the class (-0.03 mm, -0.03 mm, -0.025 mm, -0.025 mm), rounded to 10 µm |
| `pad_gap` | 0.2 mm | `INFERRED` | Fenolite's choice: the smallest copper gap between neighbouring pads of the 100 footprints of the 0.6 catalog |
| `grid` | 0.01 mm | `INFERRED` | Fenolite's choice: the 10 µm step to which Z, X and drills are rounded up and G down |
| `courtyard` | 0.5 mm | `INFERRED` | Fenolite's choice: the courtyard excess that the 0.6 catalog's `_make_footprint` uses |
| `hole_clearance` | 0.2 mm | `INFERRED` | Fenolite's choice: with the nominal 0.64 mm square pin of the Würth WR-PHD header (S-0408, 0.905 mm diagonal) it gives 1.11 mm, next to the 1.10 mm hole that data sheet recommends; manufacturer data sheets give holes but rarely the tolerance stack, so it is not calibrated |
| `annular_ring` | 0.35 mm | `INFERRED` | Fenolite's choice: the lower median of the copper rings of the 0.6 catalog's through-hole lands (0.35 mm headers and TO-220, 0.40 mm electrolytics, 0.45 mm DIPs) |
| `paste_cell` | 2 mm | `INFERRED` | Fenolite's choice: an exposed pad up to 4 mm a side gets a 2 × 2 paste grid, as the 0.6 catalog's QFN and DFN lands do |
| `paste_window` | 4/5 | `INFERRED` | Fenolite's choice: each window is 4/5 of its cell per axis (64 % coverage), as the 0.6 catalog's `_thermal_paste` |

The records used per class:

| class | records |
|---|---|
| `chip` | Vishay D/CRCW e3 0402, 0603, 0805, 1206, 1210, 2010 and 2512 (S-0990) |
| `molded` | Diodes SOD123 (S-0442), SOD123F (S-0443), SOD323 (S-0444), SOD523 (S-0445) |
| `gullwing` | TI D0008A, PW0008A, DGK0008A (S-0986), D0014A (S-0378), PW0014A (S-0983), DBV0005A and DCK0005A (S-0984), onsemi 751-07 (S-0981) |
| `gullwing-fine` | TI DGS0010A (S-0987), DYY0014A (S-0983), PT0048A (S-0402), PN0080A (S-0988) |
| `nolead` | TI RGT0016C (S-0982), RGC0064B (S-0988), DRV0006A (S-0989), DSF0006A (S-0984) |

How close the calculator comes to the manufacturers' lands is measured by
`tests/unit/catalog/footprints/test_lands.py::test_calibration_set_within_tolerance` (`H-G-LAND-CALC`): on
2026-10-30 every pad length, pad width and row spacing of the 27 calibration records was within 0.42 mm of
the manufacturer's (the largest: TI PW0008A and PW0014A row spacing). This is a measure of spread, not a
verification: the calculated lands stay `INFERRED`.

## Versioning

A released table never changes: a new calibration is `lands/2`. A record names its table version
(`[generate] lands`), so an upgrade of Fenolite never moves a land silently. Only the density `nominal` is
shipped; `compact` and `robust` are reserved (open question 1).

## Drawing conventions

`drawing/0` reproduces the 0.6 catalog: a fabrication rectangle of the nominal body (0.1 mm), a courtyard
symmetric about the origin (the extent of the body and pads plus 0.5 mm, not rounded), the 0.6 pin-1 line
across the fabrication corner and cathode line, rectangular surface pads, round through-hole pads, no
silkscreen and no 3D model; its rows keep the 0.6 placement (pin 1 at the most positive y). `drawing/1`:

| constant | value | label | use |
|---|---|---|---|
| `fab_width` | 0.1 mm | `INFERRED` | fabrication outline stroke |
| `fab_chamfer_max` | 1 mm | `INFERRED` | chamfer at the pin-1 corner of a multi-pin body: min(1 mm, short side / 4) |
| `courtyard_width` | 0.05 mm | `INFERRED` | courtyard stroke; the courtyard is the bounding box of the body and pads plus `courtyard`, rounded outward to the grid |
| `silk_width` | 0.125 mm | `INFERRED` | silkscreen stroke |
| `silk_copper_gap` | 0.175 mm | `INFERRED` | gap from a silkscreen stroke edge to any pad; the outline is cut there |
| `silk_min_piece` | 0.25 mm | `INFERRED` | shorter silkscreen pieces are dropped |
| `pin1_dot_radius` | 0.15 mm | `INFERRED` | pin-1 dot beyond the outer end of pad 1, outside the body (a circle of half the radius stroked with the radius, so no filled shape) |
| `corner_mark_max` | 1 mm | `INFERRED` | arms of the L mark at the pin-1 corner of no-lead and grid packages: min(1 mm, short side / 4) |
| `corner_ratio_ppm` | 200000 | `INFERRED` | rounded-rectangle surface pads: 20 % of the shorter side |
| `corner_radius_max` | 0.1 mm | `INFERRED` | the corner radius is capped at 0.1 mm |

Polarized two-terminals get a fabrication bar one fifth of the body length from the pad-1 end and a silkscreen
bar beside pad 1 outside the pads. Through-hole pad 1 is square, the others round or oval. Pin 1 of dual and
quad rows is at the top left (the most negative y of the Y-down library frame, `docs/formats/kicad/frame.md`)
and numbering runs counter-clockwise in the top view. A released convention never changes; a new look is
`drawing/2`.

Sources: the calibration documents above (S-0378, S-0402, S-0442, S-0443, S-0444, S-0445, S-0981, S-0982,
S-0983, S-0984, S-0986, S-0987, S-0988, S-0989, S-0990), read for numbers only; no figure, table layout or text
is copied.
