# Board analyses: recorded evidence

Counts and outcomes of change c0047 (capability board-analyses). Nothing here raises a label:
`fenolite.analysis.EVIDENCE` is `INFERRED`. The definitions and the limits are in `docs/analyses.md`.

## KiCad creepage bracket (`H-K-AN-CREEP`)

KiCad 9 and 10 have a `creepage` constraint in custom rules (S-0272). On two authored benches, a rule with
`min` 50 µm below Fenolite's creepage and one 50 µm above were run through `kicad-cli pcb drc`
(S-0022). Each rules text also holds the canary rule, whose violation shows that the rules file was
loaded. Run on 2026-10-04 with `kicad-cli` 10.0.6 (local, macOS);
`tests/kicad/analysis/test_creepage_bracket.py`; outcomes pinned in
`docs/evidence/kicad/probes/10.0.6.json`. The `kicad-10` job gave the same outcomes on Linux (run
https://github.com/lgili/Fenolite/actions/runs/37213861620).

| probe | bench | Fenolite | rule 50 µm below | rule 50 µm above | outcome |
|---|---|---|---|---|---|
| `analysis-creepage-slot` | two 1 mm tracks on the top face, a slot between their ends | 11 mm | no creepage violation | one creepage violation | `equal` |
| `analysis-creepage-edge` | a 0.5 mm track on each outer face, one above the other, 2 mm from the board edge, board 1.6 mm thick | 5.1 mm | no creepage violation | no creepage violation | `different` |

- **Slot.** KiCad's violation text gives the distance it measured: with `min` 12 mm it reports an actual
  creepage of 11.0000 mm, the value Fenolite computes. The canary fired in both runs.
- **Edge.** KiCad reports no creepage violation between the two tracks at any `min` tried: 5.15 mm, 6 mm,
  10 mm and 30 mm. The canary fired in every run, so the rules file was loaded. On this bench KiCad's
  creepage rule does not join copper on opposite faces around the board edge; Fenolite's path does
  (1.75 mm to the edge, 1.6 mm down the wall, 1.75 mm back). How KiCad defines its path is not documented
  beyond one sentence (S-0272), and no KiCad source was read.
- The first row of `H-K-AN-CREEP` expected `equal` on both benches, so it is refuted; `H-K-AN-CREEP-2`
  states what was observed.

Consequence for users: a board that passes KiCad's `creepage` rule can still hold a short path around the
board edge between its two faces. `fenolite analyze` reports that path when the board thickness is given.

## Checks without an oracle

| check | test | result on 2026-10-04 |
|---|---|---|
| arithmetic of the fit against a second computation | `test_current.py::test_fit_independent_computation` | 800 generated cases, each within 1 mA |
| copper shapes equal to the copper check's | `test_copper.py::test_same_shapes_as_the_copper_check` | 60 generated boards, more than 600 shapes, equal per layer and net |
| creepage against an eight-neighbour grid search at 0.1 mm | `test_surface.py::test_grid_agreement_on_generated_boards` | more than 100 generated boards with up to three cut-outs: never above the grid's length plus 1 nm, never below 0.92 times it |
| walls: the two directions and the two faces agree, and a limit just above the length changes nothing | `test_surface.py::test_walls_are_symmetric_on_generated_boards` | 60 generated boards |
| hand-computed cases | `test_surface.py`, `test_distance.py` | 11 mm around a slot and around a notch; 5.1 mm across the edge; a 3-4-5 crossing of an edge; a diamond-shaped board within 2 nm |

## Time of the search

One pair of nets through `analyze_distances`, on the development machine (an Apple-silicon laptop,
CPython 3.13), on 2026-10-04. Supporting data only.

| board | boundary vertices | time per pair |
|---|---|---|
| slot board, one face | 8 | 3 ms |
| slot board with walls (1.6 mm) | 8 | 13 ms |
| edge board (track above track) | 4 | 2 ms |
| round board with a round hole, both polygonised at 5 µm, with walls | 192 | 4.1 s |

The search prunes with the distance in plan view to each conductor, which no path can beat. Before that
pruning the round board took 129 s for the same result; the design's limit for one pair is 60 s.

## Power paths, insulation, grooves and conductors (change c0115)

Counts and outcomes of change c0115. Nothing here raises a label: the levels of
`fenolite.analysis.power`, `insulation`, `grooves` and `surface.BRIDGE_EVIDENCE` are `INFERRED`.

### Fill census (`H-K-FILL-SLIT`)

Every fill of the readable demo boards (S-0058) taken apart by `fenolite.analysis.fills.unfracture`:
slits removed, the remaining edges chained by exact endpoint equality, and the stored ring's shoelace
area compared with the outer ring's less the holes'. Run on 2026-10-07 with
`FENOLITE_CENSUS_OUT=<file> uv run pytest tests/corpus/test_fill_slits.py -rA`; counts only.

| tag | boards | fills | fills with slits | holes | fills that do not chain | fills whose areas differ |
|---|---|---|---|---|---|---|
| 9.0.9.1 | 5 | 24 | 6 | 238 | 0 | 0 |
| 10.0.6 | 16 | 339 | 88 | 6223 | 0 | 0 |

### Narrowest section (`H-G-AN-SECTION`)

| check | test | result on 2026-10-07 |
|---|---|---|
| hand-computed cases | `test_section.py` | a 2 mm neck; two strips of 1.2 mm beside a hole, 2.4 mm; four spokes of 0.5 mm, 2 mm; the hull of a 0.6 mm via, 1.883 mm; a 5 mm strip beside a round port and between two pads; a moat, 0 |
| the minimum cut of a four-neighbour grid at 0.05 mm (test code) | `test_section.py::test_grid_cut_agreement_on_generated_regions` | 40 generated regions with up to four rectangular holes and two rectangular ports: never above the grid cut plus 0.05 mm, never below the grid cut divided by √2 less 0.05 mm; 39 equal the grid cut, one is 85 % of it (a slanted chord) |

Time of one section, on the development machine (an Apple-silicon laptop, CPython 3.13), supporting data
only: between two 0.889 mm vias of the net, about as far apart as the fill allows, on the largest fill of
the readable demo boards (58 893 points, 1117 holes): 13 s; the section is the hull of one via, 2.791 mm.
The first version of the search took 109 s on it; integer points for stored vertices and a parity that
is known without the closest points for chords away from the seam brought it down.

### Region bounds and the path network (`H-G-AN-POUR`, `H-G-AN-NETWORK`)

Laplace's equation solved on a 0.05 mm grid in the test (`tests/_power.py::fdm_resistance`, test code,
conjugate gradients started from coarser grids), against the interval of `analyze_power`, on 2026-10-07
(`uv run pytest tests/unit/analysis/test_power.py -k fdm -rA`). 50 µm of copper and an illustrative
resistivity of 20 nΩ·m, so 400 µΩ per square. Each grid value lies inside its interval widened by 2 %.

