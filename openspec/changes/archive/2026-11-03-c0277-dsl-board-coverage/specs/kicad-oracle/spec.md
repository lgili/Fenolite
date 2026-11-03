## ADDED Requirements

### Requirement: Coverage items pass the oracle
`tests/kicad/board/test_coverage_items.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-COPPER-ART`, `H-K-PAD-SHAPES`, `H-K-TEARDROP`, `H-K-GROUP`, `H-K-IMAGE`, `H-K-DIM-KINDS`, `H-K-ZONE-ARC`, `H-K-FP-OVERRIDE`, `H-K-MODEL-REF` and `H-K-VERBATIM` with one built board per item, each loaded by `pcb drc`, exported to Gerbers and, on 10.0.6, re-saved on a copy in `tmp_path`.

#### Scenario: Items on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_coverage_items.py -rA` runs
- **THEN** every item board records `load`, no violation that names an item of the board, and after `pcb upgrade --force` the item is still present (teardrop zones excepted), with outcomes in `docs/evidence/kicad/probes/10.0.6.json`

#### Scenario: Items on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image
- **WHEN** the same test runs
- **THEN** the target-9 boards record `load` and no violation that names an item, and no re-save probe runs

### Requirement: Builds of ten, sixteen and thirty-two copper layers pass the oracle
`tests/kicad/build/test_layer_builds.py` SHALL settle `H-K-BUILD-LAYERS-32` with the blink variant of `_layercases.py` for n = 10, 16 and 32, under the rules that "Builds of four, six and eight copper layers pass the oracle" sets for n = 4, 6 and 8, and the probe `pcb-stackup-default-<n>` for the same counts.

#### Scenario: Thirty-two layers on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/build/test_layer_builds.py -k "10 or 16 or 32" -rA` runs
- **THEN** each build fills every zone, the DRC report holds no violation and no unconnected item while the canary fires, the export writes one Gerber per copper layer with `Copper,L<i>,…` functions, and the second build writes the same bytes

## MODIFIED Requirements

### Requirement: Created layer tables are probed on both majors
`tests/kicad/board/test_layer_tables.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-PCB-LAYERS` on the running `kicad-cli` with the created test board `tests/_boards.py::created_board`, whose layer table is replaced by the table of n copper layers and whose stack-up, when the created test board carries one (`board-stackup`), is removed, so that the probes judge the table alone and KiCad derives its default stack-up: for every even n from 2 to 32 the table of `layers.created_layers(n)`, for n = 1 the table holding `F.Cu` as its only copper row (change c0277), and for n = 3 the table that the row rule of `kicad-file-backend`, "Created board header", gives for three layers, written by `tests/kicad/board/_layertables.py` because Fenolite refuses to create it. Each table MUST be written for targets 9 and 10 and run through c0009's package runner on a copy in `tmp_path`, with a `{}` project file and an empty `KICAD_CONFIG_HOME`.
- **Load.** On 9.0.9 the target-9 text, and on 10.0.6 both texts, of every even n from 2 to 32 MUST load: `pcb drc --format json --severity-all` writes a report that `read_drc_report` parses (probe `pcb-layers-<n>-t<M>` = `load`). The table of 3 MUST be refused on the same majors (probe `pcb-layers-odd-t<M>` = `reject`). The table of 1 MUST be run and its outcome recorded, `load` or `reject` (probe `pcb-layers-1-t<M>`); it settles `H-K-PCB-ONE-COPPER` and decides whether 1 is a created count.
- **Gerbers.** `pcb export gerbers` MUST write exactly one Gerber per copper layer of the table, named after that layer (probe `pcb-layers-gerbers-<n>-t<M>` = `equal`).
- **Re-save.** On 10.0.6, after `pcb upgrade --force` on the copy, the copper rows of the table (number, name, type and user name, in order) MUST equal the written rows, for both texts (probe `pcb-layers-resave-<n>-t<M>` = `equal`). `kicad-cli` 9.0.9 has no `pcb upgrade` (S-0037), so this probe MUST NOT run there.
- **Same table.** A hermetic test MUST assert that `_layertables.py` gives the rows of `created_layers(n)` for every count of `CREATED_COPPER_COUNTS`, so the probes judge the table that the writer creates.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, and the facts written to `docs/formats/kicad/board.md` with S-0020, S-0022, S-0029, S-0037 and S-0058 and their evidence labels.

#### Scenario: Tables on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_layer_tables.py -rA` runs
- **THEN** both texts of every even n from 2 to 32 record `load` and `equal` for their Gerber and re-save probes, the thirty-two-layer texts give the Gerbers `F.Cu`, `In1.Cu` to `In30.Cu` and `B.Cu`, both texts of the table of 3 record `reject`, and both texts of the table of 1 record their outcome

#### Scenario: Tables on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image
- **WHEN** `uv run pytest tests/kicad/board/test_layer_tables.py -rA` runs
- **THEN** the target-9 texts of every even n from 2 to 32 record `load` and `equal` for their Gerber probes, the target-9 table of 3 records `reject`, the table of 1 records its outcome, and no re-save probe runs

#### Scenario: Probe tables follow the writer
- **WHEN** the hermetic `uv run pytest tests/kicad/board/test_layer_tables.py -k same_table` runs without `kicad-cli`
- **THEN** for every count of `CREATED_COPPER_COUNTS` the rows of `_layertables.py` equal those of `created_layers(n)`
