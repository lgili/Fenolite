## MODIFIED Requirements

### Requirement: Symbols of a built project
A build with a schematic SHALL write the symbols it embeds into project libraries, by the rule that "Footprints of every row origin are vendored" gives footprints: only what the design uses, under the nicknames of the design.
- For each nickname with an embedded symbol, the build MUST write `lib/<nickname>.kicad_sym` with `symembed.write_symbol_library`, holding the embedded definitions of that nickname (flattened, pin-pad variants included) and, for a nickname that the design authors ("Project-authored symbols"), every authored symbol of it, embedded or not, and `sym-lib-table` MUST hold one row per written nickname with `uri "${KIPRJMOD}/lib/<nickname>.kicad_sym"`, written by `libs.write_lib_table` for the target, rows sorted by nickname.
- The node of an authored symbol MUST be the one that `sym.write_symbol_library` writes ("Project-authored symbols"), in the library file and in the sheet alike. A library whose symbols are all authored, none of them with a pin-pad variant, therefore has the same bytes with the schematic written and with it skipped. An authored symbol counts as a project row for the `vendor` policy.
- With `vendor="project"`, a symbol resolved through a row that is not a project row MUST still be embedded in the sheet, MUST get no library file and no row, and MUST give one `build.global-library` info.
- When the sheet holds a power flag, the file and the row of the flag library (`kicad-schematic`, "Generated sheet content") MUST be written whatever the `vendor` policy: `lib/fenolite.kicad_sym`, or, for a design with a symbol library whose name differs from `fenolite` in letter case only, that library's file, which then holds the flag beside the library's own symbols. So a design with parts of the built-in catalog and a power flag writes `lib/Fenolite.kicad_sym` and no `lib/fenolite.kicad_sym` (before change c0143, releases 0.2.0 and 0.2.1, it was refused with `build.vendor-unsafe-name`). A design whose parts name a library `fenolite`, or that authors a symbol in it, MUST give `build.reserved-library` (error). A design that needs a power flag and holds a symbol named `PWR_FLAG` in the flag library, placed or authored, MUST give `build.reserved-library` (error) with the symbol's lib id as `where`, and nothing is written; without a power flag that symbol is no finding.
- The unsafe-name rule of "Footprints of every row origin are vendored" MUST apply to symbol library files, and `build.library-changed` MUST be given for a symbol library whose planned bytes differ from the recorded hash.
- The copies keep their library's licence; `docs/dsl.md` MUST say so beside the footprint note.

#### Scenario: Libraries of the blink
- **WHEN** the blink is built for target 9
- **THEN** `files` holds `lib/Mini.kicad_sym` with exactly the symbols `Mini_LED`, `Mini_QFP32_IC` and `Mini_R`, `lib/fenolite.kicad_sym` with `PWR_FLAG`, and a `sym-lib-table` with the rows `Mini` and `fenolite` in this order and no `version` child

#### Scenario: Project policy
- **GIVEN** the global setup of "Global footprints vendored"
- **WHEN** `build_design` runs with `vendor="project"`
- **THEN** `files` holds no `lib/Mini.kicad_sym`, `sym-lib-table` holds only the row `fenolite`, the sheet still embeds the three symbols, and `issues` holds one `build.global-library` info per symbol

#### Scenario: Reserved nickname
- **GIVEN** a design with a part of `fenolite:Thing`
- **WHEN** it is built
- **THEN** `files` is empty and `issues` holds `build.reserved-library`

#### Scenario: Catalog library holds the flag
- **GIVEN** the design of `kicad-schematic`, "Generated sheet content", scenario "Catalog parts with a supply"
- **WHEN** it is built for target 9 and for target 10
- **THEN** `files` holds `lib/Fenolite.kicad_sym` with exactly the symbols `Connector_2`, `Linear_Regulator` and `PWR_FLAG`, no `lib/fenolite.kicad_sym`, and a `sym-lib-table` with one row

#### Scenario: The flag's name is taken
- **GIVEN** a design with a power flag and a part of `FENOLITE:PWR_FLAG` from a project library, or one that authors `Fenolite:PWR_FLAG`
- **WHEN** it is built
- **THEN** `files` is empty and `issues` holds one error, `build.reserved-library`, whose `where` is that lib id

#### Scenario: The name is free where no flag is needed
- **GIVEN** the first design of "The flag's name is taken" without its `Power` interface
- **WHEN** it is built
- **THEN** no issue is an error and `lib/FENOLITE.kicad_sym` holds its symbol `PWR_FLAG`
