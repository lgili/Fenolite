## Context

c0012 gave Fenolite a neutral drawing sheet (`fenolite.model.presentation.DrawingSheet`: a setup and
corner-anchored `SheetShape`, `SheetText` and `SheetBitmap` items), a builder from `*.sheet.toml`
files and a `.kicad_wks` writer (ADR-0005). ADR-0005 lists "a second-backend token map" as a
follow-up. The v0.3 phase reads the second backend; this change reads its sheet templates.

Facts, all from public sources, to be recorded with source and label in
`docs/formats/altium/sheet-template.md`:

- **What a `.SchDot` is.** A template is drawn as a schematic document and saved with the file type
  "Advanced Schematic template (*.SchDot)". It holds the sheet size and orientation, the border and
  zone settings, graphics (lines, text strings, images) and sheet parameters (S-0261). No source
  describes a container of its own. Two public repositories hold Altium-saved `.SchDot` files whose
  sizes are whole multiples of 512 bytes, as a compound file's are (S-0264, S-0265; listings read,
  nothing downloaded). So: a `.SchDot` is a binary or ASCII schematic with another extension
  (`H-A-RD-SHT-SAME`).
- **Applied template.** When a template is applied to a sheet, its graphics cannot be selected or
  edited there (S-0261). In the file, a template record (kind 39, with a file name) owns the title
  block lines and labels, and the sheet record holds `SHOWTEMPLATEGRAPHICS` and `TEMPLATEFILENAME`
  (S-0130). A second reader puts the children of that record on the sheet (S-0131).
- **Sheet record.** `SHEETSTYLE` 0 to 17 with a drawing area each, slightly smaller than the paper;
  `USECUSTOMSHEET`, `CUSTOMX`, `CUSTOMY`; `WORKSPACEORIENTATION`; `BORDERON`, `TITLEBLOCKON`,
  `REFERENCEZONESON`; `CUSTOMXZONES`, `CUSTOMYZONES`, `CUSTOMMARGINWIDTH`; the font table (S-0130,
  S-0131). The user documentation names the same settings: rows and columns of zones, the corner the
  zone labels start from, the margin width (S-0262). No source gives the margin width or the zone
  counts of a standard style, nor the geometry of the built-in title block.
- **Graphics.** Line 13, rectangle 14, polyline 6, polygon 7, label 4, text frame 28, image 30 and
  their keys; `JUSTIFICATION` 0 to 8 from bottom-left to top-right; `ORIENTATION` 0 to 3 in quarter
  turns; line widths 0 to 3 (S-0130, S-0131).
- **Special strings.** A text that starts with `=` names a parameter of the sheet, the project or
  the variant, and shows its value (S-0130, S-0261). The predefined names are listed in S-0263. A
  name with a space is not resolved reliably (S-0261). A second reader matches the names without
  letter case (S-0131).
- **Images.** An image record has `EMBEDIMAGE`, `FILENAME` and `KEEPASPECT`; embedded files sit in
  the `Storage` stream, compressed (S-0130, S-0147).

**Interface consumed from c0040** (`openspec/changes/c0040-altium-schematic-reader/`, read on
2026-10-03): `read.sch.read_schematic(data, *, file, codepage, issues) -> SchDocument`;
`SchDocument.form`, `.sheet`, `.records`, `.additional`, `.roots`, `.owner_of`, `.children_of`,
`.walk`, `.image_data(image)`; the typed records `Sheet`, `Template`, `Label`, `Line`, `Rectangle`,
`Polyline`, `Polygon`, `Image`, `Parameter` and their `props`; `SchLength.nm()` and `.exact`;
`EmbeddedFile.data()`. This change reads keys through `props` where c0040 names no attribute.

## Goals / Non-Goals

**Goals**

- A user's own `.SchDot` becomes a neutral `DrawingSheet`, then a `.kicad_wks`, in one command.
- Every template record is imported or named in the report.
- No template of any organisation enters the repository, the package or the tests.

**Non-Goals**

