# import-python Specification

## Purpose
TBD - created by archiving change c0358-native-custom-property-preservation. Update Purpose after archive.
## Requirements
### Requirement: Source custom properties outside the public DSL remain native-owned
A native custom footprint property excluded by the existing Part.properties validation SHALL retain its original native name, value, pose and identity in the vendored footprint definition. The generated script SHALL NOT silently erase it or relax public DSL validation.

#### Scenario: Multiline native property survives import
- **WHEN** an authored native footprint contains a named custom property with line feeds
- **THEN** import and build retain the exact native field and complete strict geometry comparison equals
- **AND** directly passing that value to Part.properties remains refused

#### Scenario: Distinct retained properties remain distinct
- **WHEN** two source instances differ only in an unrepresentable custom property
- **THEN** their vendored definitions remain distinct exact variants
- **AND** no input, field comparison or public validation is suppressed

### Requirement: Native TAB value ownership is exact and bounded
The importer SHALL retain U+0009 TAB in a valid native custom footprint property value through existing native definition properties and slots without changing the printable public Part.properties contract. It SHALL preserve LF behavior and SHALL refuse other unsupported controls and names. No accepted differences or new comparison exclusions SHALL be introduced.

#### Scenario: Authored native TAB roundtrip
- **WHEN** an otherwise valid authored native footprint property value contains TAB
- **THEN** native9/10 import/build proofs preserve its exact value and presentation without generating a nonprintable Part.properties declaration

#### Scenario: Other controls stay refused
- **WHEN** a native property has TAB in its name or CR/NUL/another unsupported value control
- **THEN** import refuses before a write plan and the source remains unchanged

### Requirement: Imported empty values stay empty
`import --to python` SHALL emit `value=""` for a source component whose value is empty, except a
board-only part, which keeps its own value without it. The import self-check SHALL NOT report
`import.unequal` for the value of such a component.

#### Scenario: An imported part with an empty value
- **WHEN** a source board holds a part with an empty value whose vendored symbol's Value is its name
- **THEN** the emitted `Part` call has `value=""`
- **AND** the rebuilt footprint's Value is empty and the self-check reports no value difference

### Requirement: 3D models of an Altium import
`import --to python` of an Altium project SHALL write the same 3D models as `convert --to kicad` of it: the vendored footprints hold the `(model` entries and the import writes the model files they name (change c0409, B9).

#### Scenario: A placed STEP body
- **GIVEN** the committed blink sample whose top-side LED footprint gets an authored body naming an authored STEP file
- **WHEN** `uv run pytest tests/unit/importer/test_altium_models.py -q` converts it and imports it
- **THEN** the converted board and library and the imported library hold one `(model` per placed body, at the same `${KIPRJMOD}` path, and the imported project holds the model file at that path

### Requirement: TAB values of non-KiCad sources
`import --to python` of a source whose backend is not KiCad reads the board of the source's in-memory KiCad conversion. A component property whose value holds U+0009 TAB, and whose footprint holds exactly one field of that name, SHALL be kept natively in the vendored footprint, as the KiCad native TAB contract (c0363) keeps it, so the import needs no `--allow-lossy` (change c0420). A property without exactly one such field SHALL be counted as the unexpressed kind `property-tab`, and the import SHALL go on (change c0379). In both cases the emitted code SHALL NOT hold the property, and the public `Part.properties` contract and the KiCad native TAB contract SHALL NOT change.

#### Scenario: An Altium parameter with a TAB
- **WHEN** `uv run pytest tests/unit/importer/test_native_tab_property.py -k another_backend -q` imports a converted board whose part holds a parameter with a TAB as one footprint field
- **THEN** nothing is unexpressed, the emitted code holds neither the TAB nor the parameter, and exactly one vendored `.kicad_mod` holds the property

#### Scenario: A parameter without its field
- **WHEN** the same test imports that board with the parameter's field removed from the footprint
- **THEN** the import plans its files instead of exiting 3
- **AND** `result.unexpressed` lists `property-tab` with that reference and parameter name

### Requirement: Body and model ledger of an Altium import
`import --to python` of an Altium project SHALL hold every model reference and model file that `convert --to kicad` of it writes, and SHALL report each `body` or `model` loss of that conversion as a `convert.lossy` warning; it MUST NOT lose a body or a model silently.

#### Scenario: The authored fixture imported
- **GIVEN** the authored PCB document of `tests/_altium_models.py`
- **WHEN** `uv run pytest tests/unit/importer/test_altium_models.py -q` converts it and imports it
- **THEN** the imported library and board name the same model paths as the conversion, the imported project holds each of those files, and no `convert.lossy` warning names `body` or `model`

#### Scenario: A loss is reported
- **GIVEN** a body of unknown geometry in the same source
- **WHEN** it is imported
- **THEN** the issues hold one `convert.lossy` warning whose `where` is `body`

