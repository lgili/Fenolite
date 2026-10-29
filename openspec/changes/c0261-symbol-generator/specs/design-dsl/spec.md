## ADDED Requirements

### Requirement: Multi-unit authored symbols
`Symbol.pin` SHALL accept `unit=1` (0 for common), `hidden=False` and `alternates=()` of `(name, etype)` or `(name, etype, shape)` tuples; `Symbol.unit(number, name="")` SHALL name a unit; `Symbol.graphic` and its shortcuts SHALL accept `unit=0`. A wrong value MUST raise `DslError` at the call. Defaults MUST keep one-unit definitions equal to today's.

#### Scenario: Dual unit with common supply
- **GIVEN** a `Symbol` with `unit(1, "A")`, `unit(2, "B")`, three pins in each unit and two `power_in` pins of unit 0
- **WHEN** its `definition` is read
- **THEN** it has units 1 and 2 named `A` and `B`, `unit_count == 2`, and `pins_of(2)` holds unit 2's pins and the two common pins

#### Scenario: Hidden power refused
- **WHEN** `Symbol.pin("8", "VCC", etype="power_in", hidden=True, ...)` is called
- **THEN** `DslError` is raised and no pin is recorded

### Requirement: Derived symbols in the DSL
`Symbol.derive(name, *, value="", footprint="", description="", datasheet="")` SHALL return a `DerivedSymbol` whose definition has `extends` set to the base name, the base's library and its own properties only. `Design.add` MUST accept it, and MUST raise `DslError` when the base is not added under the same library.

#### Scenario: Variant built
- **GIVEN** a base symbol `Example:EXB6202` and `dr = base.derive("EXB6202DR", value="EXB6202DR")`, both added
- **WHEN** the design is built for KiCad
- **THEN** `lib/Example.kicad_sym` holds `EXB6202DR` with `(extends "EXB6202")`, and a part on `Example:EXB6202DR` resolves the base's pins

### Requirement: Symbols from pin tables in the DSL
`Symbol.from_pins(table, *, library, footprint="", fp_filters=())` SHALL return a finished `Symbol` whose definition equals the output of `fenolite.catalog.generate.symbol.generate_symbol` for the same arguments. Calling `pin`, `unit` or `graphic` on it MUST raise `DslError`. The DSL MUST NOT read the table file.

#### Scenario: Generated symbol in a design
- **GIVEN** `Symbol.from_pins(read_pins("pins/EXB6202.toml"), library="Example")` added to a design
- **WHEN** a part on `Example:EXB6202` is connected by pin name and the design is built
- **THEN** the build resolves every pin, and the written symbol equals the generator's output