- Writing a `.SchDot` (roadmap v0.4, "Sheet templates for the second backend, from the same sheet
  spec as c0012"). `*.sheet.toml` output. Arcs, ellipses, text frames. Colours, fonts, fills.
- The built-in title block and the border of a standard style. PCB and draftsman templates.

## Decisions

1. **The target is `DrawingSheet`, not `SheetSpec`.** A template is free graphics. `SheetSpec` is a
   closed grid of cells with a zoned frame, so it cannot hold a free line.
   - Rejected: recognising a grid and writing a `*.sheet.toml`. It fails on most templates and would
     guess at intent.
   - Rejected: new item kinds (arc, polygon fill) in the model. ADR-0005 keeps the model small; the
     `.kicad_wks` writer would need them too. Open Question 3.
2. **The importer lives in `fenolite.backends.altium.read.sheet`.** `templates` may import only
   `model`, and a backend may not import another backend. The CLI joins the Altium importer and the
   KiCad writer. No `ALLOWED` entry of `tests/unit/test_import_graph.py` changes.
   - Rejected: `fenolite.templates.altium`. It breaks the layering.
3. **The form comes from the content; the extension is ignored.** c0040's reader already reads both.
   A `.SchDoc` with an applied template works too, through the children of record 39.
   - Rejected: refuse a `.SchDoc`. The user's template is often only available as applied.
4. **Template records are the root records and the children of a record 39.** Anything else at the
   root that is not graphics (a component, a wire) is reported with its children as one record.
5. **The drawing area is centred on the named paper.** The area of a style is smaller than its paper
   (S-0130), and the model's points are offsets from the margin box. Centring makes the margin box
   equal the drawing area, so the sheet is exact inside it. Where the area sits on the paper is not
   documented: the centring is a Fenolite choice (`H-A-RD-SHT-AREA`). A style without a neutral
   paper name, and a custom sheet, give paper `custom` with zero margins.
   - Rejected: always `custom`. A4 templates would not match A4 boards.
   - Rejected: scale the area to the paper. It changes every length.
6. **One corner per item, the nearest to its centre.** The sheet is exact on its own size. On another
   size a title block stays in its corner. A user-drawn full-page frame does not stretch; only the
   border drawn from the sheet flags spans two corners.
   - Rejected: one corner for the whole sheet. A title block at the right would leave its corner.
   - Rejected: a corner per point. A long title-block line would stretch and shear the block.
   - An `--anchor` option is Open Question 4.
7. **Micrometre rounding.** The `.kicad_wks` writer refuses a length that is not a whole micrometre
   (`kicad.wks.below-resolution`). A unit of 10 mil is 254 µm, so whole units are exact. Only
   fractional coordinates round, at most 0.5 µm, and the count is reported.
8. **Border and zones are drawn only for a custom sheet.** There the file holds the margin width and
   the zone counts. For a standard style no source gives them, so the importer warns instead of
   guessing. The tick and label rule is Fenolite's (`H-A-RD-SHT-BORDER`). Zone labels start at the
   top-left corner, the default the documentation shows; the key of the other origin is unknown.
   - Rejected: copy margin and zone numbers of each style from a rendering. No public source has
     them. Open Question 2.
9. **The built-in title block is never drawn.** Its geometry is the tool's, not the file's. A template
   with its own title block has it switched off (S-0261).
10. **Text size.** The font table gives a size per font. The neutral text has a width and a height.
    The rule `size × 25.4 mm / 72`, equal for both, is a Fenolite choice: it treats the size as
    points. S-0130 notes that the visible glyph size is somewhat smaller. No width metric exists in
    either model, so texts may be a little wider or narrower than in the source tool.
11. **Special strings: ten names map to tokens, the rest to `{param:NAME}`.** The ten are the ones
    whose meaning matches a neutral token. `=CompanyName` stays a parameter, because
    `=Organization` already maps to `{organization}` and two names on one token could not be told
    apart later. No string maps to `{paper}`.
    - Rejected: map `=CurrentDate` to `{date}`. One is computed by the tool, the other is a field.
    - Rejected: drop a dynamic string. It is kept as a parameter and reported.
12. **Images: an embedded PNG is kept, everything else is reported.** `SheetBitmap` holds PNG bytes
    only (c0012). The core has no image decoder, so nothing is converted. `SheetBitmap` has a scale
    but no box, so the kept image carries a warning with the box size.
    - Rejected: read a linked file. The path is another machine's, and following it would read
      outside the given file.
    - Rejected: report the full path. It may hold a user or organisation name; only the base name
      is shown.
13. **A warning is a loss, refused by default.** `import_sheet` raises `SheetLossError`
    (`FEN-7001`) unless `allow_lossy` is set. The existing global `--allow-lossy` and exit code 7
    already mean this. Nothing can then be dropped without the user asking for it.
    - Rejected: warnings with exit 0. An agent that reads only the exit code would miss a lost logo.
    - Rejected: a new exit code or FEN code.
14. **Command: a second action of `template`.** `fenolite template import SRC --target kicad --out
    OUT`. `cmd_template` already has a positional `action`; it gains one choice. This is the one
    MODIFIED requirement.
    - Rejected: `fenolite import`. That name belongs to the design import (c0043).
    - Rejected: a nested sub-parser. The dispatcher adds the global options to the command's own
      parser (c0012, Decision 19).
15. **Only `--target kicad`.** The only writer of a `DrawingSheet` is `.kicad_wks`. The Python API
    returns the neutral sheet for any other use. A JSON target is Open Question 1.
16. **Fixtures are built in memory.** `tests/_altium_sheet.py` writes records with Fenolite's own
    encoders. No template file is committed, so the residue test can forbid the extension outright.
    - Rejected: commit small authored `.SchDot` files. A binary template in the tree is exactly what
      the residue rule should be able to refuse without exceptions.
17. **Corpus rows are measurement only.** Sheet templates carry identity more than any other file.
    The three rows are fetched, imported and counted. The test asserts form, paper and the
    accounting, and stores nothing. Rows follow c0039's id scheme (`altium-third-party-schdot-01` to
    `-03`; the first draft used an older form, `altium-sch-NN`, fixed at integration) and c0040's
    corpus rule, with the uses `altium`, `origin:third-party`, `altium-sch` and `altium-sheet`. As
    they carry `altium-sch`, c0040's corpus test reads them too; task 1.4 adds their entries to its
    `EXPECTED` table where a row gives a listed warning.
