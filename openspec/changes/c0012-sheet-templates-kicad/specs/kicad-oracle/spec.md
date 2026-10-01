## ADDED Requirements

### Requirement: Drawing sheets are judged by what KiCad draws
Drawing-sheet oracle tests SHALL judge a sheet by the texts and lines that `kicad-cli` draws, never by its exit code: a missing `--drawing-sheet` file or `page_layout_descr_file` falls back silently to the default sheet, with exit 0 and no message (observed on 9.0.9 and 10.0.6 on 2026-10-01, `H-K-WKS-FALLBACK`).
- `tests/kicad/sheets/_svg.py` SHALL provide `read_sheet_svg(text) -> SheetSvg(width_mm, height_mm, texts, paths)`, using only the standard library: the page size from the SVG `width` and `height` in millimetres, every hidden searchable `<text>` with its string and anchor, and every straight segment of the `<path>` elements (`H-K-WKS-SVG`). Its tests MUST run on an authored SVG snippet without `kicad-cli`.
- `tests/kicad/sheets/_sheet_bench.py` SHALL provide `DRAWING_SHEET_ERROR = "Error loading drawing sheet"` and `export_sheet_svg(board, sheet, *, files=None)`, which runs `pcb export svg <board> -l Edge.Cuts --mode-single [--drawing-sheet <sheet>]` through c0009's `KicadCli.run`, with the board, the sheet and any project in `files`.
- A sheet case MUST be `reject` when the output holds `DRAWING_SHEET_ERROR`. Otherwise, comparing its drawn text multiset with the default-sheet control of the same board in the same session, it MUST be `absent` when the two are equal (silent fallback); `load` when they differ and the case's marker text, when it has one, is drawn; and `different` when they differ but the marker is not drawn (KiCad drew a sheet other than the case's).
- Every session MUST run the default-sheet control (`wks-default`, no `--drawing-sheet`) and the positive control `tests/data/kicad/tokens/skeleton.kicad_wks` (`wks-control`). When the positive control is not `load`, or the default control draws no text, every sheet case of the session MUST be `inconclusive`.
- A semantic case MUST be `equal` when every drawn text and line matches the prediction of `fenolite.templates.layout` and `resolve_text`, computed with the page size read from the SVG: a text's x within 0.01 mm and its y within half its text height, and line ends within 0.01 mm. Otherwise it MUST be `different`.
- The living requirement "Load check per file kind" and the token fuzz harness are unchanged.

#### Scenario: Silent fallback is not a load
- **GIVEN** a `--drawing-sheet` path naming a file that does not exist
- **WHEN** the case runs on 10.0.6 and `kicad-cli` exits 0 without the message
- **THEN** the outcome is `absent`, not `load`

#### Scenario: Broken sheet rejected
- **GIVEN** the authored probe sheet of `wks-broken`, which holds `(frobnicate 1)` as an item
- **WHEN** the case runs
- **THEN** the outcome is `reject`, whatever the exit code

#### Scenario: Marker missing is not a load
- **GIVEN** a fake run without the message whose drawn texts differ from the default control but lack the case's marker
- **WHEN** it is classified
- **THEN** the outcome is `different`

#### Scenario: Failed control makes the session inconclusive
- **GIVEN** a session in which the skeleton control is not `load`
- **WHEN** any sheet case of that session is classified
- **THEN** its outcome is `inconclusive`

#### Scenario: SVG reader on an authored snippet
- **GIVEN** an authored SVG with `width="297.0022mm"`, two hidden `<text>` elements and one `<path d="M10 10 L20 10">`
- **WHEN** `uv run pytest tests/kicad/sheets/test_svg_reader.py` runs
- **THEN** `read_sheet_svg` returns `width_mm == Decimal("297.0022")`, the two strings with their anchors, and the segment (10, 10, 20, 10)

