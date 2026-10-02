# KiCad drawing sheets (`.kicad_wks`)

A drawing sheet (also called a worksheet or page layout) draws the frame, the reference zones and the
title block around a board or a schematic. `fenolite.backends.kicad.wks` reads and writes these files,
and `fenolite.templates` builds them from a neutral specification. This page describes the format in
Fenolite's own words; sources are listed in `docs/evidence/sources.md`. The probes that settle the
hypotheses are in `tests/kicad/sheets/`; they judge a sheet by what `kicad-cli` draws, never by its exit
code.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| The root is `kicad_wks`; KiCad still reads the older roots `page_layout` and `drawing_sheet` | S-0035, S-0032, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-WKS-ORACLE |
| The header is `(version 20231118)` for majors 8, 9 and 10, then `(generator …)`; `generator_version` is optional, and a sheet without it loads on 9.0 and 10.0 | S-0032, S-0035, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-WKS-ORACLE |
| `setup` holds `textsize` (width and height), `linewidth`, `textlinewidth` and the four margins `left_margin`, `right_margin`, `top_margin` and `bottom_margin` | S-0035 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-WKS-ORACLE |
| The items are `line` and `rect` (`start`, `end`), `tbtext` (its text, then `pos`), `polygon` (`pts` of `xy`) and `bitmap` (`pos`, `scale`, `pngdata`); each may hold `name`, `comment`, `option`, `repeat`, `incrx` and `incry`, a `tbtext` also `incrlabel`, `font` (`size`, `bold`, `italic`), `justify`, `rotate`, `maxlen` and `maxheight` | S-0035, S-0036 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-WKS-ORACLE |
| A point takes an optional corner atom `ltcorner`, `lbcorner`, `rtcorner` or `rbcorner`; it is an offset from that corner of the margin box (the page minus the setup margins), positive toward the interior | S-0035, S-0075, S-0076, S-0020 | INFERRED | H-K-WKS-CORNER |
| A point without a corner atom uses the right-bottom corner | S-0075, S-0076, S-0020 | INFERRED | H-K-WKS-CORNER |
| `repeat N` with `incrx` and `incry` draws copies, each offset by one more step in the same corner frame, until N copies or until a copy's start point leaves the margin box | S-0075, S-0020 | INFERRED | H-K-WKS-REPEAT |
| `incrlabel` steps a one-letter text through the alphabet and a number by its value per copy; numbers step past `9` (`10`, `11`, `12` are drawn); without `incrlabel` the step is 1, and `(incrlabel 0)` repeats the same text | S-0075, S-0036, S-0020 | INFERRED | H-K-WKS-REPEAT |
| On a board export, which is page 1 of 1, `(option page1only)` items are drawn and `(option notonpage1)` items are not | S-0036, S-0075, S-0020 | INFERRED | H-K-WKS-PAGE1 |
| The value atoms `ltcorner`, `lbcorner`, `rtcorner`, `rbcorner`, `page1only`, `notonpage1`, the `justify` values `left`, `center`, `right`, `top` and `bottom`, and the `font` flags `bold` and `italic` load; an unknown value atom (`bogcorner`) makes the load fail with the message | S-0035, S-0036, S-0020 | INFERRED | H-K-WKS-VALUES |
| The text variables of a sheet are `${KICAD_VERSION}`, `${#}`, `${##}`, `${COMMENT1}` … `${COMMENT9}`, `${COMPANY}`, `${FILENAME}`, `${ISSUE_DATE}`, `${LAYER}`, `${PAPER}`, `${REVISION}`, `${SHEETNAME}`, `${SHEETPATH}` and `${TITLE}` | S-0075, S-0076 | INFERRED | H-K-WKS-VARS |
| On a board, the `title_block` fills `${TITLE}`, `${ISSUE_DATE}`, `${REVISION}`, `${COMPANY}` and `${COMMENT1}` … `${COMMENT3}`; `${PAPER}` gives the paper name as the board writes it (`A4`, `User`); `${FILENAME}` the board's file name; `${#}` and `${##}` give `1`; a `text_variables` member of the project fills `${NAME}`; an undefined `${NAME}` is drawn literally | S-0001, S-0075, S-0020 | INFERRED | H-K-WKS-VARS |
| KiCad still resolves the legacy `%` text codes in a sheet: `%T` draws the title and `%R` the revision, in a `page_layout` root and in a `kicad_wks` 20231118 root alike | S-0058, S-0020 | INFERRED | H-K-WKS-PCT |
| S-0035 states a 1 µm minimum internal unit, so at most three decimal places, but KiCad draws a finer length as written: a line start written 50.0006 mm from `ltcorner` with 10 mm margins is drawn at 60.0006 mm | S-0035, S-0020 | INFERRED | H-K-WKS-RES-2 |
| A bitmap is a PNG written as `pngdata` with at most 32 space-separated hexadecimal bytes per `data` row; `scale` is a decimal | S-0035, S-0020 | INFERRED | H-K-WKS-BITMAP |
| A `pngdata` whose bytes are not a PNG still loads the sheet and draws its texts; only the image decoder's log line, absent for a good PNG, tells them apart | S-0020 | INFERRED | H-K-WKS-BITMAP |
| Bitmaps are plotted only by the PDF and PostScript plotters; the SVG export draws none | S-0075, S-0076 | INFERRED | H-K-WKS-BITMAP |
| A sheet that fails to load prints "Error loading drawing sheet", the default sheet is drawn and the exit code is 0 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-WKS-ORACLE |
| A `--drawing-sheet` path naming a missing file, and a project `page_layout_descr_file` naming a missing file, fall back to the default sheet silently: exit 0 and no message | S-0020 | INFERRED | H-K-WKS-FALLBACK |
| The project key `pcbnew.page_layout_descr_file`, holding a project-relative name or `${KIPRJMOD}/<name>`, gives the sheet that `pcb export svg` draws without `--drawing-sheet` | S-0045, S-0075, S-0020 | INFERRED | H-K-PRO-WKS |
| `pcb export svg <board> -l Edge.Cuts --mode-single [--drawing-sheet <file>]` writes the page size in mm as the SVG `width` and `height`; each drawn sheet text is written again as a hidden `<text opacity="0">` with the resolved string, its x at the text anchor and its y within half the text height of it; sheet lines and rectangles are `<path>` elements, and glyph strokes sit in `<g class="stroked-text">` groups | S-0022, S-0037, S-0020 | INFERRED | H-K-WKS-SVG |

