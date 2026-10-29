## ADDED Requirements

### Requirement: Drawn schematic in the DSL
`Design.load_schematic(path)` SHALL record a drawn schematic file, relative to the script's folder, and `dsl.drawn_schematic(design)` SHALL return that path or `None`. A second call, an absolute path, or a path outside the script's folder MUST raise `DslError`. The file is not read by the DSL, and `to_model` MUST NOT change.

#### Scenario: Recorded path
- **GIVEN** a design that calls `design.load_schematic("schematic.toml")`
- **WHEN** `uv run pytest tests/unit/dsl/test_load_schematic.py -k recorded` runs
- **THEN** `dsl.drawn_schematic(design)` is `"schematic.toml"`, and `to_model(design)` equals the model of the same design without the call

#### Scenario: Second call
- **WHEN** a design calls `load_schematic` twice
- **THEN** the second call raises `DslError` naming the first path

#### Scenario: Path outside the folder
- **WHEN** a design calls `design.load_schematic("../other/schematic.toml")`
- **THEN** `DslError` is raised naming the path

### Requirement: Drawn schematic in a build
For a design whose drawn schematic is recorded, `cmd_build` SHALL read it with `lens.drawn.read_drawn` and `build_design` SHALL call `backends.kicad.drawn.lower_drawn` where "Schematic in a build" calls `schgen.generate_schematic`, with every later step unchanged. A file that cannot be read MUST exit 3 with `FEN-3004`; a coverage error MUST write nothing (exit 5).

#### Scenario: Drawn example built
- **WHEN** `fenolite build examples/drawn/design.py --out B --confirm --json` runs for target 10
- **THEN** `receipt.written` lists the schematic and its child sheet, the sheets hold the drawn wires and junctions, and a second build writes the same bytes

#### Scenario: Designs without a drawing keep their bytes
- **WHEN** `uv run pytest tests/unit/lens/test_build_bytes_pinned.py -q` runs
- **THEN** every pinned build keeps its bytes

#### Scenario: Missing file
- **GIVEN** a design that loads `schematic.toml` from a folder without it
- **WHEN** it is built
- **THEN** the exit code is 3 and stderr carries `FEN-3004` naming the file

### Requirement: Drawn schematic build guard
A build with a drawn schematic SHALL read back the sheet texts it plans, extract and resolve them, and compare the nets with the circuit before returning any file, without any tool. A connectivity difference MUST give `build.schematic-netlist-differs` (error) with the first `REF-PIN`, and no file. The guard of generated sheets MUST NOT run for drawn ones.

#### Scenario: Lowering defect caught
- **GIVEN** `lower_drawn` patched in the test to move one wire end onto another pin
- **WHEN** `uv run pytest tests/unit/lens/test_build_drawn_guard.py -k defect` builds the example
- **THEN** `files` is empty and one `build.schematic-netlist-differs` error names the pin

#### Scenario: Hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** the example is built with its drawn schematic
- **THEN** the build succeeds

### Requirement: Drawn schematic build result
With a drawn schematic, `result.schematic.source` SHALL be `drawn`, `result.schematic.drawn` SHALL hold `file` and the counts `wires`, `junctions`, `labels`, `buses` and `opaque`, and `schematic-placements.toml` MUST NOT be read; its presence MUST give `drawn.placements-ignored` (warning). Generated schematics MUST report `source` `generated` and `drawn` `null`.

#### Scenario: Result of a drawn build
- **WHEN** the example is built with `--json`
- **THEN** `result.schematic.source` is `drawn` and `result.schematic.drawn.junctions` equals the junctions of the file

#### Scenario: Placements file ignored
- **GIVEN** the example folder with a `schematic-placements.toml`
- **WHEN** it is built
- **THEN** `issues` holds one `drawn.placements-ignored` warning naming the file, and the symbols stand where the drawing puts them
