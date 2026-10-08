## Context

**The check.** `lens.altium_copper.match_source` matches each component of the design with one footprint of the copper source and compares `(number, x, y)` of every pad of that footprint with the pads of the definition that the build writes to `<name>.PcbLib` (`footprints[link].defn.pads`). The source's pads are `FootprintInstance.pads`, as `backends.kicad.pcb.read_board` reads them for a board, or as `lens.build.build_design` places them for script copper (`embed.place_footprint`).

**The frame of those pads.** Recorded in `docs/formats/kicad/board.md`:

| Fact | Evidence | Hypothesis |
|---|---|---|
| The stored children of a bottom footprint are the library footprint mirrored about local X (DRC library parity: no mismatch for 12 bottom placements, one for an unmirrored control) | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `H-G-BOTTOM-STORE` |
| For a bottom footprint, absolute = `at + R(θ)·stored`, with no further mirror | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `H-G-BOTTOM-PLACE` |
| "Pad frame": `Pad.position` is the stored footprint-local position; bottom footprints keep their stored, mirrored coordinates | the reader's contract | — |

So the stored pad of a bottom footprint is `(x, −y)` of the library pad `(x, y)`, at every rotation: the rotation is applied only when the board places the footprint. `embed.place_footprint` writes a bottom footprint in that form (`board.md`, "Placed footprints", `KICAD-VERIFIED`), so the model of script copper holds the same mirrored pads. No new format fact is needed; this change records none.

**Reproduction** (dev 695574b). The blink with `U1` (`Mini:Mini_QFP-32_7x7mm_P0.8mm`, authored for Fenolite in `tests/data/libs/`) placed with `side="bottom"` at 90°: `fenolite build` for KiCad exits 0, and `--target altium --copper-from` that board exits 5 with `U1: the pads of Mini:Mini_QFP-32_7x7mm_P0.8mm differ from the footprint the design resolves (pad 1)`. The same at 0°, with the map `{"1": "2", "2": "1"}`, and for script copper on `U1` without `--copper-from`. With the board's `U1` pads written unmirrored (a board KiCad reports as a library mismatch) the build was accepted.

## Decisions

1. **Undo the mirror on the source side.** `library_pad_positions(footprint)` gives `(number, x, −y)` for a footprint whose `side` is `bottom` and `(number, x, y)` otherwise; `match_source` compares that with the definition. The definition stays as it is, so the top-side comparison is the same expression as before and every pinned build keeps its bytes (the check writes nothing).
2. **No rotation.** The stored positions are footprint-local and unrotated on both sides (`board.md`, "Pad frame"); the tests put the bottom part at 0° and 90° to hold that.
3. **A KiCad oracle beside the unit tests.** `tests/kicad/altium/test_copper_from_bottom_oracle.py` (`needs_kicad`, skipped before 10.0 because `pcb import` needs it) imports the written `PcbDoc` with `kicad-cli pcb import --format altium` and asserts that every pad lies where the source board has it, relative to the outline corner within 10 nm, that `U1` is on the bottom at the source's rotation, and that KiCad's own writer stores its pads so that `library_pad_positions` gives the definition. It did not run here (no `kicad-cli` in the container); CI runs it.

## Measurements

- The unit tests on dev 695574b with the old comparison: the 9 new tests fail (the negative control because the unmirrored board was accepted). With the fix: 9 passed.
- The written `PcbDoc` of each accepted build holds every pad where the KiCad board has it, up to one shift of the frame, within 2 nm (`AltiumBackend.board_pads` against `KicadBackend.board_pads`).
- Script copper on the bottom `U1` at 90° and the same script's board through `--copper-from` give byte-equal `PcbDoc` files.

## Known gaps

- The oracle is owed a run on KiCad 10.x in CI. Should it fail, the defect is in how the Altium document or KiCad's importer places a bottom footprint, not in this check: the unit tests already hold the written pads to the KiCad board's.