## Fenolite choices

- **Corner atoms on write.** The writer omits `rbcorner`, as c0007's authored skeleton does, so a point
  without a corner atom means `rb` both ways. A read point that spells `rbcorner` is kept as an opaque
  slot, so the file rebuilds tree-equal.
- **Child order.** `wks.CANONICAL_ORDER` gives the child order per head. For the names S-0035 describes
  it follows the order of S-0035's syntax descriptions: `setup` (`textsize`, `linewidth`,
  `textlinewidth`, `left_margin`, `right_margin`, `top_margin`, `bottom_margin`); `line` and `rect`
  (`name`, `start`, `end`, `repeat`, `incrx`, `incry`, `comment`); `tbtext` (the text, `name`, `pos`,
  `font`, `repeat`, `incrx`, `incry`, `comment`); `bitmap` (`name`, `pos`, `scale`, `repeat`, `incrx`,
  `incry`, `comment`, `pngdata`). The names S-0035 does not describe (`linewidth` of an item, `justify`,
  `rotate`, `maxlen`, `maxheight`, `incrlabel`, `option`; names from S-0036) are placed by Fenolite as
  c0007's authored skeleton places them, which loads on both majors: `linewidth` after `end`; `justify`,
  `rotate`, `maxlen` and `maxheight` after `font`; `incrlabel` after `incry`; `option` last before
  `pngdata`. Load on both majors is the proof; byte identity with KiCad-written sheets is not claimed.
- **Defaults written only when they differ.** `repeat`, `incrx` and `incry` are written only when they
  differ from 1, 0 and 0, and `incrlabel` only when the label step is not 1, because KiCad steps labels
  by 1 when `incrlabel` is absent.
- **Whole micrometres.** KiCad draws finer lengths unchanged (`H-K-WKS-RES-2`), but Fenolite models whole
  micrometres only: the writer refuses a modelled length that is not a multiple of 1 000 nm
  (`kicad.wks.below-resolution`), and the reader keeps an item with such a length opaque
  (`kicad.wks.kept-opaque`). No rounding is ever applied.
- **Neutral tokens.** Texts hold neutral tokens in the model (`{title}`, `{doc_id}`, `{param:NAME}`, …);
  `wks.KICAD_TOKENS` maps them to KiCad variables. KiCad-only variables, a malformed `${` and a `%`
  followed by an ASCII letter keep a read item opaque, and the writer refuses a text that would produce
  them, because KiCad would resolve them (`H-K-WKS-PCT`).
- **One output for both majors.** The writer writes `(version 20231118)` and `(generator "fenolite")`
  without `generator_version`, so the same bytes serve KiCad 9.0 and 10.0; the target selects only the
  emit check.

## Issue codes

| code | severity | when |
|---|---|---|
| `kicad.wks.kept-opaque` | info | an item or child kept opaque on read, with the reason |
| `kicad.wks.legacy-root` | info | a `page_layout` or `drawing_sheet` root on read |
| `kicad.wks.uninventoried` | error | a name with no inventory row on write |
| `kicad.wks.unknown-value` | error | a value atom outside `VALUE_ATOMS` on write |
| `kicad.wks.below-resolution` | error | a modelled length that is not a whole micrometre on write |
| `kicad.wks.param-reserved` | error | a `{param:X}` with X a reserved KiCad variable |
| `kicad.wks.literal-variable` | error | a `${`, or a `%` followed by an ASCII letter, in the written text that no token produced |
| `kicad.wks.dropped-item` | warning | an opaque item dropped under `allow_lossy` |

Code in groups 4 to 10 is written from this page.
