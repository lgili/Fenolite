## ADDED Requirements

### Requirement: Created layer tables are probed on both majors
`tests/kicad/board/test_layer_tables.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-PCB-LAYERS` on the running `kicad-cli` with the created test board `tests/_boards.py::created_board`, whose layer table is replaced by the table of n copper layers and whose stack-up, when the created test board carries one (`board-stackup`), is removed, so that the probes judge the table alone and KiCad derives its default stack-up: for n = 2, 4, 6 and 8 the table of `layers.created_layers(n)`, and for n = 3 the table that the row rule of `kicad-file-backend`, "Created board header", gives for three layers, written by `tests/kicad/board/_layertables.py` because Fenolite refuses to create it. Each table MUST be written for targets 9 and 10 and run through c0009's package runner on a copy in `tmp_path`, with a `{}` project file and an empty `KICAD_CONFIG_HOME`.
- **Load.** On 9.0.9 the target-9 text, and on 10.0.6 both texts, of n = 2, 4, 6 and 8 MUST load: `pcb drc --format json --severity-all` writes a report that `read_drc_report` parses (probe `pcb-layers-<n>-t<M>` = `load`). The table of 3 MUST be refused on the same majors (probe `pcb-layers-odd-t<M>` = `reject`).
- **Gerbers.** `pcb export gerbers` MUST write exactly one Gerber per copper layer of the table, named after that layer (probe `pcb-layers-gerbers-<n>-t<M>` = `equal`).
- **Re-save.** On 10.0.6, after `pcb upgrade --force` on the copy, the copper rows of the table (number, name, type and user name, in order) MUST equal the written rows, for both texts (probe `pcb-layers-resave-<n>-t<M>` = `equal`). `kicad-cli` 9.0.9 has no `pcb upgrade` (S-0037), so this probe MUST NOT run there.
- **Same table.** A hermetic test MUST assert that `_layertables.py` gives the rows of `created_layers(n)` for every count of `CREATED_COPPER_COUNTS`, so the probes judge the table that the writer creates.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, and the facts written to `docs/formats/kicad/board.md` with S-0020, S-0022, S-0029, S-0037 and S-0058 and their evidence labels.

#### Scenario: Tables on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_layer_tables.py -rA` runs
- **THEN** both texts of n = 2, 4, 6 and 8 record `load` and `equal` for their Gerber and re-save probes, the eight-layer texts give the Gerbers `F.Cu`, `In1.Cu` to `In6.Cu` and `B.Cu`, and both texts of the table of 3 record `reject`

#### Scenario: Tables on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image
- **WHEN** `uv run pytest tests/kicad/board/test_layer_tables.py -rA` runs
- **THEN** the target-9 texts of n = 2, 4, 6 and 8 record `load` and `equal` for their Gerber probes, the target-9 table of 3 records `reject`, and no re-save probe runs

#### Scenario: Probe tables follow the writer
- **WHEN** the hermetic `uv run pytest tests/kicad/board/test_layer_tables.py -k same_table` runs without `kicad-cli`
- **THEN** for n = 2, 4, 6 and 8 the rows of `_layertables.py` equal those of `created_layers(n)`

### Requirement: Builds of four, six and eight copper layers pass the oracle
`tests/kicad/build/test_layer_builds.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-BUILD-LAYERS` with the blink variant of `tests/kicad/build/_layercases.py` for n = 4, 6 and 8 copper layers: a zone on every inner layer, on `GND` for `In1.Cu`, `In3.Cu` and `In5.Cu` and on `VIN` for the others; the `LED_A` track stepping through a via to the deepest inner layer and back to `B.Cu`; and one via drop each for `GND` and `VIN`. Every run MUST use a temporary folder, an empty `KICAD_CONFIG_HOME` and `--seed`, `--timestamp` and `--no-backup`, and judge DRC only from the JSON report.
- **10.0.6.** For targets 9 and 10: `fenolite build --confirm`, `fill --confirm`, `check`, `export --all --confirm`, then `build --confirm` again. `fill` MUST fill every zone. `check` MUST report the stage `drc.kicad` with no violation, no unconnected item and the canary fired, `zone.fill` with every zone current, and `copper.clearance` with no short and no clearance finding. `export` MUST write one Gerber per copper layer, whose X2 file function is `Copper,L<i>,Top`, `Copper,L<i>,Inr` or `Copper,L<i>,Bot` for its place i in the table, and a job file whose `LayerNumber` is n. The second build MUST leave every project file outside `.fenolite/` with the bytes it had before that build; the views under `.fenolite/` describe the board with its fills and are not compared. Probes: `build-layers-<n>-t<M>` = `absent` (no violation, no unconnected item, the canary fired) and `build-layers-gerbers-<n>-t<M>` = `equal`.
- **Fixtures.** With `FENOLITE_PROBES_WRITE=1`, the 10.0.6 run MUST write the filled target-9 boards of n = 6 and 8 to `tests/data/kicad/layers/l6_t9_filled.kicad_pcb` and `l8_t9_filled.kicad_pcb`, each declared as authored in `tests/data/MANIFEST.toml`. The hermetic `tests/unit/test_layer_fixtures.py` MUST assert that each fixture, read with `read_board`, equals the target-9 build of its count except for the fills and the `filled` flag of its zones. No other built file MUST be committed.
- **9.0.9.** For n = 6 and 8, the fixture MUST replace the board of a target-9 build of the same variant written in the test, and the copy MUST give a DRC report with no violation and no unconnected item and one Gerber per copper layer (probes `build-layers-<n>-t9` and `build-layers-gerbers-<n>-t9` on 9.0.9). 9.0.9 cannot refill zones (S-0037), so it judges the boards that 10.0.6 filled.
- The outcomes MUST be recorded in both probe files.

#### Scenario: Builds on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/build/test_layer_builds.py -rA` runs
- **THEN** for n = 4, 6 and 8 and both targets every zone is filled, `drc.kicad` has 0 violations and 0 unconnected items with the canary fired, the eight-layer export holds the Gerbers `Copper,L1,Top` to `Copper,L8,Bot`, and each rebuild writes the same bytes

#### Scenario: Filled fixtures on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image
- **WHEN** `uv run pytest tests/kicad/build/test_layer_builds.py -rA` runs
- **THEN** the six- and eight-layer fixtures give 0 violations and 0 unconnected items and six and eight copper Gerbers, and the 10.0-only steps are skipped by `kicad_min_major(10)`

#### Scenario: Fixtures follow the build
- **WHEN** `uv run pytest tests/unit/test_layer_fixtures.py` runs without `kicad-cli`
- **THEN** each fixture equals the target-9 build of its count except for zone fills and `filled`, and the test fails, naming the fixture, after a change of the build that the fixture does not have
