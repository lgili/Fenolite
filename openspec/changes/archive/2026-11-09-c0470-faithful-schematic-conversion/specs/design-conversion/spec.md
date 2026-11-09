## ADDED Requirements

### Requirement: A converted schematic keeps the source drawing

A conversion between Altium and KiCad of a source that holds schematic sheets SHALL write the source's
drawing, extracted by the backend's drawn extractor, through the drawn writer of the target. A generated
schematic MUST be written only for a source without sheets. For every item of the source drawing, the
written drawing SHALL keep:

- the sheet;
- the position, within 1 nm;
- the rotation and mirror;
- the pin points and the text;
- for a symbol, its part and display mode.

#### Scenario: Altium sheets to KiCad

- **GIVEN** the authored project `tests/data/altium/blink/blink.PrjPcb`
- **WHEN** `fenolite convert <project> --to kicad --out out --confirm --json` runs
- **THEN** level S between the source drawing and the drawing extracted from `out` finds no difference
- **AND** `kicad-cli` 10.0.6 loads every written sheet, and its netlist equals the source circuit

#### Scenario: KiCad sheets to Altium

- **GIVEN** a public KiCad 10.0.6 demo project of the corpus with several sheets
- **WHEN** it is converted to Altium and the written sheets are read back
- **THEN** level S between the source drawing and the read-back drawing finds no difference

#### Scenario: Board alone keeps the generated schematic

- **GIVEN** an Altium PCB document converted alone
- **WHEN** it is converted to KiCad
- **THEN** the schematic is generated, and the report counts it under `schematic` with the reason
  "the source has no schematic sheets"

### Requirement: Converted symbols keep their source graphics

A conversion between Altium and KiCad SHALL write each component with its source symbol:

- the body graphics;
- every part and display mode;
- each pin's position, length, orientation, name, number, electrical type, visibility and decoration.

A pin decoration or graphic that the target cannot draw MUST be written as the closest form the target
holds and counted `changed`, with its reason, under `symbol-graphic` or `pin`.

#### Scenario: Multi-part symbol

- **GIVEN** an authored Altium sheet with a two-part component whose parts sit on different sheets
- **WHEN** it is converted to KiCad
- **THEN** the KiCad symbol has two units with the source's graphics and pins
- **AND** each unit is placed where its part was

### Requirement: Schematic report per object

The report of a conversion that writes a drawing SHALL hold one row for each of these kinds:

- `sheet`, `schematic-symbol`, `symbol-graphic`, `pin`;
- `wire`, `junction`, `label`, `port`, `power`, `bus`, `bus-entry`, `sheet-symbol`, `harness`;
- `no-connect`, `directive`, `schematic-text`, `schematic-graphic`, `image`, `title-block`.

Each row SHALL hold `source`, `written`, `changed` and `lost`, with reasons. The single row `schematic`
MUST NOT be written for such a conversion.

#### Scenario: Rows of the blink project

- **GIVEN** the conversion of `tests/data/altium/blink/blink.PrjPcb` to KiCad
- **WHEN** its report is read
- **THEN** it holds a `wire` row whose `source` equals the number of wires of the source sheet
- **AND** no row named `schematic` is present

### Requirement: Schematic items carried through the other format

An item of a source sheet that the target format cannot hold SHALL be carried in the target. The carrier
for Altium items in KiCad is `Fenolite.Altium.Sheet`, schema `fenolite.altium-sheet.v0`, stored as
canonical JSON in the title-block `comment 9` of each written sheet, which KiCad keeps on a save and its
default worksheet does not draw. The carrier for KiCad items in Altium is the document parameter
`Fenolite.KiCad.Sheet`, schema `fenolite.kicad-sheet.v0`. On the way back the conversion SHALL write the
carried items again, moved with the item that stands for them. Each carried item MUST be counted
`changed`, not `lost`.

#### Scenario: KiCad keeps the carrier on a save

- **GIVEN** a sheet written with a carrier
- **WHEN** `kicad-cli` 10.0.6 saves it again (`kicad-cli sch upgrade --force`)
- **THEN** the carrier read from the saved sheet equals the written one

#### Scenario: Harness through KiCad

- **GIVEN** the authored project `tests/data/altium/hier/altium_hier.PrjPcb`, which holds no PCB document
- **WHEN** its drawing is written to KiCad by the drawing writer of the conversion, read back, and written
  to Altium the same way
