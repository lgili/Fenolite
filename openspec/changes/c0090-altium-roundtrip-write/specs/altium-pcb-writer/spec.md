## ADDED Requirements

### Requirement: Imported boards are written from the model
`backends.altium.lower.from_design(design, *, issues)` SHALL return the inputs of the PCB and schematic writers from a `Design`: footprints with their pads and graphics taken from the board's footprint instances (no library is read), placements, copper, zones, rules, the stack and the classes.
- A footprint instance MUST be written as a component with its own pads; two instances of one library footprint MAY share a library entry only when their pads are equal.
- Native ids of the model that are Altium unique ids MUST be reused as the unique ids of the written components.
- An item outside the written scope MUST be counted per kind in the result and reported once per kind with `altium.not-lowered`.

#### Scenario: Footprints without a library
- **GIVEN** a design read from a KiCad board whose footprint libraries are not present
- **WHEN** `from_design` and the PCB writer run
- **THEN** the PCB document holds every footprint with its pads, and no library file is read