18. **No new ADR.** ADR-0005 already decides the neutral sheet, the token map per backend and the
    ban on shipped organisation sheets. This change adds a "Second backend" note to
    `docs/sheet-templates.md`.

## Files and public API

| File | Change | Public API |
|---|---|---|
| `src/fenolite/backends/altium/read/sheet.py` | new | `import_sheet(data, *, file="", name="imported", allow_lossy=False) -> SheetImport`; `SheetImport`, `SheetSource`, `SheetLossError`; `SHEET_STYLES`, `LINE_WIDTHS`, `ALTIUM_SHEET_TOKENS`, `DYNAMIC_STRINGS`, `ISSUE_CODES`, `EVIDENCE` |
| `src/fenolite/cli/cmd_template.py` | action | `template import SRC --target kicad --out OUT`; `ACTIONS = ("build", "import")` |
| `tests/_altium_sheet.py` | new | `template(name, *, form) -> bytes` for `title_block`, `mixed` and the single-record cases; `WORDS` |
| `tests/unit/backends/altium/test_read_sheet.py` | new | reading, size, border, graphics, report |
| `tests/unit/backends/altium/test_read_sheet_strings.py` | new | special strings, images |
| `tests/unit/cli/test_template_import.py` | new | the command |
| `tests/unit/cli/test_template_cmd.py` | extended | scenario "Unknown action" |
| `tests/kicad/sheets/test_sheet_import.py` | new | the oracle on the imported `title_block` |
| `tests/corpus/test_schdot_corpus.py`, `tests/corpus/manifest.toml` | new, rows | three `altium-sheet` rows |
| `tests/residue/test_template_residue.py` | extended | no `.SchDot`, no compound file in the two packages |
| `docs/formats/altium/sheet-template.md` | new | fact rows |
| `docs/sheet-templates.md`, `docs/altium.md`, `docs/cli-contract.md` | sections | — |
| `docs/evidence/sources.md`, `docs/hypotheses.md`, `src/fenolite/backends/altium/PROVENANCE.md`, `LEGAL-ANNEX.md` | rows | — |

`backends.altium.read.sheet` imports `core`, `model` and `backends.altium.read.sch` only.

## Sources registered by this change

