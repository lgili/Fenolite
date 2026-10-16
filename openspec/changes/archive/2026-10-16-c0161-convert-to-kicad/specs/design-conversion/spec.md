## ADDED Requirements

### Requirement: Altium to KiCad direction
`fenolite convert SRC --to kicad` SHALL convert an Altium project, PCB document or folder into a KiCad project for the target of `--kicad-version` (9 or 10): the board, the project file, the rules file, a footprint library derived from the board's instances, a symbol library, the library tables and a generated schematic. Each item that the KiCad project cannot hold MUST be a lost row of the report with its reason, and the conversion MUST be verified against the import under the profile `altium-to-kicad`.

#### Scenario: Public documents converted
- **WHEN** `uv run pytest tests/corpus/test_convert_altium_census.py -rA` converts the eight public PCB documents of the corpus to KiCad 10 with `--allow-lossy`
- **THEN** each is written, none gives `convert.unexplained`, and the counts per kind and reason equal those of `docs/evidence/conversion.md`

#### Scenario: Plan of an Altium sample
- **WHEN** `fenolite convert tests/data/altium/blink/blink.PrjPcb --to kicad --out out --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `out/blink.kicad_pcb`, `out/blink.kicad_pro`, `out/blink.kicad_dru`, `out/blink.kicad_sch` and `out/blink.pretty/`, and `result.equivalence.equivalent` is `true`

### Requirement: Layers of a converted Altium board
The board of a conversion to KiCad SHALL have one KiCad layer row per layer it holds: copper rows for an even count from 2 to 32 (an odd count of signal layers gets one empty inner layer, counted `changed` under `stackup`); the non-copper layers by name; `Mech.<n>` onto KiCad's user layers in order of `n`, as many as the target holds; a closed outline on `Altium.KeepOut` as a rule area that keeps out tracks, vias and copper pour on every copper layer. Every other item on a layer without a row MUST be a lost row with its reason.

#### Scenario: Mechanical and keep-out layers
- **GIVEN** the public document `altium-third-party-pcbdoc-06`, whose items lie on `Mech.1`, `Mech.2`, `Altium.KeepOut` and `Altium.74`
- **WHEN** it is converted to KiCad 10
- **THEN** the lines of `Mech.1` and `Mech.2` are on the first two user layers, each closed keep-out outline is a rule area, and the three items of `Altium.74` are lost under their kinds with the reason "a layer outside the stack"

### Requirement: Slots of a converted Altium board
A pad whose slot is turned against the pad SHALL be written with the pad turned to the slot's angle when the pad is a circle, or an oval whose long axis lies along the slot; any other such pad MUST be a lost `pad` with the reason "a slot turned against a pad of this shape".

#### Scenario: Round pad with a turned slot
- **GIVEN** a footprint with a round pad of 2 mm and a slot of 1 x 3 mm at 45 degrees
- **WHEN** the board is converted to KiCad and read back
- **THEN** the pad and its slot have the copper and the hole of the source, and the report loses no pad

### Requirement: Conversion agrees with KiCad's importer
For each public PCB document of the corpus that the direction writes, the written KiCad board SHALL equal the board that `kicad-cli pcb import` (10.0) makes of the same document at level 5 under the profile `kicad-import`, apart from the items the report names lost.

#### Scenario: Two converters agree
- **GIVEN** `kicad-cli` 10.0.6 and the corpus cached
- **WHEN** `uv run pytest tests/kicad/convert/test_a2k_import.py -rA` runs
- **THEN** every written document agrees with KiCad's import at level 5, and the probe `convert-a2k-import` records `equal`

#### Scenario: KiCad loads the converted board
- **WHEN** `uv run pytest tests/kicad/convert/test_a2k_load.py -rA` runs in the pinned 9.0.9 and 10.0.6 images
- **THEN** each board written for that major loads, its DRC writes a report, and the probe `convert-a2k-load` records `equal`
