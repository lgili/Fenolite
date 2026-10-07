# Drawing probes (change c0117)

What `kicad-cli` showed for the facts the drawing kinds lean on (`docs/drawings.md`). The subject is the
bench of `tests/_drawdesign.py`, authored for Fenolite: a four-copper board of 76 × 92 mm at
(100 mm, 100 mm) with three through vias, one blind and one micro via, a header with two plated holes, a
part with a plated slot and an unplated hole, catalog chips on both sides (one do-not-populate) and a
capacitor that shows `${REFERENCE}` on `F.Fab`. Probes: `tests/kicad/drawings/_drawbench.py`; outcomes:
`docs/evidence/kicad/probes/<version>.json`; hypotheses: `docs/hypotheses.md`, `H-K-DRAW-*`.

Recorded on 2026-10-08 with the local `kicad-cli` 10.0.6 (macOS). The pinned 9.0.9 image was not run
that day, so the 9.0.9 column says "not recorded" and every hypothesis stays `INFERRED`.

| probe | hypothesis | 10.0.6 | 9.0.9 | control |
|---|---|---|---|---|
| `draw-table`, `draw-textbox`, `draw-dimension`, `draw-vars` | H-K-DRAW-ITEMS | `present` | not recorded | the plot of the copy without the item draws none of its texts |
| `draw-defvar-board`, `draw-defvar-sheet` | H-K-DRAW-ITEMS | `present` | not recorded | without `-D` the text is drawn as written |
| `draw-wrap-overflow` | H-K-DRAW-TEXT | `present` | not recorded | a short text in the same cell is one line |
| `draw-pitch`, `draw-glyph-bound` | H-K-DRAW-TEXT | `equal` | not recorded | two sizes; one wide glyph exceeds the bound of its advance alone |
| `draw-page-position`, `draw-mirror`, `draw-no-holes` | H-K-DRAW-PAGE | `equal` | not recorded | the moved line, the plot without `--mirror`, the default plot with its holes |
| `help-pcb-export-pdf-scale`, `help-pcb-export-svg-scale` | H-K-DRAW-PAGE | `present` | not recorded | (a recorded row) |
| `draw-default-sheet-A4` to `-A0` | H-K-DRAW-SHEET | `equal` | not recorded | the plot without the sheet draws no line |
| `draw-drill-files`, `draw-drill-counts` | H-K-DRAW-DRILL | `equal` | not recorded | a table without one row differs from the report |
| `draw-dnp-crossout`, `draw-dnp-hide`, `draw-values`, `draw-pads` | H-K-DRAW-ASSEMBLY | `present` | not recorded | the plot without the option |
| `draw-bottom-designator` | H-K-DRAW-ASSEMBLY | `equal` | not recorded | the text without `mirror` has other strokes |
| `draw-repeat-pdf`, `draw-repeat-report` | H-K-DRAW-REPEAT | `equal` | not recorded | two runs more than a second apart |
| `draw-layer-added` | H-K-DRAW-LAYER | `present` | not recorded | the copy without the texts draws none |

## What KiCad showed

- **Items.** A `table` whose children are `column_count`, `uuid`, `layer`, `border`, `separators`,
  `column_widths`, `row_heights` and `cells`, a `gr_text_box` with `(knockout no)`, and an orthogonal
  `dimension` in the form of `backends/kicad/drawing.py` load and are drawn. A cell's text is anchored at
  the cell's corner plus its margin. A dimension written with the cache text "9 mm" is drawn as
  "76.00 mm": KiCad computes the text. With a negative `height` the text of a horizontal dimension lies
  above its points and that of a vertical one left of them. `${TITLE}` and `${REVISION}` resolve from
  the title block; `-D NAME=value` sets a variable for one run, in a board text and in a drawing-sheet
  text.
