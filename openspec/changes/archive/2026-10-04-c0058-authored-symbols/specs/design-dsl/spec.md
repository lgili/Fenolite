## ADDED Requirements

### Requirement: Project-authored symbols

`fenolite.dsl.Symbol(library, name, *, reference, value="", footprint="", description="")` SHALL author a one-unit symbol. `Symbol.pin(number, name, *, etype="passive", at, length, rotation=0, shape="line")` SHALL record a uniquely numbered pin with exact DSL lengths and one of the supported electrical types, shapes and cardinal rotations. `Design.add(symbol)` SHALL register symbols explicitly by `library:name`, and duplicate IDs or symbols without pins MUST be refused. The DSL SHALL expose the completed definition as a model `SymbolDef`, without adding library definitions to canonical design JSON.

`fenolite build --target kicad` SHALL resolve component symbol IDs against the design's authored definitions before external library sources. It SHALL write one `lib/<nickname>.kicad_sym` per authored library and a `sym-lib-table` whose `${KIPRJMOD}` rows point at those files. These are planned writes on dry-run and appear in the receipt on confirmation. The serializer MUST be deterministic, and the build MUST NOT invoke KiCad tools. The Altium target is outside this requirement.

#### Scenario: Build using only an authored symbol
- **GIVEN** a component whose symbol ID is present only in a `Symbol` attached to the design, and a separately resolvable footprint
- **WHEN** `fenolite build ... --target kicad --dry-run --json` runs
- **THEN** it succeeds without a symbol library table row as input, resolves the symbol pins, and plans its symbol library plus `sym-lib-table`

#### Scenario: Authored symbol library artifact
- **GIVEN** a design with two authored symbols under nickname `Local`
- **WHEN** its KiCad build is confirmed
- **THEN** it writes one `lib/Local.kicad_sym` containing both symbols and one matching `${KIPRJMOD}` table row
