# KiCad stack-up: measurements (change c0101)

What `kicad-cli` does with the `stackup` node of a board's `setup`, measured for change c0101. The facts
are in `docs/formats/kicad/board.md`, "Stack-up"; the hypotheses are `H-K-STACKUP-JOB`,
`H-K-STACKUP-COMPLETE`, `H-K-STACKUP-DEFAULT` and `H-K-STACKUP-RESAVE` in `docs/hypotheses.md`.

## How it was measured

- Benches: `tests/_stackbench.py`. Created 50 × 30 mm boards with one track per copper layer, written by
  `write_board` for the running major, with 2, 4, 6 and 8 copper layers (the counts of change c0100).
  The benches of 6 and 8 layers and the six-layer build ran on 10.0.6 only; their 9.0.9 side waits for the
  one image run of the wave.
- Commands, each on a copy: `kicad-cli pcb export gerbers -l F.Cu -o out/ bench.kicad_pcb`, which writes
  `bench-job.gbrjob` beside the Gerber; on 10.0.6 also `kicad-cli pcb upgrade --force` and
  `kicad-cli pcb export ipc2581`.
- Runs of 2026-10-07: `kicad-cli` 10.0.6, the macOS application, local; `kicad-cli` 9.0.9 in the pinned
  image `kicad/kicad:9.0.9@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`
  (linux/amd64), local run. The outcomes are pinned as probes in
  `docs/evidence/kicad/probes/10.0.6.json` and `9.0.9.json`, and
  `tests/kicad/board/test_stackup_oracle.py` asserts them.
- The proposal's own measurements (2026-10-05, another branch, 18 node variants on 2 to 8 layers) are its
  first record; this page holds only what was measured again.

## Outcomes

| probe | 10.0.6 | 9.0.9 | what it shows |
|---|---|---|---|
| `pcb-stackup-job-2` | equal | equal | copper 35 µm, a 1.5 mm core with a material, no mask in the stack-up: the job file states both masks with the thickness 0, `BoardThickness` 1.57 and `Finish` `None` |
| `pcb-stackup-job-4` | equal | equal | masks of 10 µm (one `Green`), a prepreg, a core of two sheets, a prepreg, `ENIG`, constraints: 13 entries, the sheets as `(1/2)` and `(2/2)`, the constants stated, `BoardThickness` 2.025, `ImpedanceControlled` true |
| `pcb-stackup-job-6` | equal | not run yet | masks (`Blue`), 35 and 17.5 µm copper, prepregs and cores with their constants, `HAL lead-free` |
| `pcb-stackup-job-8` | equal | not run yet | the same build-up on eight layers, with constraints: the constants are stated |
| `build-stackup-job` | equal | equal for the two-layer blink; the six-layer variant not run yet | the blink with `design.stackup(...)`, and its six-layer variant with a prepreg of two sheets, built and exported: the job file states the declared stack-up |
| `pcb-stackup-incomplete-physical` | absent | absent | copper and dielectric rows only: no thickness in the job file |
| `pcb-stackup-incomplete-nosilk` | absent | absent | masks without silkscreen and paste rows |
| `pcb-stackup-incomplete-fewer` | absent | absent | copper rows for 2 layers on a 4-layer table |
| `pcb-stackup-incomplete-more` | absent | absent | copper rows for 6 layers on a 4-layer table |
| `pcb-stackup-incomplete-names` | absent | absent | copper rows named `Top`, `Mid1`, `Mid2`, `Bottom` |
| `pcb-stackup-incomplete-twodiel` | absent | absent | two dielectric rows in one gap |
| `pcb-stackup-incomplete-nopaste` | absent | absent | paste rows on a table without paste layers |
| `pcb-stackup-order` | present | present | silkscreen after mask on the top side: used |
| `pcb-stackup-nopaste-table` | present | present | a table and a node without paste: used |
| `pcb-stackup-default-2` | equal | equal | no node, `general` 1.6 mm: copper 0.035, masks 0.01, one FR4 dielectric of 1.51 mm, finish `None` |
| `pcb-stackup-default-4` | equal | equal | three FR4 dielectrics of 0.48 mm |
| `pcb-stackup-default-6` | equal | not run yet | five FR4 dielectrics of 0.274 mm |
| `pcb-stackup-default-8` | equal | not run yet | seven FR4 dielectrics of 0.1857 mm |
| `pcb-stackup-resave` (the four benches) | equal | not run | `pcb upgrade --force` keeps the written nodes and `general`; 9.0.9 has no `pcb upgrade` |
| `pcb-stackup-resave-defaults` | equal | not run | rows without values come back with KiCad's defaults |
| `pcb-stackup-ipc-thickness` | equal | not run | `overallThickness` is `2.0250` where `general` states 1.6 |

For each of the nine node cases `read_board` gives the same verdict on the same file: no stack-up and
`kicad.board.stackup-unused` for the seven, a stack-up for the two.

## What differed from the proposal

- **Re-save adds constants.** The proposal said that a complete node in the written form comes back with
  the same text. On 10.0.6 the two-layer bench, whose core states a material and no dielectric constant,
  came back with `(epsilon_r 4.5) (loss_tangent 0.02)` added to that row; the four-layer bench, whose
  dielectrics state both, came back tree-equal. `pcb-stackup-resave` therefore compares with the written
  node after giving each dielectric sheet KiCad's defaults for what it leaves out.
- **A dielectric row without a thickness** comes back with `(thickness 0)` on 10.0.6. The reader does not
  project such a row (`kicad.board.stackup-unmodelled`).
- **A loss tangent of 0** is what KiCad-written boards hold on solder mask rows (2 rows of the corpus), so
  the model accepts it; the proposal asked for a value above 0.
- `more`, `nopaste`, `order` and `nopaste-table` had been measured on 10.0.6 only; 9.0.9 gives the same
  outcomes.

## Corpus census

`tests/corpus/test_stackup_census.py`, run on 2026-10-07 on the boards of the local corpus cache that the
reader reads and that are not heavy items (21 boards; the census of 2026-10-05 in the proposal counted 24
readable boards and 18 nodes on another cache state):

| count | value |
|---|---|
| boards read | 21 |
| boards whose `setup` holds a node | 17 |
| of those, projected into `Board.stackup` | 17 |
| by copper count | 2: 11, 4: 4, 6: 1, 8: 1 |
| entries in the 17 stack-ups | 191 |
| dielectric entries by kind | `core` 21, `prepreg` 16 |
| sheets beyond the first of a row | 2 |
| finish | `None` 11, `ENIG` 3, `HAL lead-free` 2, `Immersion tin` 1 |
| `impedance_controlled` | 2 |
| `kicad.board.stackup-thickness` | 1 |
| entries with a loss tangent of 0 | 2 |

No board gave `kicad.board.stackup-unused` or `kicad.board.stackup-unmodelled`, no projected stack-up gave
a `model.stackup-*` finding, and `tests/corpus/test_board_rt1.py` passes with every opaque count unchanged.
