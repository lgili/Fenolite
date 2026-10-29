# The ink of a KiCad text

`fenolite.backends.kicad.textink` reads the ink of stroke-font texts from what `kicad-cli` draws, and
`fenolite.silk.extents` estimates it from a table of glyph metrics when no tool is at hand. This page lists
the KiCad facts both rely on, in Fenolite's own words. Every fact here was measured with `kicad-cli` 10.0.7
(S-0020) on texts and boards authored for Fenolite; KiCad's font and source code were not read. The user
guide is `docs/assembly.md`, "Designators"; the command is `fenolite silk` (`docs/cli-contract.md`).

A measurement writes the texts as `gr_text` items on `F.SilkS` of a scratch board, one per cell of a grid,
runs `kicad-cli pcb export svg -l F.SilkS --mode-single --exclude-drawing-sheet` once, and reads each
text's group back. The glyph table `src/fenolite/silk/data/glyphs.toml` is written by
`tools/measure_glyphs.py` in the same way: it holds, per glyph, the box of its drawn ink and its advance,
never the strokes of a glyph.

## How a text is drawn

| fact | source | label | hypothesis |
|---|---|---|---|
| The SVG plot holds each stroke-font text as one `<g class="stroked-text">` group whose `desc` is the text and whose `<path>` elements are the centre lines of its strokes (`M x y L x y`), in board millimetres with four decimals; the stroke width is in the `style` of an enclosing `<g>`, with round caps; the page frame of `--exclude-drawing-sheet` is the board frame | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SILK-INK |
| The ink of a text is the box of its centre lines grown by half the drawn stroke on each side | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SILK-INK |
| The stroke drawn is the text's `thickness`, at most a quarter of the smaller of the glyph width and height: a stroke of 0.3 mm at 0.5 mm is drawn at 0.125 mm, at a width of 1 mm and a height of 0.8 mm at 0.2 mm | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SILK-INK |
| A centred text's ink spans in x a fixed multiple of the glyph width, the same at every stroke; its glyphs follow each other by their advances, and the centre is half the sum of the advances: `R12` at 1 mm draws its centre lines from x -1.2143 mm to 1.2619 mm at strokes of 0.15 mm and 0.3 mm, at 0.6 mm wide from -0.7286 mm to 0.7571 mm | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SILK-ESTIMATE |
| A centred text's capital glyphs span one glyph height up from a baseline that lies 0.4626 x the height less 0.052 x the drawn stroke below the anchor: `R12` at 1 mm and 0.15 mm from y -0.5452 mm to 0.4548 mm | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SILK-ESTIMATE |
| A `left` or `right` justification moves the ink by half the sum of the advances plus 0.658 x the drawn stroke, toward +X or -X; `top` or `bottom` moves it by 0.585 x the glyph height, down or up, at every stroke and width | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SILK-ESTIMATE |
| A footprint field is drawn with its anchor at `at + R(θ)·local` and at its board angle; a `mirror` text runs toward -X; a field at 180° or 270° is drawn as at 0° or 90° (keep upright); the box of a field at 90° is the box at 0° mirrored first, then turned as a footprint turns a point | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SILK-INK |

## What the DRC reports about texts

| fact | source | label | hypothesis |
|---|---|---|---|
| With the project rules that Fenolite writes, a silkscreen text lower than 0.8 mm is reported as `text_height` and one thinner than 0.08 mm as `text_thickness`, both warnings that name the board setup's limits | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SILK-DRC |
| A silkscreen text that crosses the board edge is reported as `silk_edge_clearance` ("Silkscreen clipped by board edge"); one 0.05 mm inside the edge is not, since the silkscreen clearance of those rules is 0 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SILK-DRC |
| A footprint's `Reference` over its own pads is reported as `silk_over_copper`, and over its own silkscreen strokes or another footprint's text as `silk_overlap` | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SILK-DRC |

The two benches of `tests/_silkbench.py` show the last row before `fenolite silk` runs, and none of the
five types after it (`tests/kicad/silk/test_designators_oracle.py`). The 9.0 side of every row waits for
the `kicad-9` job of CI.
