## ADDED Requirements

### Requirement: Altium sheet template writing
`fenolite.backends.altium.schdot.write_template(sheet, *, form="binary")` SHALL write a `DrawingSheet` as an Altium schematic template: a schematic document without components that holds the sheet size and margins, the border and reference zones, lines, rectangles, texts and special strings, and an embedded image when the sheet has a logo.
- `import_sheet(write_template(sheet))` MUST give a drawing sheet equal to `sheet` inside the written scope, which `docs/sheet-templates.md` MUST define.
- `SPECIAL_STRINGS` MUST be the table that maps the neutral text variables to Altium's special strings, the inverse of the import's table ("Altium special strings"); a variable without a special string MUST be written as a parameter reference.
- A part the form cannot carry MUST be reported with the import's `altium.sheet.*` codes, and a loss MUST need `allow_lossy`.

#### Scenario: Shipped example
- **WHEN** `write_template(build_sheet(iso5457_generic))` is imported again
- **THEN** the drawing sheet equals the built one inside the written scope, and no `altium.sheet.*` issue is reported

#### Scenario: Unknown variable
- **GIVEN** a sheet with a text `${PROJECT_CODE}`
- **WHEN** it is written
- **THEN** the text record holds `=PROJECT_CODE`

### Requirement: Template build for Altium
`fenolite template build SPEC --target altium --out FILE` SHALL write the template of a `.sheet.toml` with `write_template`, under the rules of the template build command (dry run, confirm, receipt, determinism), and `--altium-format binary|ascii` SHALL select the form.

#### Scenario: Both targets from one specification
- **WHEN** `fenolite template build iso5457_generic.sheet.toml --target altium --out t.SchDot --confirm` and the same command with `--target kicad --out t.kicad_wks` run
- **THEN** both exit 0, and the two files import or read to drawing sheets that are equal inside the written scope
