## ADDED Requirements

### Requirement: Altium import to Python keeps the source drawing

`fenolite import --to python` of an Altium project or schematic document that holds sheets SHALL emit
`schematic.toml` with the source drawing, as it does for a KiCad project, and the emitted `design.py` SHALL
load it with `design.load_schematic`. The drawing SHALL name each symbol by the component path of the emitted
code. The schematic built from the emitted code SHALL equal the source drawing at level S of
`design-equivalence`: the source drawing is the one the Altium extractor gives, the built drawing is the one
extracted from the built KiCad sheets. A source without sheets (a PCB document alone) MUST emit no
`schematic.toml`.

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
