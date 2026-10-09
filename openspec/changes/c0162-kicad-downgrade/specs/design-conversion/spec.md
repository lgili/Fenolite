## ADDED Requirements

### Requirement: KiCad downgrade direction
`fenolite convert SRC --to kicad` with a `--kicad-version` older than the major of the source's board SHALL write the project for that target with `downgrade=True`: the board, the root schematic and its sheets, the footprint and symbol libraries of the project's own library tables, and the project and rules files. The report MUST hold one row per resolver id with its counts per action (`rewrite` and `same` as `changed`, `presentation` as a `report` loss, `design` as a `refuse` loss), and the verification MUST compare the board at level 5 and the schematic at level 2 under the profile `kicad-downgrade`.

#### Scenario: Demo project for KiCad 9
- **GIVEN** the KiCad 10.0.6 demo project `pic_programmer` in the corpus
- **WHEN** `fenolite --kicad-version 9 --allow-lossy convert <project> --to kicad --out out --confirm` runs, and `kicad-cli` 9.0.9 loads `out/pic_programmer.kicad_pcb` and runs its DRC
- **THEN** the exit code is 0, the board loads, its DRC by violation type equals 10.0.6's on the source apart from the `design` rows of the report, and the probe `down-demos` records `equal`

#### Scenario: Build keeps refusing
- **GIVEN** a target-9 project whose board was re-saved by KiCad 10.0.6
- **WHEN** `fenolite --kicad-version 9 build <script> --out <project> --dry-run` runs
- **THEN** the exit code is 7 with `FEN-7002`, and its hint names `fenolite convert`
