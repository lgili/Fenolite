## ADDED Requirements

### Requirement: Copies of an embedded board array are placed only where measured
A conversion SHALL place the copies of an Embedded Board Array only for a variant (plain, turned,
mirrored, linked) whose copy placement is recorded from Altium's own output of a saved panel. Every
other array SHALL stay a refused `embedded-board` loss, and a referenced document that is missing or does
not read SHALL be named in the report.

#### Scenario: A measured plain array
- **WHEN** a board holds an unturned, unmirrored array whose placement is recorded and its referenced document reads
- **THEN** the conversion writes each copy's components and copper at the measured places, with each copy's designators and nets kept apart

#### Scenario: A measured turned array
- **WHEN** a board holds an unmirrored array with `ROTATION` 90 whose referenced board has its origin at its shape's lower-left corner
- **THEN** the conversion turns the whole array a quarter turn counter-clockwise about its location, as recorded, and turns each copy's footprints with it

#### Scenario: A mirrored array
- **WHEN** a board holds a mirrored array and no saved output records which copper side a mirrored copy takes
- **THEN** the array stays a refused `embedded-board` loss whose reason names the mirror

#### Scenario: An unmeasured variant
- **WHEN** a board holds a turned array and no saved output records the placement of a turned array
- **THEN** the array stays a refused `embedded-board` loss and the conversion exits 7 without `--allow-lossy`
