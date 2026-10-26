## Why

Milestone v0.4, a correction. A board in which a zone or a rule area holds its layers under the singular head with a wildcard or a mask, `(layer "*.Cu")` or `(layer "F&B.Cu")`, is read by Fenolite (the wildcard is expanded, the child is kept as written) and then cannot be written back at all: every command that rewrites the board is refused with exit 7, `field 'layers' cannot be written from the model: (layer "*.Cu") is kept as written`, although nothing was changed. The plural head, `(layers "*.Cu")` and `(layers "F&B.Cu")`, writes. It was first seen as `fenolite route` exiting 7.

Measured on 2026-10-08 (design, Context):

- **The released 0.2.1 has the defect, and so does the base of this change** (`v04` at `19ab2ad1`), with the same messages: `read_board` then `write_board` (`LossyWriteError`), `route`, `place` and a rebuild with `build` exit 7 with `FEN-7001`. A zone with one layer under the singular head, `(layer "F.Cu")`, was never affected.
- **KiCad 10.0.6 does not load such a board** ("One or more items were found on undefined layers (*.Cu)", exit 3), for a rule area and for a copper zone, and neither a list of names under `layer`. It loads the plural forms and saves them as explicit names. So the board is one that Fenolite reads and KiCad 10 refuses, not one that KiCad writes: none of the 2 291 zones and rule areas of the 25 cached public corpus boards holds anything but one name under `layer`. Which program wrote the board that was first seen is not known, and whether KiCad 9 loads the form was not measured.

The defect is still Fenolite's: a board that it reads without an error must be written back as it was read, and a refusal that names a field nobody changed tells the user nothing true.

## What Changes

- **A board whose zone or rule area holds its layers under `layer` with a wildcard or a mask can be rewritten.** In the writer's comparison of a kept child with the model, `layer` and `layers` of a zone or rule area are one family: the layers a child names are compared, wildcards expanded, whichever head holds them. An unchanged child is kept as written, under the head the file used, and no second layer child is written.
- **A zone whose only layer was written under `layers`, `(layers "B.Cu")`, keeps that child** when the board is written back unchanged. Before, it was written again as `(layer "B.Cu")`. KiCad reads both and writes the second.
- **A change of the layers of a zone whose child holds a wildcard or a mask is refused under both heads** with `kicad.board.projection-read-only`, as it already was under `layers`. Under `layer` 0.2.1 answered by accident of the atom count: it wrote the new single layer over a wildcard child, and for a list of names it kept the old child without a word.
- Nothing else of the writer moves: a zone with plain names is written by the number of its layers, `layer` for one and `layers` for several, as before, and KiCad 10.0.6 saves those forms again unchanged.
- The facts are recorded: what the corpus holds, what KiCad 10.0.6 loads and what it saves (`H-K-ZONE-LAYER-HEAD`).

Size: 0.25 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `kicad-file-backend`: ADDED "Singular and plural layer heads of a zone".

## Non-goals

- A warning or an error of the reader for a zone whose `layer` child names several layers, although KiCad 10.0.6 refuses the board: a decision for the maintainer (design, Open question). This change keeps the reader as it is.
- Writing a changed layer set over a wildcard child (replacing `(layers "*.Cu")` by explicit names): nowhere here, because it would move the answer for the plural head, which 0.2.1 refuses by the rule of "Projected fields on write" (design, Open question).
- `fenolite fill` on such a board: `kicad-cli` cannot load it, so the fill fails with the tool's exit code; nothing in the writer changes that.
- Wildcards of pad layer lists: unchanged.

## Evidence level required

- `H-K-ZONE-LAYER-HEAD`: `KICAD-VERIFIED (10.0.x)` by eleven probes on the local `kicad-cli` 10.0.6. Nothing was run on 9.0.9; the probes are registered for major 10 only.
- The corpus counts: `CORPUS-VERIFIED`, by a count over the cached boards.
- The writer's comparison: mechanical, unit scenarios.

## Impact

- Changed: `src/fenolite/backends/kicad/pcb.py` (the kept-child comparison of `_Writer.reconcile`, `_spelling_only`; new `ZONE_LAYER_HEADS` and `_zone_layers_key`), `tests/kicad/_probes.py`, `docs/evidence/kicad/probes/10.0.6.json`, `docs/formats/kicad/board.md`, `docs/hypotheses.md`, `LEGAL-ANNEX.md`, `CHANGELOG.md`, `docs/evidence/matrix.md` (generated).
- New: `tests/unit/backends/kicad/test_pcb_zone_layer_heads.py`, `tests/unit/cli/test_route_zone_layer_head.py`, `tests/kicad/board/_zonelayers.py`, `tests/kicad/board/test_zone_layer_heads.py`.
- New names: hypothesis `H-K-ZONE-LAYER-HEAD`; eleven probe ids `pcb-zone-layers-*`. No issue code, no message, no CLI flag, no model field, no source id, no test data file.
- The product-code part is written in lines that exist at the tag `v0.2.1`, so that it can be applied to a correction release of 0.2 (design, "Applying to 0.2.1").

## Prerequisites

None. No change of v0.4 must land first, and none waits for this one.
