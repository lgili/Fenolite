## ADDED Requirements

### Requirement: Drawing sheet and title block in the DSL
`Design.sheet(paper="A4", *, portrait=False, width=None, height=None, drawing_sheet=None)` and `Design.title_block(*, title="", date="", revision="", organization="", doc_id="", responsible="", approver="", variables={})` SHALL record the board's sheet and title block, each at most once; a second call MUST raise `DslError`.
- `paper`, `portrait`, `width` and `height` MUST follow the model's `SheetFrameRef` rules; `width` and `height` are lengths, given together for a user paper.
- `drawing_sheet` MUST be a path relative to the folder of the design script, ending in `.kicad_wks` or `.sheet.toml`; any other ending, an absolute path, or a path leaving that folder MUST raise `DslError`.
- `variables` MUST map text-variable names to string values; a name that does not match the model's parameter-name rule MUST raise `DslError`.
- `dsl.to_model` MUST set `Board.sheet` to the `SheetFrameRef` of the call, with `drawing_sheet` equal to `"<design name>.kicad_wks"` when a drawing sheet is given, and `Board.title_block` to the `TitleBlock` of the call with `params` from `variables`. The source path MUST NOT enter the model; `dsl.drawing_sheet_source(design)` MUST return it, or `None`.
- A design without these calls MUST give the model it gave before this requirement.

#### Scenario: Sheet and title block in the model
- **GIVEN** `d.sheet("A3", drawing_sheet="frames/company.kicad_wks")` and `d.title_block(title="Blink", revision="B", variables={"PROJECT_CODE": "X1"})` in the blink script
- **WHEN** `to_model(d)` runs
- **THEN** `Board.sheet` is `SheetFrameRef("A3", drawing_sheet="blink.kicad_wks")`, `Board.title_block.title` is `Blink`, its `revision` is `B`, its `params` hold `PROJECT_CODE`, and `drawing_sheet_source(d)` is `frames/company.kicad_wks`

#### Scenario: Wrong file type
- **WHEN** `d.sheet(drawing_sheet="frame.pdf")` is called
- **THEN** `DslError` is raised naming `frame.pdf`

### Requirement: Drawing sheets in a build
`fenolite build` SHALL write the drawing sheet that the script names as `<name>.kicad_wks` beside the project, as "Built project files" allows for added steps of `build_design` and added files.
- `cmd_build` MUST read the source: a `.kicad_wks` with `wks.read_drawing_sheet(text, file=<name of the source>)`, a `*.sheet.toml` with the reader of `sheet-templates` and `build_sheet`. A missing or unreadable source MUST exit 3 (`FEN-3001` or `FEN-3004`) before any planned write, because KiCad would fall back to its default frame without a word (`H-K-WKS-FALLBACK`). The reader's infos MUST be reported.
- `build_design` MUST add `<name>.kicad_wks` from `wks.write_drawing_sheet(<the sheet>, target=target, allow_lossy=allow_lossy)`; its errors MUST stop the build with its codes, as other writers do.
- The file MUST be recorded in `.fenolite/build.json` and MUST follow "Edited outputs are not overwritten".
- The project MUST name it through `apply_sheet_keys`, for the board and, when the build writes a schematic, for the schematic (`kicad-file-backend`, "Projects carry the drawing sheet and text variables").
- On a rebuild over an existing board, the paper and the title block that the script declares MUST be written from the script; a board whose script declares neither keeps its own (`layout-lens`, "Board content outside the design is kept").
- `result.drawing_sheet` MUST hold `source` (the path given in the script), `file` (`<name>.kicad_wks`) and `items` (the number of drawn items), or be `null` without a drawing sheet.

#### Scenario: User sheet in a built project
- **GIVEN** the blink script with `d.sheet(drawing_sheet="frame.kicad_wks")` and an authored `frame.kicad_wks` beside it whose root is the legacy `page_layout`
- **WHEN** it is built for target 9 with `--confirm --json`
- **THEN** `receipt.written` lists `blink.kicad_wks`, whose root is `kicad_wks` with the header `(version 20231118)`, `blink.kicad_pro` holds `pcbnew.page_layout_descr_file` `blink.kicad_wks`, and `issues` hold the info `kicad.wks.legacy-root`

#### Scenario: Missing source
- **GIVEN** the same script without `frame.kicad_wks`
- **WHEN** it is built with `--dry-run`
- **THEN** the exit code is 3, stderr carries `FEN-3001` naming `frame.kicad_wks`, and nothing is planned

#### Scenario: Schematic gets the frame
- **GIVEN** c0061 archived and the same script with the file present
- **WHEN** it is built with a schematic
- **THEN** `blink.kicad_pro` holds `schematic.page_layout_descr_file` `blink.kicad_wks` too
