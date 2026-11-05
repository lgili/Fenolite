## ADDED Requirements

### Requirement: Boards that place other PCB documents are refused losses
A conversion from an Altium PCB document whose `EmbeddedBoards6` storage holds records SHALL count the
document once under the kind `embedded-board`, lost with a reason that needs `--allow-lossy`, until the
records are read. The detection SHALL use only the storage's record count and data length.

#### Scenario: A board that places other boards
- **WHEN** a project's board holds an Embedded Board Array and `fenolite convert --to kicad` runs without `--allow-lossy`
- **THEN** the command exits 7 naming `embedded-board`
- **AND** with `--allow-lossy` the report lists the document as lost with its reason

### Requirement: Embedded board arrays are read and named
The Altium reader SHALL read each record of `EmbeddedBoards6` as an array: its referenced document, location,
rotation, mirror, column and row counts, column and row pitch, and Link Location. A storage whose `Header`
count differs from its records, or a record without one of these keys, SHALL be refused as unreadable.
A conversion SHALL list each array as one `embedded-board` item named by the document, the array's number,
the referenced document and its columns and rows, and SHALL keep the loss refused while the copies'
placement is not measured.

#### Scenario: A panel of two arrays
- **WHEN** a board holds two arrays and `fenolite convert --to kicad --allow-lossy` runs
- **THEN** the `embedded-board` row counts 2 items, each named with its referenced document and counts

#### Scenario: Records that do not read
- **WHEN** the `Header` count differs from the records of `EmbeddedBoards6`
- **THEN** the reader refuses the storage and the conversion names the document alone