| case | interval | grid | high over low | time of the analysis |
|---|---|---|---|---|
| `strip`: 20 mm × 5 mm between two pads over its ends | 1440 to 1440 µΩ | 1439.2 µΩ | 1 | 6 ms |
| `dumbbell`: a 2 mm neck, a 2 mm pad in each square | 244 to 19 800 µΩ | 1312.2 µΩ | 81 | 10 ms |
| `split4`: a 4 mm neck with a 1.6 mm hole | 240 to 13 989 µΩ | 1006.0 µΩ | 58 | 10 ms |
| `two_strips`: the strip on two layers between through-hole pads | 720 to 720 µΩ | 719.6 µΩ | 1 | 11 ms |

The two bounds are Fenolite's own derivation: S-0681 and S-0682, read as rendered on 2026-10-08, give
the facts it starts from and state no bound of the resistance of a conductor. The two bounds meet on a strip between two plates and are far apart on a pour with a neck: the upper
bound `R_s·A/w²` charges the whole area at the neck's width, and the lower bound `R_s·ℓ²/A` spreads the
current over the whole area. A drop requirement on such a pour is therefore often undecided; the interval
is reported as it is.

### Grooves and conductors on the path (`H-G-AN-GROOVE`, `H-G-AN-OVER`)

| check | test | result on 2026-10-07 |
|---|---|---|
| grooves, hand-computed | `test_grooves.py` | a 2 mm slot counts at a width of 2 mm and is bridged at 3 mm (11 mm, then 9 mm); a T-shaped cut-out with a 1 mm stem is bridged at 1.1 mm; a notch with a 2 mm mouth is filled at 3 mm |
| bridging never lengthens a creepage | `test_grooves.py::test_bridging_never_lengthens_a_creepage_on_generated_boards` | generated boards with one to three slots at four widths: never above the value before, 9 mm when every slot is bridged |
| conductors, hand-computed | `test_surface_bridges.py`, `test_distance.py` | 8 mm over a floating track, a floating via and a track of a third net (9 mm without); 2.9 mm through a via between two faces |
| a grid search whose conductor cells cost nothing | `test_surface_bridges.py::test_grid_agreement_over_conductors` | 200 generated boards with cut-outs and up to two rectangular conductors: never above the grid's length plus 1 nm, never below 0.92 times it |

