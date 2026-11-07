## MODIFIED Requirements

### Requirement: Pins records
A pins record SHALL hold `[[pin]]` tables with unique `number`, `name` and `type`, and optional `shape`, `hidden`, `unit`, `group` and `alternates`. With a `[symbol]` table that places every pin once and lists its graphics, it SHALL give a `SymbolDef` whose properties are `Reference`, `Value` and `Description` (the summary). `[symbol]` MAY hold `fields`, a list of `{ name, at, rotation, justify, hide }` that places standard fields; it SHALL give `SymbolDef.fields`, and a name that is not a standard field or that repeats MUST raise `FEN-3004`. Without `[symbol]`, using its symbol MUST give `library.generator-missing`.

#### Scenario: Pin placed twice
- **WHEN** a pins record whose `[symbol]` places pin `1` twice is read
- **THEN** `FEN-3004` is raised naming pin `1`

#### Scenario: Field placed twice
- **WHEN** a pins record whose `[symbol] fields` places `Reference` twice is read
- **THEN** `FEN-3004` is raised naming `Reference`

#### Scenario: Fields survive the canonical text
- **WHEN** a pins record with `fields` is written by the canonical writer and read again
- **THEN** its `SymbolDef.fields` are equal

#### Scenario: No drawing and no generator
- **GIVEN** a project pins record without `[symbol]`, and no symbol generator installed
- **WHEN** a design using its id is built
- **THEN** the build reports `library.generator-missing` (error) and writes nothing
