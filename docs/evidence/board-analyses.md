# Board analyses: recorded evidence

Counts and outcomes of change c0047 (capability board-analyses). Nothing here raises a label:
`fenolite.analysis.EVIDENCE` is `INFERRED`. The definitions and the limits are in `docs/analyses.md`.

## KiCad creepage bracket (`H-K-AN-CREEP`)

KiCad 9 and 10 have a `creepage` constraint in custom rules (S-0272). On two authored benches, a rule with
`min` 50 µm below Fenolite's creepage and one 50 µm above were run through `kicad-cli pcb drc`
(S-0022). Each rules text also holds the canary rule, whose violation shows that the rules file was
loaded. Run on 2026-10-04 with `kicad-cli` 10.0.6 (local, macOS);
`tests/kicad/analysis/test_creepage_bracket.py`; outcomes pinned in
`docs/evidence/kicad/probes/10.0.6.json`.

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