Time of one pair through `analyze_distances` on the readable demo board with the most tracks and vias
(8740; 12 022 shapes on its two outer layers), the development machine, supporting data only: 1.6 s per
pair over 40 pairs closer than 0.3 mm, against 1.5 s with the code before this change. The conductors of
a pair are taken from one index built for all pairs. A pair with more than 500 conductors within the
reach of one of its nets is not searched over conductors and is counted in a warning.

### Recorded KiCad behaviours (`H-K-AN-GROOVE`, `H-K-AN-SPLIT`, `H-K-AN-NECK`, `H-K-AN-LAYERS`)

Run on 2026-10-07 with `kicad-cli` 10.0.6 (local, macOS):
`uv run pytest tests/kicad/analysis/test_power_probes.py -rA`; outcomes pinned in
`docs/evidence/kicad/probes/10.0.6.json`. Each rules text holds a canary scoped to its own two nets,
which fired in every run. Supporting data: nothing gates on it and no label rises from it.

| probe | bench | what `pcb drc` reported | outcome |
|---|---|---|---|
| `analysis-groove-slot` | c0047's slot bench, `rules.min_groove_width` of 3 mm in the project file, a creepage rule of 30 mm | actual 11.0000 mm: the 2 mm slot is not bridged | `equal` |
| `analysis-creepage-split` | tracks of `A` and `B` 9 mm apart, a 1 mm track of `C` across, creepage rules of 30 mm on the three pairs | 4.0000 mm on `A`–`C` and on `C`–`B`, nothing on `A`–`B` | `equal` |
| `analysis-neck-plain` | a pour of two 10 mm squares joined by a 2 mm neck, refilled, a `connection_width` rule | nothing at a minimum of 1.95 mm, actual 2.0000 mm at 2.05 mm | `equal` |
| `analysis-neck-split` | a 4 mm neck with a 0.6 mm via of another net at its centre, zone clearance 0.5 mm, refilled, minimum 2.45 mm | actual 1.6968 mm, twice: neither a strip (1.2 mm) nor the section (2.4 mm) | `equal` |
| `insulation-layers` | 1 mm tracks of `A` on `In1.Cu` and of `B` on `In2.Cu`, one above the other, `clearance` and `physical_clearance` rules of 1 mm | nothing between the two tracks | `equal` |

On 9.0.9, in the `kicad-9` job (pinned image) of CI run 37803522539 on `a105cc0`, 2026-10-08
(`tests/kicad/analysis/test_power_nine.py`, `-rA`), each bench written for target 9:

| probe | bench on 9.0.9 | what `pcb drc` reported | outcome |
|---|---|---|---|
| `analysis-neck-plain` | the plain neck with its fill stored (9.0.9 has no `--refill-zones`), minimum 1.95 mm and 2.05 mm | `{'below': [], 'canary': True, 'above': ['2.0000']}`: nothing at 1.95 mm, actual 2.0000 mm at 2.05 mm | `equal` |
| `insulation-layers` | as above | `{'canary': True, 'between': []}`: nothing between the two tracks, the canary firing | `equal` |

Both are registered for majors 9 and 10, with their lines in `9.0.9.json`; the other three are stated
for 10.0.6 and refuse target 9.
