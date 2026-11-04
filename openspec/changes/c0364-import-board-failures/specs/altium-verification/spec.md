## ADDED Requirements

### Requirement: Parity input names under project subfolders
The `input` of a document command (`parity`, `check`, `roundtrip`) SHALL name the file by its path
relative to the document set's root, in POSIX form, and SHALL hash that file. A PCB document that a
project keeps in a subfolder SHALL be found where the project declares it.

#### Scenario: Parity of a project whose PCB is in a subfolder
- **WHEN** `fenolite parity` runs on an Altium project that declares `PCB/Board.PcbDoc`
- **THEN** the command does not fail with `FEN-1001`
- **AND** `input.path` is `PCB/Board.PcbDoc` and `input.sha256` is the SHA-256 of that file