### Requirement: One drawing sheet serves several sizes on both majors
`tests/kicad/sheets/test_sheet_acceptance.py` (`needs_kicad`, major-aware) SHALL prove v0.1 acceptance item 4: one `.kicad_wks` per shipped example, produced by `fenolite template build`, is drawn as predicted on every listed size, with the same bytes on both majors.
- For `iso5457_generic` (or `a_series_generic` after the naming gate) on A4 and A3 boards, and for `letter_generic` on Letter and Tabloid boards, each board MUST be written by `write_board` (target 10 on 10.0.6, target 9 on 9.0.9) with that size in `Board.sheet` and a `TitleBlock` whose seven fields are non-empty, and exported with `--drawing-sheet` under c0009's isolated runner.
- For each size the output MUST lack `DRAWING_SHEET_ERROR`; the drawn hidden-text multiset MUST equal the texts of `layout` resolved by `resolve_text` for that title block, the board's paper name as written and its file name; it MUST differ from the default-sheet control of the same board in the same session; and every predicted line MUST be found among the SVG path segments within 0.01 mm.
- The same run MUST hold the controls: the generated sheet with `(frobnicate 1)` inserted is `reject`; a missing `--drawing-sheet` file and a project whose `page_layout_descr_file` names a missing file are `absent`; `skeleton.kicad_wks` is `load`. A control with another outcome MUST fail the test.
- `tests/kicad/sheets/test_project_sheet.py` MUST write, with `write_triad`, a created board with `Board.sheet = SheetFrameRef("A3", drawing_sheet="frame.kicad_wks")`, a `TitleBlock` and one parameter, beside the generated sheet named `frame.kicad_wks`, and MUST find, without `--drawing-sheet`, the predicted texts with the title-block values and the parameter (`H-K-PRO-WKS`).
- The exit code MUST NOT be read. The tests MUST pass on the local 10.0.6 and in the pinned 9.0.9 image, and in the `kicad-10` and `kicad-9` jobs.

#### Scenario: Acceptance on both majors
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/sheets/test_sheet_acceptance.py -rA` runs on the local 10.0.6 and inside the pinned 9.0.9 image
- **THEN** every example and size passes with all controls, and the `.kicad_wks` bytes used are the same in both runs

#### Scenario: Wrong prediction fails
- **GIVEN** a test copy of `layout` that moves one predicted text by 1 mm
- **WHEN** the acceptance comparison runs on the same SVG
- **THEN** it fails naming that text and the size

#### Scenario: Project key draws the sheet
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/sheets/test_project_sheet.py` runs on 10.0.6 and on 9.0.9
- **THEN** it passes, and the drawn texts include the title and the parameter value of the design

### Requirement: Drawing sheet and paper semantics are probed
The drawing-sheet and paper probes SHALL be entries of c0017's `tests/kicad/_probes.py` `PROBES`, run on majors 9 and 10, with their outcomes pinned in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`.
- The sheet of every probe MUST be an authored CC0 fixture `tests/data/kicad/sheets/probe_*.kicad_wks`, declared with `origin = "authored"` in `tests/data/MANIFEST.toml`, except: `wks-default`, `wks-missing-file`, `wks-pro-missing` and `pcb-paper-*`, which use no sheet file; `wks-control`, which uses c0007's `tests/data/kicad/tokens/skeleton.kicad_wks`; and `wks-accept-*`, which use the sheets that `fenolite template build` writes.
- Every probe except `wks-accept-*` MUST run, and its outcome MUST be compared with the expected outcome of the table below and with the corner, repeat, scope, token, value and paper rules of the `design-model`, `kicad-file-backend` and `sheet-templates` requirements, before the model code of the change that adds this requirement (c0012) is written. `wks-accept-*` run with the acceptance test. `pcb-paper-*` and `wks-tokens` are re-run, with the same expected outcomes, on boards written by `write_board` once the board code exists.