| id | URL | licence | used for |
|---|---|---|---|
| S-0261 | https://www.altium.com/documentation/altium-designer/schematic/creating-templates | Altium documentation, all rights reserved (read for facts) | a template is a schematic saved as "Advanced Schematic template (*.SchDot)"; it holds size, border, graphics and parameters; lines, text strings and images draw a title block; `=<ParameterName>` strings; names with spaces; applied graphics are not editable |
| S-0262 | https://www.altium.com/documentation/altium-designer/schematic/setting-up-document and https://altium.com/documentation/altium-designer/sch-dlg-sheetoptionsdocument-options-sch-ad | Altium documentation, all rights reserved (read for facts) | page options: template, standard and custom modes; margin width; vertical and horizontal zone counts; the corner the zone labels start from; update and removal of a template |
| S-0263 | https://www.altium.com/documentation/cstu/text-string | Altium documentation, all rights reserved (read for facts) | the predefined schematic special strings and which of them the tool computes |
| S-0264 | https://github.com/SMotlaq/schematic-templates at commit `75a3de258d5920835f5648e564dfecb8b7bc991d`: two of its `.SchDot` files, an A4 landscape and an A3 portrait one (SHA-256 recorded by task 1.4) | MIT (`LICENSE`); files saved by Altium Designer, fetched to the corpus cache and never committed | `.SchDot` container and record kinds; census by record kind and key name only |
| S-0265 | https://github.com/Fermium/AltiumTemplates at commit `27f7fadb4443602b9cf23ff1ae71de0c2edb0e2d`: `A4.SchDot` (SHA-256 recorded by task 1.4) | MIT (`LICENSE`); a file saved by Altium Designer, fetched to the corpus cache and never committed | the same facts on a larger template, which may hold an embedded image |

Cited, already registered: S-0130 (sheet record, records 4, 6, 7, 13, 14, 28, 30, 39, 41, the
`Storage` stream), S-0131 (the same keys in a second reader; children of record 39; special-string
names without case), S-0147 (`Storage`), S-0002 (sheet-size table), S-0075 (drawing-sheet
variables), S-0077 and S-0079 (paper sizes). Task 1.1 widens their "used for" cells. S-0266 to
S-0268 stay unused. AltiumSharp version 1 (S-0150) was not consulted for this change; version 2 is
never used.

## Hypotheses registered by this change

All rows: backend `altium`, level `INFERRED`, result `pending`.

| id | statement | test | criterion |
|---|---|---|---|
| `H-A-RD-SHT-SAME` | A `.SchDot` has the container and the records of a schematic document, in either form, and its template graphics are root records | `tests/corpus/test_schdot_corpus.py` | each of the three rows is read by `read_schematic`, has a sheet record 0, and all its drawable records are roots; recorded as supporting data, and `CORPUS-VERIFIED` only once rows of three repositories pass |
| `H-A-RD-SHT-OWNER` | In a document with an applied template, a record 39 owns the template's graphics | unit test on an authored file; census of c0040's `altium-sch` rows for record 39 | every child of a record 39 in the corpus is of a kind in the graphics table or is reported |
| `H-A-RD-SHT-AREA` | The 18 style areas are as S-0130 lists them, orientation 1 swaps them, and centring the area on the paper is a Fenolite choice | unit tests; corpus rows state their style | the style of each corpus row is in the table; the centring is never claimed as a format fact |
| `H-A-RD-SHT-BORDER` | A custom sheet's border is two rectangles one margin width apart, with `CUSTOMXZONES` by `CUSTOMYZONES` equal fields, numbers along x and letters from the top | unit test | the counts of the scenario; `INFERRED` until an author report compares one sheet |
| `H-A-RD-SHT-WIDTH` | `LINEWIDTH` 0, 1, 2 and 3 are 4, 10, 20 and 40 mil | task 1.2 re-reads S-0130; unit test | the fact row quotes S-0130's values; a different value there corrects the table first |
| `H-A-RD-SHT-TEXT` | `JUSTIFICATION` 0 to 8 run bottom-left to top-right, `ORIENTATION` turns the text about its anchor, and the font size is in points | unit tests | S-0130 and S-0131 agree on the nine values; the size rule is labelled a choice |
| `H-A-RD-SHT-STRINGS` | A label text that starts with `=` shows the parameter named by the rest, matched without letter case | unit tests; corpus count of labels that start with `=` | every corpus special string maps to a token or a parameter, or is reported |
| `H-A-RD-SHT-IMAGE` | An embedded image's bytes are the `Storage` file named by the image's `FILENAME` | unit test on an authored `Storage`; corpus row of S-0265 | `image_data` finds a file for every embedded image of the corpus |

