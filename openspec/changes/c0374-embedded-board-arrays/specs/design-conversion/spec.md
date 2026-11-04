## ADDED Requirements

### Requirement: Boards that place other PCB documents are refused losses
A conversion from an Altium PCB document whose `EmbeddedBoards6` storage holds records SHALL count the
document once under the kind `embedded-board`, lost with a reason that needs `--allow-lossy`, until the
records are read. The detection SHALL use only the storage's record count and data length.

#### Scenario: A board that places other boards
- **WHEN** a project's board holds an Embedded Board Array and `fenolite convert --to kicad` runs without `--allow-lossy`
- **THEN** the command exits 7 naming `embedded-board`
- **AND** with `--allow-lossy` the report lists the document as lost with its reason