| probe | expected outcome | hypothesis |
|---|---|---|
| `wks-svg-shape` | `present` | `H-K-WKS-SVG` |
| `wks-default`, `wks-control` | `present`, `load` | controls |
| `wks-broken` | `reject` | `H-K-WKS-FALLBACK` |
| `wks-missing-file`, `wks-pro-missing` | `absent` | `H-K-WKS-FALLBACK` |
| `wks-corners` | `equal` | `H-K-WKS-CORNER` |
| `wks-repeat` | `equal` | `H-K-WKS-REPEAT` |
| `wks-percent` | `equal` | `H-K-WKS-PCT` |
| `wks-page1only`, `wks-notonpage1` | `present`, `absent` | `H-K-WKS-PAGE1` |
| `wks-tokens`, `wks-undefined-var` | `equal`, `present` | `H-K-WKS-VARS` |
| `wks-value-<atom>`, `wks-value-unknown` | `load`, `reject` | `H-K-WKS-VALUES` |
| `wks-bitmap-corrupt` | `present` | `H-K-WKS-BITMAP` |
| `wks-bitmap` | `load` | `H-K-WKS-BITMAP` |
| `wks-bitmap-clean` | `absent` | `H-K-WKS-BITMAP` |
| `wks-resolution` | `equal` | `H-K-WKS-RES` |
| `pcb-paper-<name>` | `equal` | `H-K-PCB-PAPER` |
| `wks-pro-relative`, `wks-pro-kiprjmod` | `present` | `H-K-PRO-WKS` |
| `wks-accept-<example>-<size>` | `equal` | acceptance item 4 |

- `pcb-paper-<name>` MUST compare the SVG page size with `PAPER_SIZES`: within 0.05 mm for `A0` … `A5` and exactly for the `User` form (Letter, Legal, Tabloid and one custom size), in the orientation written.
- A probe whose outcome differs from this table MUST NOT be overridden: `layout` MUST follow the measurement on both majors, and a successor hypothesis row with suffix `-2` MUST record it (c0014's "Refuted rows keep their id").
- `wks-bitmap-corrupt` holds a `pngdata` whose bytes are not a PNG. Its outcome MUST be `present` when its output holds at least one line (the decoder line) that the output of `wks-control` lacks. `wks-bitmap` holds a 1x1 authored PNG and MUST be classified like any sheet case. `wks-bitmap-clean` runs no `kicad-cli`: it reads the memoised outputs of `wks-bitmap`, `wks-bitmap-corrupt` and `wks-control` of the same session, and MUST be `absent` when no line that `wks-bitmap-corrupt` adds over `wks-control` appears in the output of `wks-bitmap`, and `present` otherwise. Each probe thus has one outcome. A `load` verdict alone cannot tell a good bitmap from a bad one, because KiCad loads the rest of the sheet either way.
- Each hypothesis MUST become `KICAD-VERIFIED (9.0.x, 10.0.x)` only when its probes give the expected outcome on both majors; otherwise it stays `INFERRED` with the reason. Bitmap loading stays `INFERRED` when `wks-bitmap-corrupt` is not `present` or `wks-bitmap-clean` is not `absent` on a major. Bitmap plotting stays `INFERRED` (S-0075).

#### Scenario: Probe outcomes pinned
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/test_probe_results.py` runs in the `kicad-9` and `kicad-10` jobs
- **THEN** it passes, and both probe files hold an outcome for every `wks-*` and `pcb-paper-*` probe of their major

#### Scenario: Probe tests run first
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/sheets/test_sheet_probes.py -rA` runs on 10.0.6 and in the pinned 9.0.9 image
- **THEN** each probe test asserts on `run(<probe id>)` and passes with the outcome of the table

#### Scenario: Paper size measured
- **GIVEN** a board written with `SheetFrameRef("Tabloid")`
- **WHEN** the probe `pcb-paper-tabloid` runs
- **THEN** the SVG page is 431.8 x 279.4 mm and the outcome is `equal`
