## Why

Plan item 0012 and v0.1 acceptance item 4 ask for one drawing sheet, generated from a neutral template, that KiCad draws on A3 and A4 boards. Today `paper` and `title_block` are opaque board slots (c0009), created boards write `(paper "A4")` (c0017), and c0010 leaves `text_variables` and `pcbnew.page_layout_descr_file` to this change. Public sources: worksheet syntax and variables (S-0035, S-0075, S-0076), frame and title-block figures from ISO 5457 and ISO 7200 previews (S-0077, S-0078), paper sizes (S-0079). `kicad-cli` 9.0.9 and 10.0.6 silently draw the default sheet for a missing file, so a message check proves nothing.

## What Changes

- `src/fenolite/model/presentation.py` (new): `DrawingSheet` (outside `Design`, prefix `wks`, schema `drawing_sheet.json`), its setup and items (`SheetShape`, `SheetText`, `SheetBitmap`), neutral tokens, `PAPER_SIZES`, `TitleBlock`, `SheetFrameRef`. `Board` gains `sheet` and `title_block`.
- `backends/kicad/wks.py` (new): reader, RT1 rebuild and writer; the writer refuses uninventoried names, unknown value atoms, legacy `%` codes and sub-µm lengths (`FEN-7001`).
- `pcb.py`: `paper` and `title_block` stay opaque slots, projected and written back. `pro.apply_sheet_keys` in `write_triad` sets both project keys.
- `src/fenolite/templates/` (new): `*.sheet.toml` loader with closed keys and per-number provenance, builder (frame, corner-anchored zones, title-block grid, optional PNG logo), layout predictor, CC0 examples `iso5457_generic` (A4, A3) and `letter_generic` (Letter, Tabloid).
- `fenolite template build SPEC --target kicad --out OUT` (mutating); `write_kinds` gains `kicad_wks`.
- Oracle: probes run before model code; acceptance compares KiCad's SVG texts and lines with the prediction, with broken, missing and default-sheet controls.
- Docs `worksheet.md`, `sheets.md`, `sheet-templates.md`, ADR-0005 (`Proposed` until maintainer review); sources S-0075 … S-0079; hypotheses `H-K-WKS-*`, `H-K-PCB-PAPER`, `H-K-PRO-WKS`.

Estimate: 9.5 days; bitmap support is cut first.

## Capabilities

### New Capabilities
- `sheet-templates`: specification files, provenance, builder, logo, layout prediction, determinism, `template build`, examples, decision record.

### Modified Capabilities
- `design-model`: presentation layer (MODIFIED `Model layers for v0.1`); ADDED drawing-sheet definitions, ids, schema and validation.
- `kicad-file-backend`: ADDED drawing-sheet files, issue codes, board paper and title block, project keys, format facts; MODIFIED `Board read issue codes`, `Created board header`, `Projected fields on write`.
- `kicad-slots`: MODIFIED `Slot source for model entities` (paper and title-block edits).
- `kicad-oracle`: ADDED drawn-content verdict, A3/A4 acceptance, worksheet and paper probes.

## Non-goals

- Importing a user's `.kicad_wks` into a template (v0.2a).
- DSL sheet keywords and `build` writing the sheet (follow-up, see design); `check` copying it (c0013); merge on rebuild (c0019).
- Schematic sheets, multi-page numbering, KiCad-only variables as tokens (v0.2a); a second-backend token map (v0.4).
- KiCad's US and `A` … `E` paper names, ANSI frames, centring marks, ISO conformance claims.
- Reading the kicad-templates sheets (S-0066) or KiCad's default sheet as a source.
- `template build --verify`; exports with the sheet (c0024).
- Zone fill, routing, DRC, RT2, library cache, placement, agent loop (c0015, c0016, c0020 … c0025); no `ci-baseline`, `package-layering` or `kicad-version-gating` delta.

## Evidence level required

- Generated sheets drawn as predicted on two sizes, with controls: `KICAD-VERIFIED` on 10.0.6 (local and `kicad-10`) and 9.0.9 (`kicad-9`).
- Corners, repeat, page-1 scope, variables, `%` codes, value atoms, paper forms, project keys: `KICAD-VERIFIED` (9.0.x, 10.0.x) when probes settle, else `INFERRED`.
- Bitmap loading `KICAD-VERIFIED` only if a corrupt-bitmap control is told apart, else `INFERRED`; plotting `INFERRED` (S-0075). S-0035's 1 µm truncation is probed; the µm rules are Fenolite choices. Third-party worksheets `INFERRED`.
- A `template build` run (no `kicad-cli`): `INFERRED`. Loader, builder, predictor, reader, writer, RT1: mechanical.

## Impact

- New `cli/cmd_template.py`, `tests/kicad/sheets/`, schema `drawing_sheet.json`; `board.json` regenerated.
- Registers: `sources.md`, `hypotheses.md`, both `PROVENANCE.md`, `LEGAL-ANNEX.md`, ADR index. No runtime dependency; no new FEN code.
- Depends on c0009 (`KicadCli`, board reader), c0010 (`pro`, `write_triad`), c0014 (registers, ADR numbering), c0017 (`write_board`, probes).
