## Context

- **Plan item.** Plan item 0012 asks for sheet templates in `*.sheet.toml` (sizes A0 to A5, Letter, Legal, Tabloid and custom; orientation and margins; a frame with reference zones after ISO 5457; an optional logo; a title block as a cell grid with neutral tokens and ISO 7200 field names; `[provenance]` headers), the command `template build`, one `.kicad_wks` that serves A3 and A4, a residue test and an ADR with human review. v0.1 acceptance item 4 asks that one sheet passed with `--drawing-sheet` to an A3 and an A4 board loads on both majors. The batch moved `wks.py` from plan 0009 to this change and gave it the presentation layer (`TitleBlock`, `SheetFrameRef`) and the worksheet half of plan 6.10.
- **Worksheet syntax.** The root is `kicad_wks` (older roots `page_layout` and `drawing_sheet`), with `(version 20231118)` frozen for majors 8, 9 and 10 (S-0032, c0007 `FORMAT_VERSIONS`). The body is one `setup` (`textsize`, `linewidth`, `textlinewidth`, four margins) and items `line`, `rect`, `tbtext`, `polygon` and `bitmap` (S-0035). Points take an optional corner atom `ltcorner`, `lbcorner`, `rtcorner` or `rbcorner` (S-0035); the editor manual says the default corner is the right-bottom one (S-0075, S-0076). Items repeat with `repeat`, `incrx`, `incry` and `incrlabel`, and take `(option page1only)` or `(option notonpage1)` (names S-0036, behaviour S-0075); S-0075 says the label increment has meaning only for a one-letter or one-digit text. S-0035 states a 1 µm minimum unit and that digits beyond three decimals are truncated (`H-K-WKS-RES`). A bitmap is `pngdata` with at most 32 space-separated hex bytes per `data` row (S-0035), and only the PDF and PostScript plotters draw bitmaps (S-0075).
- **Text variables.** The editor manual lists `${KICAD_VERSION}`, `${#}`, `${##}`, `${COMMENT1}` … `${COMMENT9}`, `${COMPANY}`, `${FILENAME}`, `${ISSUE_DATE}`, `${LAYER}`, `${PAPER}`, `${REVISION}`, `${SHEETNAME}`, `${SHEETPATH}` and `${TITLE}` (S-0075). A board's `title_block` holds `title`, `date`, `rev`, `company` and `comment N` (N = 1 … 9), and `paper` takes a size name (`A0` … `A5`, `A` … `E`) or a width and height, with an optional `portrait` (S-0001).
- **Probe observations** (scratch runs on 2026-10-01 with `kicad-cli` 10.0.6 local and 9.0.9 in the pinned image (S-0029); not normative; both majors gave identical texts and page sizes):
  - `pcb export svg <board> -l Edge.Cuts --mode-single [--drawing-sheet <f>]` writes an SVG whose `width` and `height` in mm are the page size, with a viewBox in page mm. Each drawn worksheet text is also a hidden searchable `<text>` holding the resolved string, and lines and rectangles are `<path>` elements (`H-K-WKS-SVG`).
  - KiCad's pages measure A4 297.0022 × 210.0072 mm and A3 419.9890 × 297.0022 mm; `(paper "User" 431.8 279.4)` measures exactly 431.8 × 279.4 mm; `(paper "Tabloid")` fails the board load (`H-K-PCB-PAPER`).
  - `ltcorner` places a point at (margin + x, margin + y); a point without a corner atom at (W − margin − x, H − margin − y) (`H-K-WKS-CORNER`). Repeated copies outside the page are not drawn, and `incrlabel 1` steps `A` to `B` and `1` to `2` (`H-K-WKS-REPEAT`). On 10.0.6, a repeated `tbtext` without `incrlabel` stepped `Q`, `R`, `S` and `5`, `6`, `7`, and `(incrlabel 0)` drew `M`, `M`, `M`: KiCad's default step is 1. `page1only` items are drawn on a board export and `notonpage1` items are not (`H-K-WKS-PAGE1`).
  - Variables resolve from the board's `title_block`; `${PAPER}` gives the paper name as written (`A4`, `User`); `${FILENAME}` gives the board file name; `${#}` and `${##}` give `1`; a `.kicad_pro` `text_variables` member resolves; an undefined `${X}` is drawn literally; `${KICAD_VERSION}` differs per major (`H-K-WKS-VARS`).
  - A broken sheet (unknown head, `bogcorner`, `(option bogus)`, a future version) prints "Error loading drawing sheet", draws the default sheet and exits 0 (`H-K-TOK-WKS-ORACLE`, `H-K-WKS-VALUES`). A missing `--drawing-sheet` file and a `page_layout_descr_file` naming a missing file fall back to the default sheet silently: exit 0 and no message (`H-K-WKS-FALLBACK`). So the message check alone proves nothing.
  - `page_layout_descr_file` holding `s.kicad_wks` or `${KIPRJMOD}/s.kicad_wks` is used without `--drawing-sheet` (`H-K-PRO-WKS`).
  - Lengths with more than 3 decimals and exponent forms load. On 10.0.6, a line start written `50.0006 30.0004` with `ltcorner` and 10 mm margins was drawn at `60.0006 40.0004`: no quantisation to 1 µm was seen.
  - KiCad still resolves the legacy `%` text codes: on 10.0.6, `(tbtext "Title: %T")` and `(tbtext "Rev: %R")` drew the board's title and revision, in a `page_layout` file and in a `kicad_wks` 20231118 file alike (`H-K-WKS-PCT`).
  - A `bitmap` whose `pngdata` holds garbage or a truncated PNG gave the same verdict as a good 1×1 PNG (no message, marker drawn); only the image decoder's own log lines differed (`H-K-WKS-BITMAP`).
