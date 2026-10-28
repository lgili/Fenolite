## Why

Task 9.3 of change c0175 ("Assembly marks", package 8), `fenolite silk --clip`. A footprint's silkscreen
outline often runs over its own pads, and a part placed close to another crosses the neighbour's pads.
The fabricator clips silkscreen at every mask opening anyway, so the ink that is printed is not the ink
that was drawn, and KiCad's DRC reports each crossing as `silk_over_copper`. Change c0212 placed the
designators and left the clip out, because cutting a footprint's own graphics on the board makes the
footprint differ from its library: the next update from the library brings the ink back ("Silkscreen
that came back" in the agent guide). Change c0223 now makes a library from a board (`fenolite library
--out`) and reports the drift (`--diff`), so the clip can keep the library in step.

## What Changes

- **Cut.** `fenolite silk PATH --clip [--margin LENGTH]` cuts every silkscreen stroke of the board and of
  its footprints (lines, arcs, circles, outlines of rectangles and polygons) where its ink comes within
  `--margin` of a mask opening (a pad's copper grown by its mask expansion) or a pad's hole. The pieces are
  written as lines and arcs; a piece shorter than its stroke is dropped. Filled shapes and texts are not
  cut (`silk.clip-skipped`).
- **Margin.** By default the largest minimum of the project's `silk_clearance` rules, else 0: what KiCad's
  DRC applies between silkscreen and pads (measured, `docs/formats/kicad/drc.md`).
- **Check.** Every piece is judged again, exactly, against every opening before anything is written
  (`silk.check-failed`).
- **Library in step.** A footprint's own graphics are cut by its own openings once per footprint and
  identically on each instance, so `fenolite library` makes one footprint of them. Each changed footprint
  is reported once (`silk.footprint-changed`, info) with the command that makes or compares the library;
  a cut by another part's opening makes that instance differ (`silk.cut-by-other`, warning).
- **With designators.** `--clip` and `--designators` may run together: the clip first, then the
  designators placed against the clipped strokes. `--drc` judges the written board as before.
- Two new hypotheses: `H-K-SILK-MASK` (what KiCad's `silk_over_copper` measures) and `H-K-SILK-CLIP` (a
  clipped board gives no `silk_over_copper` and nothing new).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `silkscreen-layout`: ADDED "Silkscreen clipping" (moved from c0175 and narrowed), "Clipped strokes
  checked", "Clipped footprints and their library" and "Clip options".

c0175 no longer holds a delta of `silkscreen-layout`; its task 9.4 (`testpoints --place`) stays there.

## Non-goals

- **Cutting texts.** A text over a pad is moved, not cut: `--designators` moves the `Reference`; other
  texts are reported with `--drc` only.
- **Cutting at the board edge, at vias and at other silkscreen** (`silk_edge_clearance`, `silk_overlap`):
  the clip removes ink only, so it never adds those findings; the oracle checks that they do not grow.
- **A footprint's own `solder_mask_margin`** (on the footprint, not on a pad) and **mask-only pads** (a
  mask layer without copper on that side): not read; KiCad's DRC measures to the copper, which the cut
  always clears.
- **Writing the library.** `silk` writes the board only; `fenolite library BOARD --out LIB.pretty` writes the
  library, and `--diff LIB` compares it.

## Evidence level required

`INFERRED` without `--drc` (`H-K-SILK-CLIP`, with `H-K-SILK-MASK`); `KICAD-VERIFIED` for the board written
with `--drc` and no new finding. The facts of `docs/formats/kicad/drc.md`, "Silkscreen over pads", are
measured with `kicad-cli` 10.0.7 on 2026-10-28 (`KICAD-VERIFIED (10.0.x)`); the oracle tests
run in the jobs `kicad-9` and `kicad-10`.

## Impact

- New: `src/fenolite/silk/cut.py`, `src/fenolite/silk/clip.py`, `tests/unit/silk/test_cut.py`,
  `tests/unit/silk/test_clip.py`, `tests/kicad/silk/test_clip_oracle.py`, and the bench parts of
  `tests/_silkbench.py` (`BOXED`, `DOT`, `probe`, `clipped`). No test data file is added: the benches are
  written in the tests.
- Changed: `src/fenolite/backends/kicad/fpitems.py` (the graphic children of a footprint and their
  replacement), `src/fenolite/cli/cmd_silk.py`, `src/fenolite/silk/codes.py`,
  `cli/data/explain.toml`, `docs/cli-contract.md`, `docs/assembly.md`, `docs/formats/kicad/drc.md`,
  `docs/evidence/sources.md` (S-0020), `docs/hypotheses.md`, `docs/evidence/matrix.md`, the guide page
  `board-assembly` and the generated `commands`, `CHANGELOG.md`,
  `openspec/README.md`, and c0175's `tasks.md`, `design.md`, `proposal.md` and its `silkscreen-layout`
  delta (removed).
