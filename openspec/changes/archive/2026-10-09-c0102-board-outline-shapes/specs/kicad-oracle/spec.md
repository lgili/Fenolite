## ADDED Requirements

### Requirement: Outline shapes and holes pass the oracle
`tests/kicad/board/test_outline_shapes.py`, `tests/kicad/board/test_holes.py` and `tests/kicad/zones/test_zone_box.py` (markers `needs_kicad`, major-aware) SHALL prove on the running `kicad-cli` what this change writes for outlines and holes. Each probe is registered in `tests/kicad/_probes.py` with its majors, and its outcome is recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`; built files MUST NOT be committed. Drill files are written with the options of `exports.plan`.
- **Arcs** (`H-K-OUTLINE-ARCS`), on a board of the running major's target with corners of radius 3 mm, a round cut-out, a horizontal slot and a slot turned 30°, first written through the model API with its edges as `Edge.Cuts` graphics, then built from a script with `board(outline=…)` and `cutout()`; the outcomes MUST be the same:
  - `outline-arcs-drc` (majors 9 and 10): `absent` when `pcb drc` reports no `invalid_outline`;
  - `outline-arcs-drill` (majors 9 and 10): `absent` when the drill files hold no hole that is not a pad's or a via's;
  - `outline-arcs-keep` (major 10): after `pcb upgrade --force`, `merge_outline` finds the edges signed and equal to the script's outline: `equal`.
- **Malformed outlines** (`H-K-OUTLINE-INVALID`), on six boards written by `write_board` with edge graphics: a round cut-out across the edge (`cross`), one touching it (`touch`), two overlapping (`overlap`), a self-crossing board ring (`selfx`), a cut-out inside a cut-out (`nested`) and a control (`inside`). `outline-invalid-<case>` records `present` when `invalid_outline` is reported: `cross` and `touch` `present` on 10 and `absent` on 9; `overlap` `present` on both; `selfx` `present` on 10 and `absent` on 9; `nested` and `inside` `absent` on both.
- **Copper outside** (`H-K-OUTLINE-OUTSIDE`), on a 50 mm × 30 mm board: `outline-outside-free` (majors 9 and 10) `absent` when a track and a via wholly outside get no `copper_edge_clearance`; `outline-outside-across` (majors 9 and 10) `present` when a track and a via across the edge each get one.
- **Zone box** (`H-K-ZONE-BOX`), on the board of the arcs with a zone whose outline is the box of the board ring, which a zone declared without an outline takes once the board is built from a script: `zone-box-fill` (major 10) `absent` when, after `pcb drc --refill-zones --save-board`, no fill vertex lies outside the board ring or inside a cut-out of `board_outline` and none lies closer to a ring than the board-setup edge clearance less 5 µm.
- **Holes** (`H-K-HOLE-FOOTPRINT`, `H-K-HOLE-COURTYARD`, `H-K-HOLE-SYMBOL`), on a board with a round hole and a slot that are not plated, a slot turned 30°, a plated hole on `GND`, a top part and a bottom part overlapping a hole's courtyard, and a part clear of it, first written through the model API and with authored footprints, then built from a script with `design.hole()`; the outcomes MUST be the same:
  - `hole-root-pad` (majors 9 and 10): a board with a root `(pad "" np_thru_hole …)` written by token edit, `reject` when `kicad-cli` cannot load it;
  - `hole-drill` (majors 9 and 10): `equal` when the NPTH file holds the round hole at its position with its diameter and each slot as one `G85` slot between its centres, and the PTH file holds the plated hole;
  - `hole-pos` (majors 9 and 10): `absent` when `pcb export pos` lists no hole;
  - `hole-courtyard-top` and `hole-courtyard-bottom` (majors 9 and 10): `present` when `courtyards_overlap` names the hole and the top part, and the hole and the bottom part; `hole-courtyard-clear`: `absent` for the part clear of it;
  - `hole-symbol-load` (majors 9 and 10): `equal` when `kicad-cli sym export svg` exports both symbols of a library written by `sym.write_symbol_library` that holds a symbol without pins and one with one passive pin, both with `in_bom` false, as `holes.hole_symbol` makes them; on a build, the library is `lib/Fenolite_Holes.kicad_sym`.
- An outcome other than the one stated MUST stop the part of this change that rests on it, and the register row MUST record what KiCad showed.

#### Scenario: Arcs load and are not drilled
- **WHEN** `uv run pytest tests/kicad/board/test_outline_shapes.py -k arcs -rA` runs on 10.0.6 and in the `kicad-9` job
- **THEN** `outline-arcs-drc` and `outline-arcs-drill` are `absent` on both majors, and `outline-arcs-keep` is `equal` on 10.0.6

#### Scenario: KiCad's verdict on malformed outlines
- **WHEN** `uv run pytest tests/kicad/board/test_outline_shapes.py -k invalid -rA` runs on both majors
- **THEN** each `outline-invalid-<case>` records the outcome stated above, and `check_outline` gives `kicad.outline.invalid` for every case but `inside`

#### Scenario: Holes are drilled as declared
- **WHEN** `uv run pytest tests/kicad/board/test_holes.py -rA` runs on 10.0.6 and in the `kicad-9` job
- **THEN** `hole-root-pad` is `reject`, `hole-drill` and `hole-symbol-load` are `equal`, `hole-pos` and `hole-courtyard-clear` are `absent`, and `hole-courtyard-top` and `hole-courtyard-bottom` are `present`, on both majors

#### Scenario: The zone box fills the board only
- **WHEN** `uv run pytest tests/kicad/zones/test_zone_box.py -rA` runs on 10.0.6
- **THEN** `zone-box-fill` is `absent`

### Requirement: Outline and layer changes pass the oracle
`tests/kicad/lens/test_outline_rebuild.py` and `tests/kicad/lens/test_layer_change.py` (markers `needs_kicad`, major-aware) SHALL prove that a board adapted by "Outline changes across rebuilds" and "Copper layer changes across rebuilds" (`layout-lens`) is one that KiCad accepts, with the probe rules of "Outline shapes and holes pass the oracle".
- **Layer facts** (`H-K-LAYER-CHANGE`), on a four-layer build of the running major's target, edited by token: `layers-added` (majors 9 and 10) `absent` when the rows `In3.Cu` (8) and `In4.Cu` (10) give no DRC finding that the unedited board lacks and the Gerber job file lists six copper layers; `layers-left-items` (majors 9 and 10) `present` when items left on removed rows give `item_on_disabled_layer`; `layers-stale-stackup` (majors 9 and 10) `present` when a four-copper stack-up under six or two rows leaves the job file without thicknesses.
- **Rebuilds** (major 10, where `fenolite build` and `fill` run end to end):
  - `rebuild-outline` `absent` when a routed blink rebuilt on a smaller outline, its copper that no longer fits dropped, gives no `invalid_outline` and no `copper_edge_clearance`, and its unconnected items are those of the dropped tracks;
  - `rebuild-layers` `absent` when a routed four-layer build rebuilt with six copper layers and then with two gives no `item_on_disabled_layer` and a job file with thicknesses each time.

#### Scenario: Layer facts on both majors
- **WHEN** `uv run pytest tests/kicad/lens/test_layer_change.py -k facts -rA` runs on 10.0.6 and in the `kicad-9` job
- **THEN** `layers-added` is `absent`, and `layers-left-items` and `layers-stale-stackup` are `present`, on both majors

#### Scenario: Adapted boards pass DRC
- **WHEN** `uv run pytest tests/kicad/lens/test_outline_rebuild.py tests/kicad/lens/test_layer_change.py -k rebuild -rA` runs on 10.0.6
- **THEN** `rebuild-outline` and `rebuild-layers` are `absent`
