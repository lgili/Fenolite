## Why

Package 8 of change c0175 ("Assembly marks"). A board's designators are its most visible marks: the
assembler, the tester and the repairer read them. A footprint drops its `Reference` on its own centre, over
its pads, and a dense board leaves dozens of texts on copper, on each other and across the neighbours.
KiCad's DRC lists them (`silk_over_copper`, `silk_overlap`), but nothing in Fenolite moves them, and placing
them by hand is slow. Doing it by estimate is the usual failure: the text box guessed by eye is too small.
So the placement needs the real ink of each text, measured with the tool that draws it, and a check of
every place it writes.

## What Changes

- **Text ink, measured.** `backends.kicad.textink` writes texts on a scratch board, runs `kicad-cli pcb
  export svg` once and reads each text's ink from its `stroked-text` group. `silk.extents` caches the boxes
  per tool version, string, size, stroke and justification, and without a tool estimates them from a glyph
  table that the new `tools/measure_glyphs.py` measured with `kicad-cli` (boxes and advances, no glyph
  shape). New format page `docs/formats/kicad/text.md`.
- **Designator placement.** `silk.layout` (candidates, cost, grouped rows and columns, greedy search with
  repair) and `silk.board` (obstacles of a KiCad board, the write into the `Reference` field, the check of
  the written board).
- **Command** `fenolite silk PATH --designators [--keep] [--refs GLOB]... [--sizes LENGTHS] [--angles 0,90]
  [--clearance LENGTH] [--gap LENGTH] [--measure auto|kicad|estimate] [-o FILE] [--drc] [--kicad-cli PATH]`
  under the mutation protocol; six `silk.*` codes; hypotheses `H-K-SILK-INK`, `H-K-SILK-ESTIMATE`,
  `H-K-SILK-DRC`.
- The generated `commands` page of the agent guide may hold 700 lines instead of 600: the new command's
  options do not fit in the old budget.

## Capabilities

### New Capabilities

- `silkscreen-layout`: "Text ink extents", "Glyph table", "Designator placement", "Designator search",
  "Placed designators checked" and "Silk command". The capability holds the tools that lay out the
  silkscreen of a board, every placement checked before it is written.

### Modified Capabilities

- `agent-guide`: "Page budgets and writing rules" (a generated page may hold 700 lines).

c0175 keeps the rest of its `silkscreen-layout` delta ("Silkscreen clipping", task 9.3) and its
`assembly-test-features` delta ("Test-point placement", task 9.4).

## Non-goals

- **Silkscreen clipping** (`--clip`, c0175 task 9.3): it cuts the footprints' own graphics, so the change
  must reach the library ("Library made from a board", package 10), which does not exist yet.
- **Test-point placement** (`testpoints --place`, c0175 task 9.4): it adds parts and copper that the
  board's design script lacks, so a rebuild would drop them unless `sync` carries them back; its site
  search needs the copper clearance of each new probe and joining track against every net, and a
  fixture-pitch spread. It is a package of its own, built on `checks.copper`, left for a later change with
  its own bench.
- **A placement record beside the board** (`silk-placements.toml` in c0175's spec): a rebuild already keeps
  a board's footprint fields (`docs/lens.md`, "Footprint fields"), so the record would repeat it.
- **TrueType texts and texts at angles other than multiples of 90°**: a designator is written at 0° or 90°
  in the stroke font; other texts are boxed conservatively as obstacles.
- **Part bodies other than courtyards** as obstacles: the courtyard stands for the body.

## Evidence level required

`INFERRED` without `--drc` (`H-K-SILK-DRC`, with `H-K-SILK-INK` for measured ink or `H-K-SILK-ESTIMATE`
for estimated ink). `KICAD-VERIFIED` for the board written with `--drc`, judged by `kicad-cli` on the exact
bytes. The facts of `docs/formats/kicad/text.md` are `KICAD-VERIFIED (10.0.x)`, measured with `kicad-cli`
10.0.7 on 2026-10-28; the oracle tests run in the jobs `kicad-9` and `kicad-10`.

## Impact

- New: `src/fenolite/silk/` (with `data/glyphs.toml`), `src/fenolite/backends/kicad/textink.py`,
  `src/fenolite/cli/cmd_silk.py`, `tools/measure_glyphs.py`, `docs/formats/kicad/text.md`,
  `tests/_silkbench.py`, `tests/data/kicad/silk/row.kicad_pcb`, `tests/unit/silk/`, `tests/kicad/silk/`.
- Changed: `backends/kicad/cli.py` (`export_layers_svg`), `cli/_examples.py`, `cli/explain.py`,
  `cli/data/explain.toml`, `tests/unit/test_import_graph.py` (row `silk`), `tests/unit/agent/test_pages.py`
  (budget, page words), `tests/unit/cli/test_paging.py` (the paged `silk`, and `tidy` of c0208, which the
  list lacked), `docs/evidence/matrix.md` (generated again), `docs/cli-contract.md`, `docs/assembly.md`, `docs/hypotheses.md`,
  `docs/evidence/sources.md` (S-0020), `LEGAL-ANNEX.md`, the guide page `board-assembly` and the generated
  `commands`, `CHANGELOG.md`, and c0175's `tasks.md`, `design.md` and `specs/silkscreen-layout/spec.md`.