- **Text.** Two lines of a text are 1.61 × the size apart (2.4149 mm at 1.5 mm). A line of n glyphs of
  advance a is n × a + 0.25 × the size long: 1, 2, 10, 20 and 40 repeats of `m` at 1.5 mm are 2.375,
  4.375, 20.375, 40.375 and 80.375 mm, and of `…` 2.5179, 4.6607, 21.8036, 43.2321 and 86.0893 mm. The
  widest advance of the measured set is that of `…`, 1.4286 × the size. The measurements of 2026-10-05
  divided the length of ten repeats by ten and took 1.45 × the size as the bound of a line; one `m` is
  longer than that, so `text_width` adds the constant. A note of 227 characters in a cell of
  80 × 6 mm is wrapped by KiCad into four lines that leave the row, which is why Fenolite breaks the
  lines itself.
- **Page.** At the default scale a line from (150, 30) to (250, 40) mm is drawn there, and with
  `--mirror` at W − x. The default plot of `Edge.Cuts` and `Dwgs.User` draws the pad holes (three circles
  and the slot) and no via hole; `--drill-shape-opt 0` draws none. `pcb export pdf` and `svg` have
  `--scale` on 10.0.6.
- **Default sheet.** The plotted pages are 297.0022 × 210.0072 (A4), 419.9890 × 297.0022 (A3),
  594.0044 × 419.9890 (A2), 840.9940 × 594.0044 (A1) and 1188.9994 × 840.9940 mm (A0). On each, KiCad's
  default sheet draws its borders 10 mm and 12 mm inside the page edges and its title block from
  (W − 120, H − 44) to (W − 12, H − 12) mm.
- **Drill.** `pcb export drill -o drawings/ --format excellon --excellon-units mm --excellon-separate-th
  --drill-origin absolute --generate-map --map-format pdf --generate-report` writes, for the bench,
  `<stem>-PTH.drl`, `<stem>-NPTH.drl` and `<stem>-front-in1.drl` (the blind and the micro via of `F.Cu`
  to `In1.Cu` share one file), a `-drl_map.pdf` beside each, and `<stem>-drill.rpt`. The report's second
  line is `Created on <date>`. Per drill file it has a head (`plated through holes:`, `unplated
  through holes:`, or `holes connecting layer pair: 'F.Cu and In1.Cu' (blind vias):`) and one line per
  tool: `T1  0.300mm  0.0118"  (3 holes))`, `T2  1.000mm  0.0394"  (3 holes)  (with 1 slot)`,
  `T1  3.200mm  0.1260"  (1 hole)`. A slot is counted with the round holes of its width. What a map
  draws was not probed: its legend is stroked text in a compressed stream.
- **Assembly.** On `F.Fab` with the outline, the bench draws 117 paths; `--crossout-DNP-footprints-on-fab-layers`
  119, `--hide-DNP-footprints-on-fab-layers` 90 (and no value text of the part), and
  `--sketch-pads-on-fab-layers` 192 with the pad numbers. `--exclude-value` is an option of the PDF
  export; `pcb export svg` 10.0.6 exits 1 for it, so the probe counts the text operators of the PDF.
  A `gr_text` with `(justify mirror)` on `B.Fab` in a `--mirror` plot has the strokes of the same text
  on `F.Fab` in a plain plot.
- **Repeat.** Two exports of both drawing kinds, more than a second apart, differ in the
  `/CreationDate` line of each PDF and in the `Created on` line of the report, and in nothing else.
- **Layers.** `tests/data/kicad/board/two_layer.kicad_pcb` has no `Dwgs.User`, `F.Fab` or `B.Fab`. With
  the rows `(17 "Dwgs.User" user "User.Drawings")`, `(35 "F.Fab" user)` and `(33 "B.Fab" user)` added at
  the end of its layer table it loads, and a text on each layer is drawn.

Every 10.0.6 run also wrote `<stem>.kicad_prl` beside the board in the run folder; `export` lists it under
`result.tool_writes` and never writes it.
