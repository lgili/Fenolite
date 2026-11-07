## ADDED Requirements

### Requirement: A refused generated schematic is a declared loss
When the schematic generator of an Altium to KiCad conversion refuses the circuit, the conversion SHALL
still write the board and its libraries, SHALL count the schematic as lost with a reason that needs
`--allow-lossy`, and SHALL NOT report the generator's refusal as an error finding. The lost schematic SHALL
explain the `component-missing` of each component that no footprint places.

#### Scenario: A circuit larger than one A0 page
- **WHEN** a PCB document alone holds more units than one A0 page and `fenolite convert --to kicad --allow-lossy` runs
- **THEN** the plan holds the board and exits 0 or 5 without `build.schematic-too-large` as an error
- **AND** without `--allow-lossy` the command exits 7 naming `schematic`

### Requirement: Source sheets and pages of a generated schematic
The schematic that an Altium to KiCad conversion generates SHALL place the parts of each source schematic
document of a flat project on a KiCad sheet of its own, and SHALL spread a sheet that no paper holds over
sibling pages before it refuses the circuit; a page SHALL be refused only when one part alone does not fit.
The written sheets SHALL load in KiCad 9 and 10 with the source's netlist, and two conversions of one
source SHALL write equal bytes.

#### Scenario: A flat project of several sheets
- **WHEN** a flat Altium project whose parts lie on two schematic documents is converted to KiCad
- **THEN** each document's parts lie on `sheets/<document stem>.kicad_sch` under the root sheet
- **AND** the conversion verifies without unexplained differences

#### Scenario: A circuit larger than one page
- **WHEN** a sheet of the generated schematic holds more units than one A0 page
- **THEN** its parts are spread over `<sheet>-1`, `<sheet>-2`, … (`page-1`, … at the root)
- **AND** KiCad's ERC reads every page and its exported netlist is the circuit's