### Requirement: Altium import to Python keeps the source drawing

`fenolite import --to python` of an Altium project or schematic document that holds sheets SHALL emit
`schematic.toml` with the source drawing, as it does for a KiCad project, and the emitted `design.py` SHALL
load it with `design.load_schematic`. The drawing SHALL name each symbol by the component path of the emitted
code. The schematic built from the emitted code SHALL equal the source drawing at level S of
`design-equivalence`: the source drawing is the one the Altium extractor gives, the built drawing is the one
extracted from the built KiCad sheets. Building the emitted code with `--target altium` SHALL also write the
drawn sheets directly without refusing carried opaque subtrees, harness records, notes or compile masks. A
source without sheets (a PCB document alone) MUST emit no `schematic.toml`.

#### Scenario: Authored flat project

- **GIVEN** the authored project `tests/data/altium/blink/blink.PrjPcb`
- **WHEN** it is imported with `fenolite import <project> --to python --out code --confirm --json`
- **THEN** `code/schematic.toml` exists and `code/design.py` loads it
- **AND** building `code/design.py` for KiCad gives sheets whose drawing equals the source drawing at level S

#### Scenario: Authored hierarchical project

- **GIVEN** the Altium project built from the authored example `examples/altium_hier_board` with module
  sheets (the authored project `tests/data/altium/hier` holds no PCB document, which an import needs)
- **WHEN** it is imported to Python and the code is built for KiCad
- **THEN** level S between the source drawing and the built drawing finds no difference, sheet symbols and
  their entries included

#### Scenario: PCB document alone

- **GIVEN** the authored PCB document `tests/data/altium/blink/blink.PcbDoc` imported alone
- **WHEN** it is imported to Python
- **THEN** no `schematic.toml` is written

### Requirement: Rules the DSL cannot say are kept as written
`import --to python` SHALL NOT emit a `design.rules` call that the DSL refuses. When a rule of the source's
rules file has no `design.rules` call (an undeclared net class, a selector or limit the DSL cannot write)
and the source holds the text of every rule of that constraint kind, every rule of that kind SHALL be
emitted as `design.verbatim("rule/<n>", <text>, target="kicad_dru")` in file order, and SHALL NOT be counted
as `custom-rule`; the rules of the other kinds SHALL stay `design.rules` calls (change c0427).

#### Scenario: An undeclared class
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -k cannot_say -q` imports the committed `two_sheet` project with clearance rules `ghost` (class `Ghost`, not declared) and `wide`, and a track width rule
- **THEN** both clearance rules are verbatim items in their file order, the track width is `design.rules.minimum`, the script builds, and the built rules file holds the clearance rules `ghost` then `wide`

### Requirement: Nets that only copper graphics name
A net that a copper graphic of the source names SHALL be declared with `Net(...)` and passed as the graphic's
`net=`, whether or not a pad, track, zone or sheet names it (change c0427).

#### Scenario: A board-only net
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -k only_a_copper_graphic -q` imports `two_sheet` with a filled `F.Cu` polygon on net `ISLAND`
- **THEN** nothing is unexpressed, the result is equivalent, the script declares `Net("ISLAND")`, and the built board holds the polygon on `ISLAND`

### Requirement: Paste-layer drawings
A drawing on `F.Paste` or `B.Paste` SHALL be emitted as a DSL drawing call (change c0427).

#### Scenario: A paste polygon
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -k paste -q` imports `two_sheet` with a filled polygon on `B.Paste`
- **THEN** nothing is unexpressed and the built board holds the polygon on `B.Paste`

### Requirement: A straight arc is the line it draws
`import --to python` SHALL emit a drawing arc whose three points lie on one line, with the middle point
between the ends and a width above 0, as `design.line()` from its start to its end, on its layer and of its
width. An arc of
one point, or whose middle point lies beyond an end, SHALL stay counted as `drawing` (change c0427).

#### Scenario: Straight arcs on Dwgs.User
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -k straight_arc -q` imports `two_sheet` with three `Dwgs.User` arcs of width 0.2 mm: one with its middle point between its ends, one of one point, one whose middle point lies beyond its end
- **THEN** the first is `design.line()`, the other two are counted as `drawing`, the script builds, and the built board holds one `Dwgs.User` line from (10, 10) to (12, 10) mm, 0.2 mm wide

### Requirement: Public Altium rows are pinned
The import result of every public Altium PCB document of the corpus manifest SHALL be pinned: exit code,
codes of its error findings, and no unexpressed item (change c0427).

#### Scenario: The public rows
- **WHEN** `uv run pytest tests/corpus/test_altium_import_python.py -q` runs with the corpus cached (row 08 with `FENOLITE_HEAVY=1`)
- **THEN** rows 03 to 07 exit 0 and are equivalent, rows 01, 02 and 08 exit 5 with `import.unequal` only, and no row leaves an item out

