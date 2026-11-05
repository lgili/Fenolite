## ADDED Requirements

### Requirement: Conversion of a source without a PCB design
`convert` SHALL refuse a source whose design has no PCB with `FEN-3001` (exit 3) before a direction
writes anything. The message SHALL name the PCB documents the project declares and lacks, or say that
the project declares no PCB document. It SHALL NOT fail with an internal error.

#### Scenario: An Altium project whose PcbDoc is missing
- **WHEN** an Altium project declares `PCB/Board.PcbDoc`, that file is absent, and `fenolite convert --to kicad` runs
- **THEN** the command exits 3 with `FEN-3001` and the message names `PCB/Board.PcbDoc`
- **AND** no file is planned