- **THEN** level S between the source drawing and the final drawing finds no difference, the harness items
  included

#### Scenario: Hierarchical board through KiCad

- **GIVEN** the Altium project built from the authored example `examples/altium_hier_board` with module
  sheets
- **WHEN** it is converted to KiCad and the KiCad project back to Altium
- **THEN** level S between the source drawing and the final drawing finds no difference, the sheet symbols
  and their entries included

### Requirement: Schematic conversion verified at level S

A conversion that writes a drawing SHALL run level S between the source drawing and the drawing read
back from the written files. It SHALL also compare the resolved drawn netlist with the circuit. A
difference that no report row explains MUST give `convert.unexplained` and exit 5, unless the conversion
ran with `--no-verify`.

#### Scenario: An unexplained moved symbol

- **GIVEN** a test writer that moves one symbol by 1 mm and reports nothing
- **WHEN** the conversion runs
- **THEN** it gives `convert.unexplained` naming that symbol's component path and unit

## MODIFIED Requirements

### Requirement: Changes of the Altium direction
In the report of the direction from KiCad to Altium, a polygon whose fill is not carried from the source (kind `zone-fill`) and a schematic generated from the circuit (kind `schematic`) SHALL be counted under `changed`, not `lost`, each under its reason. A source whose sheets are drawn keeps its drawing (requirement "A converted schematic keeps the source drawing"): its `schematic` row has no change, and its drawn items are counted under their own kinds.

#### Scenario: Detailed contract for changes of the altium direction
- **WHEN** this behavior is exercised
- **THEN** the following detailed conditions MUST hold:

In the report of the direction from KiCad to Altium, a polygon whose fill is not carried from the source (kind `zone-fill`) and a schematic generated from the circuit (kind `schematic`) SHALL be counted under `changed`, not `lost`, each under its reason. The reason of `zone-fill` MUST be "a polygon is written unpoured; Altium fills it on a repour" with the pour mode `outline`, and "the pour is computed by Fenolite from the written document (experimental)" for a polygon poured with `computed`; a polygon refused with `computed` keeps the first reason. A schematic is generated, and counted under `changed`, only when the source has no drawing or its drawing cannot be written.

#### Scenario: Unpoured polygon is a change
- **GIVEN** the routed two-layer KiCad sample, whose board holds a filled zone
- **WHEN** it is converted to Altium with `--altium-pour outline`
- **THEN** the row `zone-fill` has `changed` above 0 and `lost` 0 with the reason of an unpoured polygon, and the row `schematic` has `changed` 1 and `lost` 0

#### Scenario: Computed polygon is a change
- **WHEN** the same sample is converted with `--altium-pour computed`
- **THEN** the row `zone-fill` has `changed` above 0 and `lost` 0 with the reason of a computed pour

#### Scenario: Drawn sheets are not generated
- **GIVEN** the authored nested KiCad project of `tests/_schbuild.py`
- **WHEN** it is converted to Altium
- **THEN** the row `schematic` has `changed` 0 and `lost` 0, and the report holds a `sheet` row

### Requirement: Altium to KiCad direction
`fenolite convert SRC --to kicad` SHALL convert an Altium project, PCB document or folder into a KiCad project for the target of `--kicad-version` (9 or 10): the board, the project file, the rules file, a footprint library derived from the board's instances, a symbol library, the library tables and a schematic. The schematic is the drawing of the source sheets (requirement "A converted schematic keeps the source drawing"); a source without sheets, or whose drawing cannot be written, gets a schematic generated from the circuit. Each item that the KiCad project cannot hold MUST be a lost row of the report with its reason, and the conversion MUST be verified against the import under the profile `altium-to-kicad`.

#### Scenario: Public documents converted
- **WHEN** `uv run pytest tests/corpus/test_convert_altium_census.py -rA` converts the eight public PCB documents of the corpus to KiCad 10 with `--allow-lossy`
- **THEN** each is written, none gives `convert.unexplained`, and the counts per kind and reason equal those of `docs/evidence/conversion.md`

#### Scenario: Plan of an Altium sample
- **WHEN** `fenolite convert tests/data/altium/blink/blink.PrjPcb --to kicad --out out --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `out/blink.kicad_pcb`, `out/blink.kicad_pro`, `out/blink.kicad_dru`, `out/blink.kicad_sch` and `out/blink.pretty/`, and `result.equivalence.equivalent` is `true`
