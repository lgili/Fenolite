# Renders of change c0406: readable (before) and wired (after) sheets

Each authored design of `tests/_wireddesigns.py` built for KiCad 10 with `--schematic-layout readable`
(the build default before this change, `*-before.png`) and with the new default `wired` (`*-after.png`),
exported with `kicad-cli sch export svg` 10.0.6 on 2026-11-05 and converted to PNG at 1600 px. The
two-module design has a root sheet and the sheets `amp` and `psu`.

Measures of `fenolite.backends.kicad.schreadability.measure_sheets` over all sheets of a design. The faults a
readable sheet avoids (wires over a pin or a body, four-way points, T joints without a junction,
overlapping texts) are 0 on every sheet of both layouts.

| design | layout | labels | wires | junctions | power symbols | crossings |
|---|---|---:|---:|---:|---:|---:|
| op-amp stage | readable | 19 | 4 | 0 | 0 | 0 |
| op-amp stage | wired | 5 | 25 | 3 | 10 | 1 |
| controller | readable | 31 | 5 | 0 | 0 | 0 |
| controller | wired | 8 | 50 | 6 | 14 | 3 |
| linear supply | readable | 17 | 2 | 0 | 0 | 0 |
| linear supply | wired | 3 | 16 | 0 | 13 | 0 |
| transistor switch | readable | 12 | 3 | 0 | 0 | 0 |
| transistor switch | wired | 3 | 17 | 2 | 7 | 0 |
| two modules | readable | 19 | 6 | 0 | 0 | 0 |
| two modules | wired | 4 | 27 | 1 | 17 | 1 |

KiCad 10.0.6 ERC reports no violation on any wired sheet, and the nets of `sch export netlist` equal
Fenolite's own netlist (`tests/kicad/schematic/test_wired_oracle.py`). The drafting rules and their
sources are in `docs/schematic-drafting.md`.

To draw them again, build a design with `build_authored(DESIGNS[name](), layout)` of
`tests/_wireddesigns.py`, write its `files` to a folder and run
`kicad-cli sch export svg -o <folder> <name>.kicad_sch`.