- **Corpus.** The demo worksheet `kicad-demo-10-0-6-wks-01` (S-0058, CC-BY-SA-4.0, `embeddable = false`) is a `page_layout` root without a version. 1 149 of its numbers are not whole micrometres and 27 are not whole nanometres; all of them sit in its single `polygon` item, which is opaque anyway. 15 of its texts use `%` codes (observed, not normative). No modelled item of the corpus holds a sub-micrometre length, so an authored fixture proves that rule. Paper on the demo boards (observed census): `A4` 20 times, `A3` twice, `A4 portrait` once, `A5` once and `User 210.007 229.997` once; 17 boards hold a `title_block`.
- **Public standards figures.** The ISO 5457:1999 public preview (S-0077) shows the trimmed sizes A0 to A4, borders of 20 mm on the filing side and 10 mm elsewhere, 0.7 mm frame lines, 50 mm reference fields measured from the centring axes, letters without `I` and `O`, numerals left to right, 3.5 mm characters and 0.35 mm grid lines. The ISO 7200:2004 public preview (S-0078) names the title-block data fields and gives a 180 mm title-block width. Both are copyrighted documents: their values are read as facts, written in Fenolite's words, and no text or figure is reproduced. S-0079 gives A5 and the US sizes (Letter 8.5 × 11 in, Legal 8.5 × 14 in, Tabloid 11 × 17 in). Full copies of the standards found elsewhere are never consulted.
- **Upstream changes.**
  - c0009 (archived): `KicadCli.run(args, *, files, env=None) -> CliRun` with a fresh temporary folder, an empty `KICAD_CONFIG_HOME` and `LANG=C`/`LC_ALL=C`; `pcb.read_board`, `rebuild_board`, `model_source`, `ISSUE_CODES`, `opaque_count`; `paper` and `title_block` are opaque root slots ("Modelled board content"); `CapabilityReport`, `ReadResult` (content `Design | Library`).
  - c0017 (archived, commit `7d973f1`): `pcb.write_board(design, *, target, allow_lossy) -> WriteResult`, `CANONICAL_ORDER`, `FLOOR_HEADS`, `WRITE_ISSUE_CODES`, projection reconciliation (its Decision 10), `versions.LossyWriteError` (`FEN-7001`, `droppable`), the global options `--kicad-version` and `--allow-lossy`, `tests/kicad/_probes.py` (`PROBES`, `run`), `docs/evidence/kicad/probes/<version>.json`, `tests/_boards.py::created_board`. Its living "Created board header" writes `(paper "A4")`, and its "Projected fields on write" makes other projections read-only; this change MODIFIES both and `kicad-slots` "Slot source for model entities" (Decision 22).
  - c0010: `pro.synthesize_project`, `update_project`, `read_project`, `apply_project(design, info, *, issues=None)`, `ProjectInfo`, `pro.template(target)`, `proerrors.ISSUE_CODES`, `triad.write_triad(design, *, name, target=DEFAULT_TARGET, existing_project=None, allow_lossy=False, issues=None)`. Its synthesis keeps `text_variables` and `pcbnew.page_layout_descr_file` at their template values "(filled by c0012)".
  - c0014 (archived): the hypothesis register guard, `fenolite.verify.proposed_ids` (ids in this design's table "Hypotheses registered by this change" pass inside the change folder), "Refuted rows keep their id", and ADR numbering (next free number: 0005).
  - c0007 (archived): `versions.FileKind.WORKSHEET`, `LEGACY_WORKSHEET_ROOTS`, `GENERATOR`, `require_readable`, `check_emittable(node, kind, target_major)` (where `kicad.token.uninventoried` is a warning), the 44 `wks-*` inventory rows and the authored fixtures `tests/data/kicad/tokens/{skeleton,drawing_sheet,page_layout}.kicad_wks`.
  - c0006 (archived): `sexpr.parse`, `dumps(style="kicad")`, `Atom.from_nm`, `Atom.to_nm(exact=True)`, `tree_equal`; `slots.split`, `rebuild`, `to_ext`, `from_ext`, `from_ext_all` with nested relative locators.
  - c0011 owns `fenolite.dsl` and `build`; its `--timestamp` is unused because a build writes no date, and this change generates none either. c0013 copies the drawing sheet named by the project into its check copy set.
- **Environment.** `kicad-cli` 10.0.6 is installed locally; 9.0.9 runs in the pinned image (emulated on arm64, about 2 s per run). The `kicad-10` and `kicad-9` jobs run the oracle tests.
- **Constraints.** Stdlib only (`tomllib`, `decimal`, `base64`, `xml.etree.ElementTree` in tests). `templates` may import only `model` and `core`; `backends.kicad` imports `model`, `geometry` and `backends.base` (`package-layering`). Lengths are integer nm, angles integer µdeg. Budget: 9.5 days (see "Budget").

## Goals / Non-Goals

**Goals:**
- A neutral drawing-sheet definition and the board's paper and title block in the model, with schemas.
- A `.kicad_wks` reader with RT1 and a writer whose single output both majors load.
- Board `paper` and `title_block` read and written from the model; the project keys `pcbnew.page_layout_descr_file` and `text_variables` written and read back.
- A closed `*.sheet.toml` format with per-number provenance, a builder, a layout predictor, two CC0 examples and `fenolite template build`.
- v0.1 acceptance item 4 proved by what KiCad draws, with controls, on 10.0.6 and 9.0.9.
- ADR-0005 written `Proposed` and accepted only by the maintainer.

**Non-Goals:**
- Everything listed under "Non-goals" in the proposal.
- `SheetPolygon` and vector logos: polygons stay opaque items.
- Schematic `page_layout_descr_file`, sheets beyond page 1 of 1.
- A fourth file in `write_triad`: the `.kicad_wks` is written only by `template build`.
- A `src` oracle helper for drawing sheets: the SVG reader and bench live under `tests/kicad/sheets/`.
- Byte identity with sheets that KiCad writes.

## Decisions

1. **Neutral sheet tree in the model.** `templates` builds a `DrawingSheet`, `backends/kicad/wks.py` serialises it, and `cli/cmd_template.py` composes the two. Both packages import `model` only (with `core`), so `package-layering` and `tests/unit/test_import_graph.py` are unchanged. The plan's `templates/kicad_wks.py` role ("generate the tree") becomes `templates/build.py` producing the neutral tree; generation and serialisation stay separate roles.
   - Rejected: a MODIFIED layering table that lets `templates` import `backends.kicad` (it makes templates backend-specific before the v0.4 second backend).
   - Rejected: a KiCad-shaped tree inside `templates` (the same reason).

2. **Drawing sheets are definitions outside `Design`.** `DrawingSheet(name, setup, items)` is an entity with the common header, like `FootprintDef`: prefix `wks`, own schema `drawing_sheet.json`, never in the six `.fenolite/` layer files, because one sheet serves many boards and sizes. Items are immutable value objects in an ordered tuple.
   - Opaque items and unmodelled children live in the sheet's `ext["kicad"]` slots under nested relative locators (`tbtext[3]/font[0]`), which `slots.to_ext` already supports.
   - `Board.sheet: SheetFrameRef | None` and `Board.title_block: TitleBlock | None` default to `None`, so earlier `board.json` documents load unchanged. They enter through the MODIFIED `design-model` requirement "Model layers for v0.1".
   - Rejected: items as entities (ids nobody references).
   - Rejected: the sheet inside `Board` (it would be duplicated per board and per size).

3. **Item set.** `SheetShape` (`kind` `line` or `rect`), `SheetText` and `SheetBitmap` are modelled; the bitmap is the plan's optional logo. `polygon` items and unknown heads are opaque items, re-emitted verbatim at their positions.
   - `SheetShape.kind` is required and has no default, as `Graphic.kind`. `canonical.loads` returns the first union member that decodes, and the canonical form leaves out defaults, so two classes with the same fields, or a defaulted kind, would read a rectangle back as a line. `SheetText` and `SheetBitmap` differ by their required fields.
   - Bitmaps are verified for loading only, because the SVG plotter does not plot them (S-0075); `layout` counts them and draws nothing. A load verdict cannot tell a good bitmap from a corrupt one, so `wks-bitmap-corrupt` must show a decoder log line that `wks-bitmap` lacks (`wks-bitmap-clean`, Decision 17); otherwise bitmap loading stays `INFERRED`.
   - Bitmap support is the first budget cut: the model type stays, the reader and writer keep it, and `load_spec` refuses `[bitmap]` with `template.unknown-key` until a follow-up.
   - Rejected: modelling `SheetPolygon` now (the roadmap lists it, but no example needs it).
   - Rejected: separate `SheetLine` and `SheetRect` classes with the same fields (ambiguous canonical form).

4. **Corner semantics and item syntax.** A `SheetPoint(corner, x, y)` is an offset from the named corner of the margin box (the page minus the `setup` margins), positive toward the interior (S-0035, S-0075; `H-K-WKS-CORNER`).
   - A point without a corner atom is `rb`. The writer omits the `rbcorner` atom, as c0007's authored skeleton does.
   - Scopes `first_only` and `not_first` are written `(option page1only)` and `(option notonpage1)` (S-0036; `H-K-WKS-PAGE1`).
   - `SheetRepeat(count, step_x, step_y, label_step)` maps to `repeat`, `incrx`, `incry` and `incrlabel`. The model defaults are KiCad's file defaults: 1, 0, 0 and 1, because KiCad steps labels by 1 when `incrlabel` is absent (observed; `H-K-WKS-REPEAT`). Each is written only when it differs from that default, and an absent child reads as the default.
   - Text rotation is µdeg in the model and degrees in the file. A bitmap's scale is integer parts per million in the model and a decimal in the file.
   - A bitmap is written as `pngdata` with at most 32 space-separated hex bytes per `data` row (S-0035; `H-K-WKS-BITMAP`).
   - `wks.CANONICAL_ORDER` gives the child order per head from the order of the S-0035 syntax descriptions; the order is recorded in `worksheet.md`. Load on both majors is the proof (Decision 18); byte identity with KiCad-written sheets is not claimed.
   - Rejected: absolute page coordinates (one file could not serve A3 and A4).

5. **Neutral tokens in the model, KiCad map in the backend.** `SHEET_TOKENS` has 11 names, plus `{param:NAME}` for user parameters and `{{`/`}}` for literal braces. It stays backend-free for the v0.4 backend. `split_tokens(text)` is the only parser, and every text a builder or reader produces passes it.
   - `wks.KICAD_TOKENS` is the plan's table: `{title}` → `${TITLE}`, `{doc_id}` → `${COMMENT1}`, `{revision}` → `${REVISION}`, `{sheet}` → `${#}`, `{sheets}` → `${##}`, `{date}` → `${ISSUE_DATE}`, `{organization}` → `${COMPANY}`, `{responsible}` → `${COMMENT2}`, `{approver}` → `${COMMENT3}`, `{filename}` → `${FILENAME}`, `{paper}` → `${PAPER}`, `{param:X}` → `${X}`.
   - `wks.RESERVED_VARIABLES` is the S-0075 list plus `KIPRJMOD` (S-0045).
   - The reader inverts the map. KiCad-only variables (`${SHEETNAME}`, `${SHEETPATH}`, `${LAYER}`, `${KICAD_VERSION}`, `${KIPRJMOD}`, `${COMMENT4}` … `${COMMENT9}`), a malformed `${` and a `%` followed by an ASCII letter keep the item opaque; any other `${X}` reads as `{param:X}`; literal braces read as `{{` and `}}`.
   - KiCad still resolves the legacy `%` codes (`%T` draws the title) in current files (observed; `H-K-WKS-PCT`). Mapping them to tokens would need the full code list, which no registered source gives, so the reader keeps such texts opaque; the demo worksheet's 15 such texts are re-emitted verbatim.
   - The writer refuses `{param:X}` with X reserved (`kicad.wks.param-reserved`), and a `${` or a `%` followed by an ASCII letter in the KiCad form that no token produced (`kicad.wks.literal-variable`), both `LossyWriteError` with `droppable=False`. No escape for `%` is proven, so a literal `%T` cannot be written. So reading and writing are inverse.
   - Rejected: KiCad `${…}` text in the model.
   - Rejected: allowing `{param:TITLE}` (it would read back as `{title}`).

6. **Exact numbers and the 1 µm resolution.** Template files are read with `tomllib.loads(text, parse_float=Decimal)` and converted to nm exactly; no float is created.
   - S-0035 states a 1 µm minimum unit and truncation beyond three decimals (`H-K-WKS-RES`), but 10.0.6 drew a sub-micrometre length unchanged (Context). The two rules below are therefore Fenolite choices, not KiCad facts: whole micrometres are what S-0035 promises, and Fenolite needs nothing finer.
   - A template length that is not a whole micrometre is `template.resolution` at load. The writer refuses a modelled length that is not a multiple of 1 000 nm (`kicad.wks.below-resolution`, `LossyWriteError`, `droppable=False`).
   - The reader keeps an item opaque, with the info `kicad.wks.kept-opaque`, when one of its lengths is not a whole micrometre, an angle is not a whole µdeg or a scale is not a whole part per million. KiCad loads such items. In the demo worksheet every such number sits in the opaque `polygon`, so the authored fixture `tests/data/kicad/sheets/sub_um.kicad_wks` (a `line` starting at 50.0006 mm) proves the rule. This closes the gap listed in the project plan's code report. Unchanged opaque items are re-emitted verbatim.
   - The refusal is safe whichever way `H-K-WKS-RES` settles: Fenolite never needs a finer length, and a `-2` successor would only widen what the reader models.
   - Rejected: rounding to the nearest micrometre (a silent change of the user's numbers).

7. **Reader and RT1.** `read_drawing_sheet(source, *, file="", name=None, issues=None)` accepts a path, text or a parsed `Node`, checks the version as `read_board` does (`info = versions.inspect(root, file=file)`, then `versions.require_readable(info, file=file)`, with `versions.version_issues(info)` added to `issues`), and reads the roots `kicad_wks`, `page_layout` and `drawing_sheet` (a legacy root adds the info `kicad.wks.legacy-root`).
   - Each modelled child is re-emitted with the writer's emitter and compared with the original, as boards do in "Modelled children are reproducible". A child that is not reproduced tree-equal (for example an explicit `rbcorner` or `(pos 10.000 10)`) becomes an opaque slot; its value stays projected and the info `kicad.wks.kept-opaque` names the reason.
   - `rebuild_drawing_sheet(sheet)` keeps the source root and header, emits modelled items and children from the model and opaque items and slots verbatim. RT1 is `tree_equal(rebuild_drawing_sheet(read_drawing_sheet(t)), parse(t))` for every authored fixture and the demo worksheet; `opaque_count` counts opaque items and slots.
   - On write, a kept slot whose projection still equals the model is re-emitted verbatim; one whose value changed is re-emitted from the model (c0017's projection reconciliation).
   - The reader is a library function for RT1, the oracle and the demo check. There is no import command (v0.2a), and third-party worksheets stay `INFERRED` (one corpus origin).
   - Rejected: normalising non-canonical children (RT1 would fail on hand-written sheets).

8. **Writer header and emit check.** `write_drawing_sheet` takes the rebuilt tree and always writes root `kicad_wks`, `(version 20231118)` and `(generator "fenolite")` (S-0032), re-rooting a legacy root. For a read sheet it first calls `versions.require_editable(versions.inspect(<source root>))`, as c0017 does for boards: a sheet read from a `FUTURE` file raises `FutureFormatError` (`FEN-3002`), because re-heading it to 20231118 would be a silent downgrade of a read-only file. It writes no `generator_version`: c0007's authored skeleton loads on both majors without it, so one output serves both majors byte for byte, and `--kicad-version` selects only the emit-check target.
   - Children follow `wks.CANONICAL_ORDER`; the text is printed with `dumps(style="kicad")`.
   - `check_emittable(root, FileKind.WORKSHEET, target)` runs on the final tree. Each `kicad.token.uninventoried` warning becomes the error `kicad.wks.uninventoried`. Each value atom outside `wks.VALUE_ATOMS` (corners, options, justify values, font flags) becomes `kicad.wks.unknown-value`, because KiCad rejects such values (observed for `bogcorner` and `(option bogus)`; `H-K-WKS-VALUES`) and `check_emittable` checks heads only.
   - Both raise `LossyWriteError` (`FEN-7001`, `droppable=True`) with a hint naming `--allow-lossy`. With `allow_lossy=True`, the opaque item that holds them is dropped with the warning `kicad.wks.dropped-item`. Modelled items produce only inventoried names and listed values (unit test over every modelled kind).
   - `kicad-version-gating` is unchanged, as c0018 does for rules: the writer uses its existing `inspect`, `require_editable` and `check_emittable`.
   - The closed issue table:

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

   - Rejected: `generator_version "<target>.0"` (two files for one sheet, no gain).
   - Rejected: trusting `check_emittable` alone (it lets bad value atoms through).

9. **Board `paper` and `title_block` become projections.** Both heads stay opaque root slots, so c0009's closed list of "Modelled board content", every corpus `opaque_count` and RT1 are unchanged. Their content is projected into `Board.sheet` and `Board.title_block` by `project_paper(node, *, issues=None)` and `project_title_block(node)`; `read_board` passes its own `issues` list.
   - Read: `(paper "A0")` … `(paper "A5")` with optional `portrait` project to the named size. `(paper "User" W H)` projects to `Letter`, `Legal` or `Tabloid` when W × H equals that size of `PAPER_SIZES` in either orientation (portrait when W < H), and otherwise to `custom` W × H. Any other name (`USLetter`, `A` … `E`, …) and a size that is not a whole nm keep `Board.sheet = None` with the info `kicad.board.paper-unmodelled`.
   - `title_block` children `title`, `date`, `rev`, `company` and `comment 1` … `comment 3` project through `pcb.TITLE_BLOCK_FIELDS`; `comment 4` … `comment 9` and unknown children stay in the fragment.
   - Write, created board: `paper` from `Board.sheet` (`(paper "A4")` for `None`, as today), and `title_block` right after `paper` when one of the seven fields is non-empty. This widens the head set of the living "Created board header" (that of the skeleton board, which has no `title_block`) through a MODIFIED delta. `pcb.CREATED_ROOT_HEADS` stays the head set of a created board without a title block; `pcb.CANONICAL_ORDER["kicad_pcb"]` inserts `title_block` right after `paper`, and `CANONICAL_ORDER["title_block"]` is `("title", "date", "rev", "company", "comment")`. Letter, Legal, Tabloid and custom are written `(paper "User" W H)`: the width-and-height form of S-0001, spelled `User` as KiCad-written demo boards spell it (S-0058; `H-K-PCB-PAPER`). KiCad's own US names are never written, because no registered public source names them, and `Tabloid` fails the board load (observed).
   - Write, read board: an unchanged value keeps its fragment; a changed `paper` is re-emitted whole; a changed `title_block` is rewritten in place (mapped children replaced, inserted in the order `title`, `date`, `rev`, `company`, `comment 1` … `comment 3`, or removed when emptied; every other child tree-equal at its position; a board read without `title_block` gains one right after `paper`). The MODIFIED "Projected fields on write" makes both projections editable, and the MODIFIED `kicad-slots` "Slot source for model entities" lists them as two more exceptions to the tree-equal re-emission of opaque fragments.
   - `pcb.FLOOR_HEADS` gains `title_block`, `title`, `date`, `rev`, `company` and `comment` (S-0001; S-0033 at tag 8.0.0, as c0017 records its floor names), and `created_board()` gains `SheetFrameRef("A4")` and a seven-field `TitleBlock`, so c0017's `created_tokens` test and its `pcb-write-heads-*` probes cover the new heads. c0017's empty-design head-set scenarios are unaffected (no title block).
   - `ISSUE_CODES` gains the info `kicad.board.paper-unmodelled` through the MODIFIED requirement "Board read issue codes".
   - Rejected: modelled root fields (they change c0009's closed list and every corpus opaque count).
   - Rejected: read-only projections (no edit path for agents); kept as budget cut 2.

10. **Project keys are a post-step of `write_triad`.** `pro.apply_sheet_keys(project_text, design, *, allow_lossy=False, issues=None)` runs inside `write_triad` after `synthesize_project` or `update_project`.
    - It sets `pcbnew.page_layout_descr_file` (`pro.PAGE_LAYOUT_POINTER`) to `Board.sheet.drawing_sheet` verbatim when that is not `None`, and otherwise keeps the existing value. `model.sheet-path` refuses absolute paths and `..` before any write. `schematic.page_layout_descr_file` is untouched.
    - It adds or replaces one `text_variables` member per `TitleBlock.params` key, appends new members sorted by name, and deletes none. `pro.SHEET_KEY_PATHS` (`/text_variables/*`) are the only paths it may add.
    - A reserved name gives `kicad.project.reserved-variable` (`LossyWriteError`, `droppable=True`); with `allow_lossy` the variable is left out with `kicad.project.dropped-variable`.
    - When the design sets neither key, the text comes back unchanged, so every c0010 scenario holds byte for byte.
    - `read_project` fills `ProjectInfo.drawing_sheet` and `ProjectInfo.text_variables`; a `text_variables` member whose value is not a string gives the new info `kicad.project.unread-variable`, so c0010's `kicad.project.unread-entry` (a pattern or assignment entry) keeps its meaning. `apply_project` copies them into `Board.sheet.drawing_sheet` (when `Board.sheet` exists) and `TitleBlock.params`.
    - A triad written without `existing_project` reads back equal in normal form (`H-K-PRO-WKS`): a `None` sheet reads back as `SheetFrameRef("A4")`, because a created board writes `(paper "A4")`, and a `TitleBlock` with seven empty fields and no parameter reads back as `None`, because no `title_block` is written for it.
    - Rejected: changing `synthesize_project` or `update_project` (it contradicts c0010's requirement text and its byte-level scenarios).
    - Rejected: writing the `.kicad_wks` inside the triad (c0010 fixes three files).

11. **Template format.** `*.sheet.toml` has the closed key set of the requirement "Sheet specification files": `[provenance]`, `[sheet]`, `[margins]`, `[frame]`, the optional `[bitmap]` and `[title_block]` with `[[title_block.cell]]`. Lengths are millimetres; there are no expressions and no includes. `docs/sheet-templates.md` is the reference for users and agents.
    - Every problem is collected in file order and raised as one `TemplateError(FormatError)`: `locator` is the TOML key path of the first problem, `issues` holds one `Issue` per problem, and the dispatcher maps it to `FEN-3004` (exit 3). A TOML syntax error is raised at once as `template.bad-value` with the parser's line and column. No new FEN code.
    - The closed code table:

      | code | severity | when |
      |---|---|---|
      | `template.unknown-key` | error | a key or table outside the closed set |
      | `template.bad-value` | error | a wrong type or value, or a TOML syntax error |
      | `template.resolution` | error | a length that is not a whole micrometre |
      | `template.unknown-token` | error | a cell `token` or a `label` that `split_tokens` refuses |
      | `template.unproven-value` | error | a number missing from `[provenance.values]` when provenance is required |
      | `template.cell-overlap` | error | two cells covering one grid position |
      | `template.cell-outside` | error | a cell leaving the grid |
      | `template.zone-letters` | error | more than 8 letter rows on a listed size |
      | `template.bitmap-not-png` | error | a `[bitmap]` file without the PNG signature |
      | `template.too-wide` | warning | a grid wider or taller than the margin box of a listed size |

    - Rejected: exit 5 for specification problems (they are malformed input, not findings about a design).
    - Rejected: expressions or includes (the format would grow into a second DSL).

12. **One file serves several sizes.** Frame, margins, zone band and title block are corner-anchored, so one sheet serves every listed size (acceptance item 4).
    - The frame is one `SheetShape` of kind `rect` from `lt(0, 0)` to `rb(0, 0)`. With zones, an inner rectangle is inset by `zone_band`. Number ticks and labels run along x from the `lt` and `lb` corners, letter ticks and labels along y from the `lt` and `rt` corners, at `zone_pitch` (50 mm in the ISO example, S-0077). Label k is centred at `k × pitch + pitch / 2` from its corner along the band.
    - Repeat counts cover the largest listed size; KiCad does not draw copies whose start point leaves the margin box (`H-K-WKS-REPEAT`), so each size shows its own field count (A4 landscape with 20/10 mm margins: `1` … `5` and `A` … `D`; A3: `1` … `8` and `A` … `F`).
    - Labels use `incrlabel`, which does not skip letters, so `load_spec` refuses with `template.zone-letters` a zoned specification whose largest listed size needs more than 8 letter rows. Sizes up to A3 in either orientation and A2 landscape pass with 10 mm margins and a 50 mm pitch.
    - ISO 5457 measures fields from the centring axes, which no corner can express for two sizes. The zone origin at the frame corners is a Fenolite choice, and centring marks are left out. `[provenance]`, `docs/sheet-templates.md` and the ADR say so.
    - Rejected: one file per size (contradicts item 4 and an agent's single `--drawing-sheet`).
    - Rejected: ISO zones exact for one declared size only (misplaced on the other size).

13. **Provenance per number.** `load_spec(…, require_provenance=True)`, used for the shipped examples, requires every numeric key path (except the grid indices `row`, `col` and `span`) in `[provenance.values]`, mapped to `fenolite-choice` or an S-id listed in `[provenance] sources`; otherwise `template.unproven-value`. User specifications need no provenance.
    - `tests/residue/test_template_residue.py` checks, as an allowlist, that every `[provenance.values]` entry of a shipped example is `fenolite-choice` or one of S-0077, S-0078 and S-0079 and is registered, so a value mapped to S-0058 (KiCad's demo files, including the demo worksheet), S-0066, S-0075 or S-0076 fails. It also checks that every text is a neutral token, a label listed in `docs/formats/sheets.md` or a one-character zone label, and that the residue scan of the written `.kicad_wks` is clean.
    - Rejected: a denylist of S-0066 only (it lets a value through that came from KiCad's own files).
    - No test of this change reads a kicad-templates sheet or KiCad's default sheet, so the examples cannot be derived from them.
    - Rejected: one provenance line per file (it cannot show which number came from where).

14. **Clean room, naming gate and human review.** Example geometry comes only from S-0077, S-0078 and S-0079, recorded in `docs/formats/sheets.md` in Fenolite's words, or is a Fenolite choice. The planned values of `iso5457_generic` (final values in task 9.1):

    | key path | value | provenance |
    |---|---|---|
    | `sheet.sizes`, `sheet.orientation` | `A4`, `A3`; landscape | not numbers (no provenance entry); sizes from S-0077, chosen by acceptance item 4 |
    | `margins.left` / other margins | 20 mm / 10 mm | S-0077 |
    | `frame.line_width` | 0.7 mm | S-0077 |
    | `frame.zone_pitch`, `frame.zone_text_size`, `frame.zone_line_width` | 50 mm, 3.5 mm, 0.35 mm | S-0077 |
    | `frame.zone_band` | 5 mm | `fenolite-choice` |
    | `title_block.columns` (sum) | 180 mm | S-0078 |
    | `title_block.corner` | `rb` | not a number (no provenance entry); title-block position from S-0077 |
    | row heights, column split, `label_size`, cell `font_size`, `title_block.line_width`, `sheet.text_size`, `sheet.line_width`, `sheet.text_line_width` | to be set in task 9.1 | `fenolite-choice` unless `sheets.md` records a figure |

    - `letter_generic` lists Letter and Tabloid landscape, no zones, 12.7 mm margins and title-block geometry labelled `fenolite-choice`; its labels are the same ISO 7200 field names.
    - Naming gate (task 1.3): the example is `iso5457_generic` only if the S-0077 values above are visible on the preview as registered. Otherwise it ships as `a_series_generic`, every value is `fenolite-choice`, and `EXAMPLES` names it. S-0078 is gated separately: if its field names or the 180 mm width are not visible as registered, the width becomes `fenolite-choice` and the labels become Fenolite-choice labels, listed as such in `docs/formats/sheets.md` and accepted by the residue test. Either way no conformance is claimed.
    - ADR-0005 is written with Status `Proposed`. Only the maintainer sets `Accepted (<date>)`, after reviewing the ADR, both examples and their provenance tables, in their own commit with a `LEGAL-ANNEX.md` row. The change is archived only after that commit.
    - Rejected: an agent-written "reviewed" line.
    - Rejected: reading the kicad-templates sheets (S-0066) or KiCad's default sheet "for measurement" (any likeness would then be unprovable).

15. **Layout predictor.** `templates.layout(sheet, *, width, height, page=1)` maps corners inside the margins, applies repeats with margin-box clipping and the label step, and keeps items by page scope on page 1 of 1. `resolve_text(text, block, *, paper, filename, sheet=1, sheets=1)` gives the string KiCad shows on a board: title-block fields, the paper name as written, the board file name, `1` for sheet and sheets, `block.params` for parameters (an absent parameter stays `{param:NAME}`, as KiCad draws an undefined variable literally).
    - It imports only `model` and `core`, and feeds `template build` (`result.drawn`) and the oracle.
    - The caller passes the page size. The oracle uses the size read from KiCad's SVG (A4 measures 297.0022 × 210.0072 mm), so no KiCad size table is copied; `template build` uses `PAPER_SIZES`.
    - It depends on `H-K-WKS-CORNER`, `H-K-WKS-REPEAT` and `H-K-WKS-PAGE1`. If a probe measures otherwise, `layout` follows the measurement on both majors and a `-2` successor row records it (c0014 "Refuted rows keep their id").

16. **Probe spike before model code.** Task group 2 runs every probe of the table below before any model code is written; only the `wks-accept-*` cases wait for group 11, and task 6.3 re-runs `pcb-paper-*` and `wks-tokens` on boards written by `write_board`. The probes compare KiCad with these rules:

    | probes | rules checked |
    |---|---|
    | `wks-svg-shape`, `wks-default`, `wks-control` | the SVG reader and the controls (Decision 17) |
    | `wks-broken`, `wks-missing-file`, `wks-pro-missing` | the verdict classes (Decision 17) |
    | `wks-corners`, `wks-repeat`, `wks-page1only`, `wks-notonpage1` | corners, repeat with and without `incrlabel`, and scope (Decisions 4 and 15) |
    | `wks-tokens`, `wks-undefined-var`, `wks-percent` | the token map, `resolve_text` and the `%` codes (Decisions 5 and 15) |
    | `wks-value-<atom>`, `wks-value-unknown` | `VALUE_ATOMS` (Decision 8) |
    | `wks-bitmap`, `wks-bitmap-corrupt`, `wks-bitmap-clean`, `wks-resolution` | `pngdata` rows, the corrupt-bitmap control and the resolution (Decisions 3, 4 and 6) |
    | `pcb-paper-<name>` | paper forms (Decision 9) |
    | `wks-pro-relative`, `wks-pro-kiprjmod` | the project key (Decision 10) |

    - Before `layout` exists, each semantic probe compares the SVG with literal expectations in `tests/kicad/sheets/_expected.py`, computed by hand from the fixture numbers and the rules above. Task 8.3 adds a hermetic test that `layout` reproduces every entry of `_expected.py`, and then the probes use `layout`.
    - Probe boards are built by `_sheet_bench.board_text(paper=…, title_block=…)`, which replaces the `paper` child of c0007's skeleton board in the parsed tree and, when `title_block` is given, inserts it right after `paper` (KiCad's order, recorded in `board.md`); the skeleton has no `title_block`. Probe projects come from c0010's `pro.template(target)` with the keys set in the test. Task 6.3 switches `pcb-paper-*` and `wks-tokens` to boards written by `write_board` from `Board.sheet` and `Board.title_block`, with the same expected outcomes.
    - Probe sheets are authored CC0 fixtures `tests/data/kicad/sheets/probe_*.kicad_wks` (`origin = "authored"`), each with a one-word marker text. Exceptions: `wks-default`, `wks-missing-file`, `wks-pro-missing` and `pcb-paper-*` use no sheet file, `wks-control` uses c0007's `skeleton.kicad_wks`, and `wks-accept-*` use the sheets that `template build` writes.
    - Gate: an outcome that contradicts a rule stops the change until this design is amended and a `-2` successor row is added. The probes are never overridden.
    - About 47 probe runs per major: 13 value atoms, 11 paper forms (A0 to A5, A4 portrait, Letter, Legal, Tabloid, one custom size), the 4 acceptance cases of group 11 and 19 others. `wks-bitmap-clean` adds no run: it reads the memoised outputs of three of them.

17. **Oracle verdict from the drawn content.** Probes live in c0017's registry. Each runs `pcb export svg <board> -l Edge.Cuts --mode-single [--drawing-sheet <f>]` through `KicadCli.run`, with the board, sheet and project in `files`.
    - `tests/kicad/sheets/_svg.py` reads, with `xml.etree.ElementTree`, the page size, every hidden searchable `<text>` with its string and anchor, and the straight segments of every `<path>` (`M`, `L`, `H`, `V`, `Z`, absolute and relative) (`H-K-WKS-SVG`).
    - Classes: `reject` when the output holds "Error loading drawing sheet". Otherwise, against the default-sheet control of the same board in the same session: `absent` when the drawn texts equal it (silent fallback); `load` when they differ and the case's marker, if any, is drawn; `different` when they differ but the marker is missing (another sheet was drawn). Semantic cases are `equal` when every text matches within 0.01 mm in x and half the text height in y and every line end within 0.01 mm, else `different`.
    - Every session runs the default control (`wks-default`) and the positive control `tests/data/kicad/tokens/skeleton.kicad_wks` (`wks-control`). When the positive control is not `load`, or the default control draws no text, every sheet case of the session is `inconclusive`.
    - Bitmaps: `wks-bitmap-corrupt` (garbage `pngdata`) is `present` when its output holds a line that `wks-control` lacks (the decoder line; a scratch run on 10.0.6 showed one). `wks-bitmap` is classified like any sheet case and must be `load`. `wks-bitmap-clean` reads the memoised outputs of the same session and is `absent` when none of those lines appears in the output of `wks-bitmap`, `present` otherwise, so each probe id has one outcome from c0017's closed set. If the corrupt control shows no such line, or `wks-bitmap-clean` is not `absent`, on a major, bitmap loading stays `INFERRED` there.
    - The exit code is never read.
    - Rejected: PDF output (it needs a parser).
    - Rejected: a `src` oracle helper (no v0.1 product consumer; c0013 or c0024 may move it).
    - Rejected: a verdict from the message alone (silent fallback).
    - Rejected: committing KiCad's default-sheet strings as a negative marker (GPL program output; the same-session control needs none).

18. **Acceptance (v0.1 item 4).** For each example, each listed size and each major, with the same `.kicad_wks` bytes on both majors (produced by `fenolite template build`) and boards written by `write_board` (target 10 on 10.0.6, target 9 on 9.0.9) with that size and a seven-field `TitleBlock`:
    - the message is absent;
    - the drawn hidden-text multiset equals `layout` plus `resolve_text` for that title block, the paper name as written and the board file name;
    - it differs from the default control of the same board in the same session;
    - every predicted line is found among the SVG path segments within 0.01 mm.
    - Controls in the same run: the generated sheet with `(frobnicate 1)` inserted is `reject`; a missing `--drawing-sheet` file and a project naming a missing sheet are `absent`; the skeleton is `load`. A control with another outcome fails the test.
    - `test_project_sheet.py` writes a triad whose board names `frame.kicad_wks` and holds a `TitleBlock` and one parameter, and finds the predicted texts without `--drawing-sheet` (`H-K-PRO-WKS`).

19. **`template build`.** `fenolite template build SPEC --target kicad --out OUT` (`cli/cmd_template.py`, `mutates=True`, schema `fenolite.template.v0`) loads, builds and writes through the dispatcher's mutation protocol: plan, `FEN-4001` (exit 4) without `--confirm`, receipt with SHA-256, `.bak`.
    - Registration: `main.build_parser` adds the global options, `--dry-run` and `--confirm` to the command's own parser before `register`. So `register` adds `build` as a positional argument with the single choice `build`, then `SPEC`, `--target` and `--out` (short form `-o`), on that same parser. `--out` is spelled as c0011's `build --out DIR`, so an agent that learns one command does not mistype the other. A nested sub-parser would reject every global or mutation flag placed after `build SPEC …` (exit 2, `FEN-2001`; checked with a scratch argparse copy of the layout).
    - `--target` names the backend; anything other than `kicad` exits 2. The global `--kicad-version` picks the emit-check target, and `--allow-lossy` is passed to the writer.
    - Exit codes: 0 ok, 2 usage, 3 (`FEN-3004` for a malformed specification; `FEN-3001` for a missing or unreadable file), 4 confirmation required, 7 (`FEN-7001`). No new FEN code. On a raised `TemplateError` the stderr error object's message names every code and key path, and its `where` is `<file>:<locator>` of the first problem. The `template.*` issues, each naming its key path, also reach the envelope's `issues` through c0011's `cli-contract` requirement "Refusals carry their issues" (c0011 archives first), as do the issues of the writer's `LossyWriteError`. No `cli-contract` delta is needed.
    - `result` holds `sheet` (`name`, `sizes`, `items`, `tokens`), `target`, `kicad_version`, `drawn` (per listed size: text and line counts and the texts resolved with an empty `TitleBlock`, on the `PAPER_SIZES` page in the specified orientation, or on `sheet.width` × `sheet.height` for `custom`) and `output`. The dispatcher adds `plan` to a `--dry-run` or unconfirmed run; a confirmed run carries the `receipt` instead.
    - It runs no `kicad-cli`, so its envelope evidence is `INFERRED` with `H-K-WKS-CORNER`.
    - `example_args` and `mutation_example_args` resolve `example_path("iso5457_generic")`, so the consistency test stays hermetic. `example_args` end with `--dry-run`, because `test_json_envelope` expects exit 0; `mutation_example_args` hold neither `--dry-run` nor `--confirm`, because `test_mutation_protocol` appends them.
    - Rejected: `--verify` running the SVG verdict (follow-up; the probes prove the constructs).

20. **Determinism and ids.** `build_sheet` uses no random generator, clock or environment value, and generates no date. The same specification gives equal canonical JSON and a byte-identical `.kicad_wks`.
    - `DrawingSheet.id = derived_id("wks", "template", spec.name)`; a read sheet has `derived_id("wks", "kicad", name)`, with the name defaulting to the file stem. Items, `TitleBlock` and `SheetFrameRef` carry no ids.
    - Both are the living "imported objects with a native id" case of "Identifier derivation", which this change does not modify: a sheet comes from a file (a `*.sheet.toml` or a `.kicad_wks`), `template` and `kicad` name the source format, and the declared `sheet.name` or the file name is the native id, as library names are for c0008's definitions. c0017 and c0011 MODIFY "Identifier derivation" because placed copies and DSL objects have no native id in a source file; a sheet does. Not modifying it also keeps this change free of c0011's MODIFIED text.
    - Rejected: a fifth case in a MODIFIED "Identifier derivation" (it would copy c0011's full text and tie this change to c0011's archive order for no behavioural gain).
    - A built sheet written and read back has equal `setup` and `items`.

21. **Capability report.** `write_kinds` gains `kicad_wks`; `read_kinds` is unchanged, because `Backend.read` returns a `Design` or a `Library` and a `DrawingSheet` is neither (c0010's reasoning for `.kicad_pro`). `KicadBackend.write_sheet(sheet, *, target=None, allow_lossy=False)` is a method like `write` and `lower`; the `Backend` protocol and the operation literal are unchanged. The pinned capability tests pass unchanged, because they check `write_kinds` by membership.

22. **Spec deltas against living and unarchived requirements.**
    - `design-model` "Model layers for v0.1" is MODIFIED with the living text copied in full; no other change of the batch or of c0011 and c0013 modifies it.
    - `kicad-file-backend` "Board read issue codes" is MODIFIED with the living text copied in full (c0009 is archived), adding one row and one scenario; no unarchived change modifies it.
    - c0017 was archived on 2026-10-01 (commit `7d973f1`), so three of its requirements are MODIFIED with the living text copied in full: `kicad-file-backend` "Created board header" (the `paper` line from `Board.sheet`, `title_block` after `paper` when a field is set, `CREATED_ROOT_HEADS` unchanged otherwise) and "Projected fields on write" (`paper` and `title_block` are editable projections), and `kicad-slots` "Slot source for model entities" (two more exceptions). No unarchived change (c0010, c0018, c0011, c0013) modifies them; c0011 only cites "Projected fields on write" for `Component.properties`, which this delta leaves unchanged. The ADDED "Paper and title block on boards" keeps only the new rules (projections, `paper_node`, `title_block_node`, the in-place rewrite).
    - "Projects carry the drawing sheet and text variables" stays ADDED, because c0010 is not archived. It names the c0010 requirements it takes precedence over: "Project files are synthesised and preserved", "Generated projects are coherent", "Project files are read into the model" and "Project issue codes".
    - Task 1.4 re-checks the bases. If c0010 is archived by then, those four become MODIFIED deltas with the living text copied in full (Open Questions).

23. **Hand-overs.** This change writes only the project key; the user runs `template build --out <project folder>/<name>.kicad_wks`. c0011's DSL gains no sheet keywords here; v0.1 sets `Board.sheet` and `Board.title_block` through the model API. c0013's copy set already copies the sheet named by `page_layout_descr_file`. c0019 merges `.kicad_pro` through `update_project`, and `apply_sheet_keys` runs after it. c0024 exports with the sheet.
    - Answer to c0011's Open Question on `BOARD_ORIGIN`: `Board.sheet` never moves footprints or the outline, and `BOARD_ORIGIN = (100 mm, 100 mm)` stays fixed, because c0019's layout preservation relies on it. A board larger than its page is the user's choice of paper.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/model/presentation.py` (new) | `Corner = Literal["lt", "lb", "rt", "rb"]`; `PageScope = Literal["all", "first_only", "not_first"]`; `HJustify`, `VJustify`; `SheetPoint(corner: Corner = "rb", x: Nm = 0, y: Nm = 0)`; `SheetRepeat(count: int = 1, step_x: Nm = 0, step_y: Nm = 0, label_step: int = 1)`; `SheetSetup(text_size: tuple[Nm, Nm], line_width: Nm, text_line_width: Nm, left_margin: Nm, right_margin: Nm, top_margin: Nm, bottom_margin: Nm)`; `ShapeKind = Literal["line", "rect"]`; `SheetShape(kind: ShapeKind, start: SheetPoint, end: SheetPoint, width: Nm \| None = None, repeat: SheetRepeat = SheetRepeat(), scope: PageScope = "all", name: str = "", comment: str = "")` (`kind` required, no default); `SheetText(text: str, pos: SheetPoint, size: tuple[Nm, Nm] \| None = None, bold: bool = False, italic: bool = False, justify: HJustify = "left", vjustify: VJustify = "center", rotation: Udeg = 0, max_len: Nm \| None = None, max_height: Nm \| None = None, repeat, scope, name, comment)`; `SheetBitmap(pos: SheetPoint, png: str, scale_ppm: int = 1_000_000, repeat, scope, name, comment)`; `SheetItem = SheetShape \| SheetText \| SheetBitmap`; `DrawingSheet(Entity)(name: str, setup: SheetSetup, items: tuple[SheetItem, ...])` (`items` ordered); `SHEET_TOKENS: frozenset[str]`; `SheetToken(name: str, param: bool = False)`; `split_tokens(text: str) -> tuple[str \| SheetToken, ...]`; `PaperSize`; `PAPER_SIZES: Mapping[str, tuple[Nm, Nm]]`; `TitleBlock(title="", date="", revision="", organization="", doc_id="", responsible="", approver="", params: dict[str, str] = field(default_factory=dict))` (as `Entity.native_ids`; the canonical loader and `tools/gen_schemas.py` support `dict`, not `Mapping`); `SheetFrameRef(paper: PaperSize = "A4", portrait: bool = False, width: Nm \| None = None, height: Nm \| None = None, drawing_sheet: str \| None = None)` |
| `src/fenolite/model/board.py`, `design.py`, `__init__.py` | `Board.sheet: SheetFrameRef \| None = None`; `Board.title_block: TitleBlock \| None = None`; `Design.validate()` gains `model.sheet-path`, `model.sheet-size`, `model.param-name`; re-exports of the presentation names |
| `src/fenolite/core/ids.py` | `PREFIXES` gains `wks` |
| `src/fenolite/model/schema.py`, `tools/gen_schemas.py` | target `drawing_sheet.json` (`fenolite.drawing_sheet.v0`); `board.json` regenerated |
| `schemas/fenolite.model.v0/drawing_sheet.json` (new), `board.json` | generated |
| `src/fenolite/backends/kicad/wks.py` (new) | `read_drawing_sheet(source: str \| os.PathLike[str] \| Node, *, file: str = "", name: str \| None = None, issues: list[Issue] \| None = None) -> DrawingSheet`; `rebuild_drawing_sheet(sheet: DrawingSheet) -> Node`; `write_drawing_sheet(sheet: DrawingSheet, *, target: int = DEFAULT_TARGET, allow_lossy: bool = False) -> WriteResult`; `opaque_count(sheet: DrawingSheet) -> int`; `KICAD_TOKENS: Mapping[str, str]`; `RESERVED_VARIABLES: frozenset[str]`; `VALUE_ATOMS: Mapping[str, frozenset[str]]`; `CORNER_ATOMS`, `SCOPE_ATOMS`, `CANONICAL_ORDER`; `ISSUE_CODES: Mapping[str, Severity]` (Decision 8); `EVIDENCE`, `WRITE_EVIDENCE` (`INFERRED`, `H-K-WKS-CORNER`) |
| `src/fenolite/backends/kicad/pcb.py` (c0009, c0017; extended) | `project_paper(node: Node, *, issues: list[Issue] \| None = None) -> SheetFrameRef \| None`; `project_title_block(node: Node) -> TitleBlock`; `paper_node(sheet: SheetFrameRef \| None) -> Node`; `title_block_node(block: TitleBlock) -> Node`; `TITLE_BLOCK_FIELDS: Mapping[str, str]`; `ISSUE_CODES` gains `kicad.board.paper-unmodelled`; `FLOOR_HEADS` gains six names; `CREATED_ROOT_HEADS` unchanged; `CANONICAL_ORDER["kicad_pcb"]` inserts `title_block` after `paper`, and `CANONICAL_ORDER["title_block"] = ("title", "date", "rev", "company", "comment")` |
| `src/fenolite/backends/kicad/pro.py`, `proerrors.py`, `triad.py` (c0010; extended) | `apply_sheet_keys(project_text: str, design: Design, *, allow_lossy: bool = False, issues: list[Issue] \| None = None) -> str`; `PAGE_LAYOUT_POINTER = "/pcbnew/page_layout_descr_file"`; `SHEET_KEY_PATHS = frozenset({"/text_variables/*"})`; `ProjectInfo.drawing_sheet: str \| None = None`, `ProjectInfo.text_variables: tuple[tuple[str, str], ...] = ()`; `proerrors.ISSUE_CODES` gains `kicad.project.reserved-variable` (error), `kicad.project.dropped-variable` (warning) and `kicad.project.unread-variable` (info); `write_triad` runs `apply_sheet_keys` |
| `src/fenolite/backends/kicad/backend.py`, `__init__.py` | `KicadBackend.write_sheet(sheet: DrawingSheet, *, target: int \| None = None, allow_lossy: bool = False) -> WriteResult`; `CAPABILITIES.write_kinds` gains `kicad_wks`; re-exports of the `wks` functions |
| `docs/cli-contract.md` (updated) | the `result.backends` example lists `kicad_wks` in `write_kinds` |
| `src/fenolite/templates/__init__.py` (new) | re-exports below; `EXAMPLES = ("iso5457_generic", "letter_generic")`; `example_path(name: str) -> Path` |
| `src/fenolite/templates/spec.py` (new) | `TitleCell(row: int, col: int, span: int = 1, label: str = "", token: str = "", font_size: Nm \| None = None, justify: HJustify = "left")`; `FrameSpec(line_width, zones, zone_pitch, zone_band, zone_line_width, zone_text_size)`; `TitleBlockSpec(corner, columns, rows, line_width, label_size, cells)`; `BitmapSpec(path: str, pos: SheetPoint, scale_ppm: int)`; `SheetSpec(name, sizes, portrait, width, height, margins, text_size, line_width, text_line_width, frame, title_block, bitmap, provenance)`; `load_spec(source: str \| os.PathLike[str], *, file: str = "", require_provenance: bool = False) -> SheetSpec`; `TemplateError(FormatError)` with `issues: tuple[Issue, ...]`; `ISSUE_CODES` (Decision 11) |
| `src/fenolite/templates/build.py` (new) | `build_sheet(spec: SheetSpec, *, base_dir: Path \| None = None, issues: list[Issue] \| None = None) -> DrawingSheet` |
| `src/fenolite/templates/layout.py` (new) | `layout(sheet: DrawingSheet, *, width: Nm, height: Nm, page: int = 1) -> SheetLayout`; `SheetLayout(texts: tuple[PlacedText, ...], lines: tuple[PlacedLine, ...], bitmaps: int)`; `PlacedText(text: str, x: Nm, y: Nm, size: tuple[Nm, Nm])`; `PlacedLine(x1: Nm, y1: Nm, x2: Nm, y2: Nm)`; `resolve_text(text: str, block: TitleBlock, *, paper: str, filename: str, sheet: int = 1, sheets: int = 1) -> str` |
| `src/fenolite/templates/examples/iso5457_generic.sheet.toml`, `letter_generic.sheet.toml` (new) | CC0 examples, first line `# SPDX-License-Identifier: CC0-1.0` (package data) |
| `src/fenolite/templates/PROVENANCE.md` (new) | the provenance table of `docs/provenance.md` (columns `fact-or-area`, `public source`, `licence of source`, `date`, `how used`), with rows for S-0077, S-0078 and S-0079 (`facts only`) |
| `src/fenolite/cli/cmd_template.py` (new) | `COMMAND` (`name="template"`, `mutates=True`); `register` adds the positional `action` (choices `("build",)`), `SPEC`, `--target` and `-o/--out` to the command's own parser (no nested sub-parser); `example_args` end with `--dry-run` |
| `tests/unit/model/test_presentation.py`, `tests/unit/test_schema_drift.py` | model, tokens, paper sizes, validation, schema |
| `tests/unit/backends/kicad/test_wks_read.py`, `test_wks_write.py` | reader, RT1, writer, refusals, closed codes |
| `tests/unit/backends/kicad/test_pcb_sheet.py`, `test_pro_sheet.py` | paper and title block; project keys |
| `tests/unit/templates/test_spec.py`, `test_build.py`, `test_layout.py` | loader, builder, predictor (including `_expected.py`) |
| `tests/unit/cli/test_template_cmd.py` | command, exit codes, determinism |
| `tests/residue/test_template_residue.py` | example provenance and texts |
| `tests/corpus/test_wks_corpus.py` (`needs_corpus`) | RT1 and opaque count on `kicad-demo-10-0-6-wks-01` |
| `tests/kicad/sheets/_svg.py`, `_sheet_bench.py`, `_expected.py` | `read_sheet_svg(text: str) -> SheetSvg(width_mm: Decimal, height_mm: Decimal, texts: tuple[SvgText, ...], paths: tuple[Segment, ...])`; `DRAWING_SHEET_ERROR = "Error loading drawing sheet"`; `export_sheet_svg(board: Path, sheet: Path \| None, *, files: Mapping[str, Path] \| None = None) -> SheetCase` (memoised per session; a case keeps its output lines); `classify(case: SheetCase, *, default: SheetCase, control: SheetCase, marker: str \| None = None) -> str`; `board_text(*, paper: str, title_block: str = "") -> str`; literal probe expectations |
| `tests/kicad/sheets/test_svg_reader.py`, `test_sheet_verdict.py`, `test_sheet_probes.py`, `test_sheet_acceptance.py`, `test_project_sheet.py` | hermetic SVG reader; hermetic verdict classes on fake runs; probes; acceptance; project keys |
| `tests/kicad/_probes.py` (c0017; extended) | the probe ids of Decision 16 |
| `tests/_boards.py` (c0017; extended) | `created_board()` gains `SheetFrameRef("A4")` and a seven-field `TitleBlock` |
| `tests/data/kicad/sheets/all_items.kicad_wks`, `sub_um.kicad_wks`, `probe_*.kicad_wks`, `logo_1x1.png`; `tests/data/MANIFEST.toml` | authored CC0 fixtures, `origin = "authored"` (`sub_um` holds a `line` with a sub-micrometre length) |
| `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json` | regenerated with the new probes |
| `docs/formats/kicad/worksheet.md` (new), `docs/formats/kicad/board.md`, `docs/formats/sheets.md` (new) | worksheet facts; paper and title-block rows; paper sizes and frame figures in Fenolite's words |
| `docs/sheet-templates.md` (new), `docs/adr/0005-sheet-templates.md` (new), `docs/adr/README.md`, `tests/unit/test_adrs.py` | format reference; ADR (`Proposed`), index row, `REQUIRED` |
| `docs/evidence/sources.md`, `docs/hypotheses.md`, `src/fenolite/backends/kicad/PROVENANCE.md`, `LEGAL-ANNEX.md`, `tests/unit/test_provenance.py`, `tests/unit/test_format_facts.py` | registers; `test_provenance.py` also checks `templates/PROVENANCE.md`, `test_format_facts.py` also checks `sheets.md` |

Layering: `model.presentation` imports `core` only. `templates` imports `core`, `model` and the standard library (`tomllib`, `decimal`, `base64`). `wks` imports `core`, `model`, `backends.base` and its own package (`versions`, `sexpr`, `slots`). `pcb` gains `model.presentation`; `pro` gains `wks` (for `RESERVED_VARIABLES`), and `wks` imports neither `pcb` nor `pro`, so no cycle forms. `cli/cmd_template.py` imports `templates` and `backends.kicad` (`cli` → any). Every edge stays inside `package-layering`.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0075 | https://docs.kicad.org/10.0/en/pl_editor/pl_editor.html | GPL-3.0-or-later or CC-BY-3.0-or-later (stated on the page; facts only) | text variables, corner positions and the right-bottom default, repeat and label increment, page-1 options, bitmaps plotted only to PDF and PostScript (10.0) |
| S-0076 | https://docs.kicad.org/9.0/en/pl_editor/pl_editor.html | to verify on the page (facts only) | the same facts for 9.0 |
| S-0077 | https://standards.iteh.ai/catalog/standards/iso/cda39033-c87c-4173-a875-365a3e33753f/iso-5457-1999 | copyright ISO; public preview shown by a distributor; dimensions read as facts only, text and figures never reproduced (to verify on the page; use confirmed in the ADR-0005 review) | trimmed sizes A0 to A4, borders, frame and grid line widths, 50 mm reference fields, lettering of fields, title-block position |
| S-0078 | https://standards.iteh.ai/catalog/standards/iso/cda0743a-d12c-45c6-87fd-4e96ffda6041/iso-7200-2004 | copyright ISO; public preview; field names and dimensions read as facts only (to verify on the page; use confirmed in the ADR-0005 review) | title-block data field names, 180 mm title-block width |
| S-0079 | https://en.wikipedia.org/wiki/Paper_size | CC-BY-SA-4.0 (facts only) | A5, Letter, Legal and Tabloid dimensions |

Cited from other changes, never re-registered: S-0001 (`paper` and `title_block` syntax, the page's common-syntax sections; "used for" cell widened by task 1.1, because it names only millimetres and the 1 nm resolution today), S-0020 (`kicad-cli` runs), S-0022 and S-0037 (`pcb export svg`, `--drawing-sheet`; "used for" cells widened by task 1.1), S-0029 (the 9.0.9 image), S-0032 (worksheet version constant), S-0035 (worksheet syntax, 1 µm resolution, `pngdata`), S-0036 (worksheet names, `page1only`, `notonpage1`), S-0045 (`KIPRJMOD`), S-0058 (demo file contents: the `User` paper spelling and the demo worksheet; "used for" cell widened by task 1.1). S-0066 (kicad-templates) is named only to forbid its use. If a URL above is already registered when this change is implemented, the existing id is cited and the row is not duplicated. No KiCad source file is read beyond the keyword and version files already registered (S-0032, S-0036).

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-WKS-SVG | `pcb export svg <board> -l Edge.Cuts --mode-single [--drawing-sheet <f>]` writes an SVG whose `width` and `height` give the page in mm, with a viewBox in page mm, one hidden searchable `<text>` per drawn worksheet text holding the resolved string and its anchor, and worksheet lines as `<path>` elements (S-0020, S-0022, S-0037; observed 2026-10-01) | `tests/kicad/sheets/test_sheet_probes.py::test_svg_shape` | `wks-svg-shape` `present` on 9.0.9 and 10.0.6: an A4 board's page is within 0.01 mm of 297 × 210 mm, and a sheet with three `tbtext` items adds exactly three hidden texts with those strings |
| H-K-WKS-FALLBACK | A missing `--drawing-sheet` file and a `page_layout_descr_file` naming a missing file are ignored silently (exit 0, no message, default sheet drawn); a broken file prints "Error loading drawing sheet", draws the default sheet and exits 0 (S-0020; extends `H-K-TOK-WKS-ORACLE`) | `tests/kicad/sheets/test_sheet_probes.py::test_fallback` | `wks-missing-file` and `wks-pro-missing` `absent`, `wks-broken` `reject`, on 9.0.9 and 10.0.6 |
| H-K-WKS-CORNER | A point is an offset from its named corner of the margin box, positive toward the interior; a point without a corner atom uses the right-bottom corner (S-0035, S-0075, S-0076) | `tests/kicad/sheets/test_sheet_probes.py::test_corners` | `wks-corners` `equal`: four corner texts and one default-corner text drawn as predicted (x within 0.01 mm, y within half the text height) on A4 and A3 boards, on 9.0.9 and 10.0.6 |
| H-K-WKS-REPEAT | `repeat N` with `incrx`/`incry` draws copies until N or until a copy's start point leaves the margin box (S-0075); `incrlabel` (name S-0036) steps a one-letter or one-digit text (S-0075), and an absent `incrlabel` steps by 1 (observed on 10.0.6). Whether a number steps past `9` is not stated by any source and is measured here | `tests/kicad/sheets/test_sheet_probes.py::test_repeat` | `wks-repeat` `equal`: count, labels and positions of a letter row, a 12-copy number row and a letter row without `incrlabel` agree with the prediction on A4 and A3, on 9.0.9 and 10.0.6 |
| H-K-WKS-PAGE1 | On a board export (page 1 of 1), `(option page1only)` items are drawn, `(option notonpage1)` items are not, and `${#}` and `${##}` give `1` (S-0075; names S-0036) | `tests/kicad/sheets/test_sheet_probes.py::test_page1` | `wks-page1only` `present` and `wks-notonpage1` `absent`, on 9.0.9 and 10.0.6 |
| H-K-WKS-VARS | The board's `title_block` fills `${TITLE}`, `${ISSUE_DATE}`, `${REVISION}`, `${COMPANY}` and `${COMMENT1}` … `${COMMENT3}`; `${PAPER}` gives the paper name as written; `${FILENAME}` the board file name; a `.kicad_pro` `text_variables` member fills `${NAME}`; an undefined `${NAME}` is drawn literally (S-0001, S-0075) | `tests/kicad/sheets/test_sheet_probes.py::test_tokens` | `wks-tokens` `equal` (the 11 tokens and one parameter resolved as `resolve_text` predicts) and `wks-undefined-var` `present`, on 9.0.9 and 10.0.6 |
| H-K-WKS-VALUES | The value atoms Fenolite writes load (`ltcorner`, `lbcorner`, `rtcorner`, `rbcorner`, `page1only`, `notonpage1`, `left`, `center`, `right`, `top`, `bottom`, `bold`, `italic`), and an unknown value atom fails the load with the message (S-0035, S-0036) | `tests/kicad/sheets/test_sheet_probes.py::test_values` | every `wks-value-<atom>` `load` and `wks-value-unknown` `reject`, on 9.0.9 and 10.0.6 |
| H-K-WKS-BITMAP | A PNG written as `pngdata` with at most 32 space-separated hex bytes per `data` row loads; bitmaps are plotted only to PDF and PostScript (S-0035, S-0075) | `tests/kicad/sheets/test_sheet_probes.py::test_bitmap` | `wks-bitmap-corrupt` `present` (a decoder line absent from `wks-control`), `wks-bitmap` `load` with a 1×1 authored PNG, and `wks-bitmap-clean` `absent` (none of those lines in the output of `wks-bitmap`), on 9.0.9 and 10.0.6; without a `present` corrupt control the row stays `INFERRED`; plotting stays `INFERRED` |
| H-K-WKS-RES | Worksheet lengths have a 1 µm minimum unit, and digits beyond three decimals are truncated (S-0035). A scratch run on 10.0.6 drew 50.0006 mm unchanged, so a refutation is expected | `tests/kicad/sheets/test_sheet_probes.py::test_resolution` | `wks-resolution` `equal`: a line end written 0.0006 mm past a whole millimetre is drawn at the truncated micrometre (within 0.0001 mm) on 9.0.9 and 10.0.6; `inconclusive` when the SVG has fewer than 4 decimals; any other drawing refutes the row, and a `-2` successor records what KiCad draws |
| H-K-PCB-PAPER | `(paper "A0")` … `(paper "A5")` with optional `portrait`, and `(paper "User" W H)`, set the board page; `User` takes W × H mm exactly (S-0001; `User` spelling in demo boards, S-0058) | `tests/kicad/sheets/test_sheet_probes.py::test_paper` | every `pcb-paper-<name>` `equal`: the SVG page within 0.05 mm of `PAPER_SIZES` for A0 to A5 and exact for `User` (Letter, Legal, Tabloid, one custom size), orientation as written, on 9.0.9 and 10.0.6 |
| H-K-PRO-WKS | `pcbnew.page_layout_descr_file` holding a project-relative name or `${KIPRJMOD}/<name>` is used by `pcb export svg` without `--drawing-sheet`, and `text_variables` members resolve in that sheet (S-0045, S-0075) | `tests/kicad/sheets/test_sheet_probes.py::test_project_keys` | `wks-pro-relative` and `wks-pro-kiprjmod` `present` (their marker and a `text_variables` value drawn) on 9.0.9 and 10.0.6, with projects from `pro.template(target)` and the keys set in the test |
| H-K-WKS-PCT | KiCad resolves legacy `%` text codes in worksheet texts (`%T` the title, `%R` the revision) in `page_layout` files and in `kicad_wks` 20231118 files (observed on 10.0.6 on 2026-10-01; the demo worksheet uses such codes, S-0058) | `tests/kicad/sheets/test_sheet_probes.py::test_percent` | `wks-percent` `equal`: `Title: %T` and `Rev: %R` drawn with the board's title and revision, in both roots, on 9.0.9 and 10.0.6 |

`layout` depends on `H-K-WKS-CORNER`, `H-K-WKS-REPEAT` and `H-K-WKS-PAGE1`; the writer's refusals do not depend on any open row (Decisions 5 and 6). Every row starts `INFERRED` with result `pending` and is settled by the probe spike (group 2), before the code that relies on it. The `write_triad` half of the project-key behaviour is not a hypothesis criterion: it is acceptance evidence of `test_project_sheet.py` (task 11.2).

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| One `.kicad_wks` per example drawn as predicted on two sizes, with controls (v0.1 item 4) | `KICAD-VERIFIED` on 10.0.6 (local and `kicad-10`) and 9.0.9 (`kicad-9`) | `tests/kicad/sheets/test_sheet_acceptance.py` |
| SVG shape, silent fallback and broken-sheet message | `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-WKS-SVG`, `H-K-WKS-FALLBACK`) | `test_sheet_probes.py` |
| Corners, repeat and label step, page-1 scope | `KICAD-VERIFIED (9.0.x, 10.0.x)` when the probes settle, otherwise `INFERRED` with the hypothesis and the reason | `test_sheet_probes.py` |
| Token resolution, value atoms and legacy `%` codes | the same (`H-K-WKS-VARS`, `H-K-WKS-VALUES`, `H-K-WKS-PCT`) | `test_sheet_probes.py` |
| Paper forms on boards | the same (`H-K-PCB-PAPER`) | `test_sheet_probes.py::test_paper` |
| Project keys draw the sheet | the same (`H-K-PRO-WKS`) for the keys; `KICAD-VERIFIED` on both majors for a `write_triad` set (acceptance) | `test_sheet_probes.py::test_project_keys`; `test_project_sheet.py` |
| Bitmap loading | `KICAD-VERIFIED (9.0.x, 10.0.x)` only when `wks-bitmap-corrupt` is `present`, `wks-bitmap` is `load` and `wks-bitmap-clean` is `absent`, otherwise `INFERRED` (`H-K-WKS-BITMAP`) | `test_sheet_probes.py::test_bitmap` |
| Bitmap plotting | `INFERRED` (S-0075, `H-K-WKS-BITMAP`) | none; the SVG plotter draws no bitmap |
| 1 µm resolution (S-0035's truncation) | `KICAD-VERIFIED (9.0.x, 10.0.x)` if `wks-resolution` is `equal`; otherwise the row is refuted and a `-2` successor records what KiCad draws. The writer refusal and the reader's opaque rule stay Fenolite choices either way | `test_sheet_probes.py::test_resolution` |
| Reading third-party worksheets | `INFERRED` (one corpus origin plus authored fixtures; not `CORPUS-VERIFIED`) | `tests/corpus/test_wks_corpus.py` |
| A single `template build` run | `INFERRED` (`wks.WRITE_EVIDENCE`, `H-K-WKS-CORNER`): it runs no `kicad-cli` | `test_template_cmd.py` |
| Loader, provenance check, builder, predictor arithmetic, reader, writer, RT1, board projections, project keys in text | mechanical (unit tests) | unit tests of groups 4 to 10 |
| ISO 5457 and ISO 7200 | no conformance claim | ADR-0005 |

`wks.EVIDENCE` (reading) and `wks.WRITE_EVIDENCE` stay `INFERRED`: a read or write runs no `kicad-cli`, and the oracle verifies the constructs, not each file. The hypothesis rows carry the verified levels. The merge is blocked while the acceptance test fails on either major or a control gives another outcome.

## Budget (about 2 weeks; the plan lines were 0.5 week for templates and half of a 0.5-week rules and worksheet line, about 3.75 days)

| work | days |
|---|---|
| registers, naming gate, consumed-name check | 0.5 |
| probe spike: SVG reader, bench, probe fixtures, probes | 0.75 |
| format pages (`worksheet.md`, `board.md` rows, `sheets.md`) | 0.5 |
| model and schemas | 0.75 |
| `wks.py` reader, RT1, writer | 1.25 |
| board `paper` and `title_block` | 1.0 |
| project keys | 0.5 |
| templates: loader 0.75, builder 0.5, predictor 0.5 | 1.75 |
| examples, residue test, ADR, user guide | 0.75 |
| command and capability report | 0.5 |
| acceptance oracle on both majors | 0.75 |
| closing | 0.5 |
| **total** | **9.5** |

The plan gives about 3.75 days to this work (0.5 + 0.25 week). The estimate is 9.5 working days, about 2.5 times the plan lines, in line with c0008's overrun; the roadmap's 7 days did not count the SVG oracle and the predictor. Cuts, in order: (1) bitmap support (−0.5 day: the model type and the reader keep it, `[bitmap]` is refused); (2) title-block edits on read boards become read-only (−0.5 day); (3) the `apply_project` read-back of text variables (−0.25 day). Floor: 8.25 days. A cut taken amends this change's deltas in the same commit: cut 1 moves the requirement "Optional logo bitmap" to the follow-up, cut 2 rewrites the scenario "Title block projected and edited in place" as a read-only refusal and drops the `title_block` edit from the MODIFIED "Projected fields on write" and "Slot source for model entities", and cut 3 drops the read-back half of "Both keys written and read back". Not optional: the probe spike, the SVG acceptance with all controls, the writer refusals, the provenance-values check and the human review gate.

## Risks / Trade-offs

- [Silent fallback makes a wrong path look accepted] → The drawn-content verdict and a same-session default control; `wks-missing-file` and `wks-pro-missing` pin the fallback per version.
- [A later KiCad stops writing hidden `<text>` or changes the `<path>` form] → `test_probe_results.py` fails on the new version; token resolution and positions drop to `INFERRED` until a new probe settles them.
- [An example resembles an organisation's frame or KiCad's sheets] → Per-number provenance, no kicad-templates or default sheet read by any test, the residue scan, and the maintainer's review before archive.
- [The ISO previews are copyrighted documents shown by a distributor] → Facts only, in Fenolite's words; the licence cells say so; the ADR review confirms the use. Fallback: the naming gate ships `a_series_generic` with Fenolite-choice values.
- [Corner-anchored zones differ from ISO 5457's centred fields] → Stated as a Fenolite choice in the example, `docs/sheet-templates.md` and the ADR; per-size files are rejected because of item 4.
- [KiCad clips repeats at the page, not the margin box, or measures corners differently] → The probe spike runs before model code; `layout` follows the measurement, and a `-2` successor records it.
- [Board projections regress RT1 on the corpus] → `paper` and `title_block` stay opaque slots; `test_board_rt1.py` and c0017's `created_tokens` test are proofs of group 6.
- [Changing `created_board()` changes outputs pinned by earlier tests] → Task 6.2 runs c0017's writer tests and `pcb-write-heads-*` probes, and every test of c0011, c0013, c0019 and c0020 that uses `created_board()`, in the same commit.
- [Spec text of unarchived c0010 contradicts the new project requirement] → The ADDED requirement states its precedence; task 1.4 converts it to MODIFIED deltas if c0010 is archived first. c0017's requirements are already MODIFIED here.
- [The TOML format grows into a second DSL] → Closed keys, no expressions or includes; a new key needs a change.
- [Bitmap encoding differs by major, or a bad bitmap loads silently] → `wks-bitmap` and the corrupt-bitmap control run per major; bitmap loading stays `INFERRED` when the control cannot tell them apart; bitmap support is the first cut.
- [KiCad resolves legacy `%` codes in texts Fenolite thinks are literal] → The reader keeps such texts opaque, the writer refuses `%` followed by a letter, and `wks-percent` pins the behaviour per major.
- [Budget overrun] → 9.5 days stated with three cuts (floor 8.25 days).
- [The 9.0.9 image runs emulated on arm64 macOS] → About 45 probe runs per major at about 2 s each.

## Migration Plan

- Additive. `Board` gains two optional fields with `None` defaults, so earlier `board.json` documents load unchanged and `board.json` is regenerated. `write_triad` output is byte-identical for designs that set neither key, and boards read before this change rebuild tree-equal.
- To roll back, remove `model/presentation.py`, `backends/kicad/wks.py`, `templates/`, `cli/cmd_template.py`, the new schema, the `pcb` projections and `pro.apply_sheet_keys`, and regenerate `board.json`.

## Open Questions

- Are the ISO 5457:1999 and ISO 7200:2004 public previews (S-0077, S-0078) acceptable as "public standards figures"? The default is yes, for facts only, flagged in their licence cells and confirmed in the ADR-0005 review; otherwise the naming gate ships `a_series_generic`.
- If c0010 is archived before task 1.4 (likely, since the roadmap opens this change after c0019 and c0020), should "Projects carry the drawing sheet and text variables" become MODIFIED deltas of "Project files are synthesised and preserved", "Generated projects are coherent", "Project files are read into the model" and "Project issue codes", with the living text copied in full? The default is yes, so the living specs never contradict each other; the ADDED requirement then keeps only its new rules.
- Divergence on 2026-10-02: c0009 and c0014 (commit `b528e19`) and c0017 (commit `7d973f1`) are archived, so "Board read issue codes", "Created board header", "Projected fields on write" and "Slot source for model entities" are MODIFIED here rather than overridden by ADDED text. c0017's names exist in the working tree and match its contract: `pcb.FLOOR_HEADS`, `CREATED_ROOT_HEADS`, `CANONICAL_ORDER`, `WRITE_ISSUE_CODES` and `write_board`, `tests/_boards.py::created_board(copper=2)`, and `KicadCli.load_board_svg(board, *, files=None)` (checked 2026-10-02). The default is that the committed proposals are the contract, and task 1.4 re-checks every consumed name.
- c0013 defines `projectset.WORKSHEET_POINTER = "/pcbnew/page_layout_descr_file"`, the same value as `pro.PAGE_LAYOUT_POINTER`, and its task 2.2 already asserts in `tests/unit/backends/kicad/test_projectset.py` that the two are equal once `pro.PAGE_LAYOUT_POINTER` exists. The default is to keep both names and add no second assertion: task 7.1 runs c0013's test and checks that the assertion now executes instead of being skipped. c0013 may alias `pro.PAGE_LAYOUT_POINTER` once this change is archived.
- Does `incrlabel` step `9` to `10`? A2 landscape needs 12 number labels. The default is the 12-copy number row in `wks-repeat`; if KiCad does not step past `9`, `load_spec` also refuses zoned sizes needing more than 9 number columns with `template.zone-letters`, and a `-2` successor records the measurement.
- Does KiCad resolve built-in variables beyond the S-0075 list (for example a current-date variable)? The default is `RESERVED_VARIABLES` = the S-0075 list plus `KIPRJMOD`; `wks-undefined-var` shows that an unknown name is drawn literally, and a name found later is added by a follow-up.
- Should c0011's DSL gain `d.sheet(paper=…, drawing_sheet=…, title=…)`? Neither c0011 nor this change takes it: c0011 lists drawing sheets as a non-goal, and `fenolite.dsl` is c0011's. The default follows c0011's Open Questions: a follow-up proposed after this change archives (with c0019, which reworks `build`, or in v0.2a). v0.1 does not need it, because acceptance item 4 passes the sheet with `--drawing-sheet`, and the model API and `write_triad` already carry the fields.
- Should `build` (c0011) write the sheet named by `Board.sheet.drawing_sheet`? The default is no: this change writes only the project key, and the user runs `template build --out <project folder>/<name>.kicad_wks`.
- Should `template build` gain `--verify`, or `check` a sheet stage? The default is neither here; the probes prove the constructs.
- `letter_generic` margins: no public figure for ANSI frames is registered. The default is 12.7 mm on all sides, no zones, labelled `fenolite-choice`.
- Do ANSI `A` … `E` or KiCad's `USLetter`, `USLegal` and `USLedger` need neutral equivalents on read? The default is no: they read as unmodelled paper with `kicad.board.paper-unmodelled`. A public KiCad page naming them would let a follow-up map them.
- 9.0.9 did not create a `.kicad_prl` after `pcb export svg` in the scratch runs, while 10.0.6 did. The default is to hand this to c0010's `.kicad_prl` facts rather than measure it here; `KicadCli.run` works on a temporary copy either way.