No id collides with `docs/hypotheses.md` or with an active change (checked 2026-10-03).

## Evidence level per behaviour (before merge)

| Behaviour | Level | Basis |
|---|---|---|
| A `.SchDot` reads as a schematic | `INFERRED`, with the corpus result as supporting data | three fetched rows of two repositories; c0039's rule needs three repositories for `CORPUS-VERIFIED` |
| Sheet styles, flags, record keys | `INFERRED` (S-0130, S-0131) | unit tests on authored records |
| Paper centring, corner anchoring, text size, border rule | Fenolite's own rules | unit tests; labelled as choices on the fact page |
| Special strings | `INFERRED` (S-0130, S-0261, S-0263) | unit tests |
| Images | `INFERRED` (S-0130, S-0147) | unit test; corpus count |
| Accounting of every record | Fenolite's own rule | unit tests and the corpus test |
| The written `.kicad_wks` draws what `layout` predicts | `ORACLE-VERIFIED(kicad-cli)` | `tests/kicad/sheets/test_sheet_import.py`, the c0012 oracle |
| The command envelope | `INFERRED` | no second reader of an Altium schematic exists |

## Size (design-days)

| work | design-days |
|---|---|
| 1. sources, hypotheses, fact page, provenance, corpus rows | 0.75 |
| 2. fixtures, reading, size and margins | 1.0 |
| 3. graphics, border, strings, images, report | 1.75 |
| 4. command | 0.5 |
| 5. oracle, corpus census, residue | 0.75 |
| 6. documentation | 0.25 |
| 7. closing | 0.5 |
| **total** | **5.5** |

A size, not calendar time.

## Overlaps with other changes

- **c0040.** This change needs its reader and its corpus rule, and archives after it. It adds no
  requirement to `altium-schematic-reader`: every key it needs is reachable through `props`.
- **c0039.** Used only through c0040.
- **c0043.** Imports designs, not sheets. It may later set `Board.sheet` from a schematic's style;
  it would reuse `SHEET_STYLES`.
- **c0012 (archived).** "Template build command" is MODIFIED from the living text of
  `openspec/specs/sheet-templates/spec.md`; no active change modifies it.
- **c0037.** Harness records of `Additional` are reported, never drawn.

## Risks / Trade-offs

- **Most real templates use a standard style with the border on**, so they need `--allow-lossy` and
  come out without a border. Mitigation: the warning says so and the user guide shows how to add a
  frame; Open Question 2 removes the limit once a public source gives the numbers.
- **Text widths differ between tools.** A long value may leave its cell. The neutral model has no
  font metrics; the guide says to check the plot.
- **c0040's attribute names may change before it is implemented.** Mitigation: task 2.1 re-reads
  c0040 and this change uses `props` and record kinds.
- **A corpus file may hold no special string or no image.** Then the matching hypothesis stays
  `INFERRED`, which the criterion allows.
- **A text with `${` or a `%` code** is refused by the `.kicad_wks` writer (c0012). The command exits
  7 with the writer's issue; the import itself keeps the text.

## Migration Plan

- No migration. `template build` keeps its arguments, output and exit codes.
- Rollback: remove the action and the module; no stored file depends on them.

## Open Questions

1. Should `--target json` write the canonical JSON of the `DrawingSheet`? Default: no, until a
   second writer or a reader of that file exists.
2. Should the border of a standard style be drawn from a table of margins and zone counts? Default:
   no, until a public source or an author report gives each number.
3. Should arcs and filled polygons enter the neutral model? Default: no; it is a model change with
   its own proposal.
4. Should `--anchor lt|lb|rt|rb` force one corner? Default: no; the per-item rule covers title
   blocks.
5. Should the maintainer save one authored template in Altium Designer and report how the imported
   sheet compares? Default: yes when the licence in use allows a report, as a later author-report
   row; it does not block this change.
6. Should `=CompanyName` map to `{organization}` when the template has no `=Organization`? Default:
   no; one fixed map is easier to predict.
