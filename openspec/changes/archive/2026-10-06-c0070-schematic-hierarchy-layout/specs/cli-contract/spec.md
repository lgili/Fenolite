## MODIFIED Requirements

### Requirement: Netlist command
`fenolite netlist PATH [--source kicad|fenolite] [--min-pins N] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_netlist.py` with `mutates=False`, and SHALL print the components and nets of a KiCad project's schematic without writing any file.
- **Schematic.** `PATH` MUST be a `.kicad_sch` file, or a project folder, `.kicad_pro` or `.kicad_pcb` that `projectset.resolve_board` resolves, whose schematic is `<stem>.kicad_sch`. A missing path or schematic MUST exit 3 with `FEN-3001`; an ambiguous folder MUST exit 2 with `FEN-2001`.
- **Source `kicad`** (the default). The netlist MUST be `kicad-cli sch export netlist` on copies, read with `netlist.read_netlist` through `oracle.export_netlist_of`: the schematic, the sheet files it names inside its folder, and the copy set of the board beside it when there is one (else the project file of its stem). No tool MUST exit 6 with `FEN-6001` and a hint that names `--source fenolite`, an unsupported major with `FEN-6002`, and a run that times out with `FEN-6001` and `retryable: true`. A schematic the tool cannot load, and an export the reader refuses, MUST exit 3 with `FEN-3004` and the tool's sanitised line.
- **Source `fenolite`.** The netlist MUST be `sch_netlist.own_netlist` of the root sheet and of the child sheets it names, each read once with `read_schematic` and keyed by its path from the root file's folder, with no subprocess. A sheet file that is missing or outside that folder is not read, so its reference is a grammar issue. A sheet outside the grammar MUST exit 7 with `FEN-7001`, the grammar issues in `issues`, and a hint that names `--source kicad`.
- **Result.** `result` MUST hold `schematic` (the file name without its folder), `source`, `components` (each `ref`, `value`, `footprint`, `properties`), `nets` (each `name`, `class`, `unconnected`, `pins` as `{ref, pin, type}`) and `counts` (`components`, `nets`, `pins`, `unconnected`, `below_min_pins`). `unconnected` MUST be true for a net of one pin whose name starts with `unconnected-(`. Components MUST be sorted by natural order of the reference, nets by name, pins by reference and pin.
- **`--min-pins`.** Nets with fewer pins MUST be left out of `nets` and counted in `counts.below_min_pins`. The default MUST be 1; a value below 1 MUST exit 2 with `FEN-2001`.
- **Read-only and deterministic.** The project folder MUST be unchanged. The output MUST hold no date, no temporary path and no absolute path, and two runs MUST give the same stdout apart from `elapsed_ms`.
- **Evidence.** The envelope evidence MUST be that of the source: `Evidence.combine(netlist.EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>`, or `sch_netlist.EVIDENCE`.
- `example_args` MUST be `(EXAMPLE_SCHEMATIC,)`, with `fenolite.cli._examples.EXAMPLE_SCHEMATIC` the absolute path of `tests/data/kicad/schematic/flat.kicad_sch`, and `example_tools` MUST be `("kicad-cli",)`. `docs/cli-contract.md` MUST have a section "netlist". The fakes of the example suites MUST be given the authored `export_10.net` (`tests/_fakecli.py::EXAMPLE_NETLIST`), since a fake without a netlist refuses the schematic.

#### Scenario: Built blink through KiCad
- **GIVEN** a fake `kicad-cli` that writes the authored `export_10.net`
- **WHEN** `uv run pytest tests/unit/cli/test_netlist_cmd.py -k kicad` runs `fenolite netlist <project> --json`
- **THEN** the exit code is 0, `result.source` is `kicad`, `result.counts.components` is 3, the net `GND` lists `D1` pin `1` and `U1` pin `10`, and stdout holds no absolute path and no date

#### Scenario: Own reading without a tool
- **GIVEN** the blink built with a schematic into `tmp_path`, and `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `fenolite netlist <dir> --source fenolite --json` runs
- **THEN** the exit code is 0, `result.source` is `fenolite`, and `result.counts.unconnected` is 29

#### Scenario: Sheet outside the grammar
- **WHEN** `fenolite netlist tests/data/kicad/schematic/flat.kicad_sch --source fenolite --json` runs
- **THEN** the exit code is 7, stderr carries `FEN-7001`, the envelope's `issues` hold `kicad.sch.netlist-unsupported`, and the hint names `--source kicad`

#### Scenario: Small nets left out
- **WHEN** `fenolite netlist <dir> --source fenolite --min-pins 2 --json` runs on the built blink
- **THEN** `result.nets` holds `GND`, `LED_A` and `LED_DRV`, and `result.counts.below_min_pins` is 30

#### Scenario: Both sources agree
- **WHEN** `uv run pytest tests/kicad/check/test_netlist_oracle.py -k command` runs both sources on the built blink on 9.0.9 and on 10.0.6
- **THEN** the two `result.nets` are equal apart from `class`

#### Scenario: No schematic
- **WHEN** `fenolite netlist tests/data/kicad/board/two_layer.kicad_pcb` runs
- **THEN** the exit code is 3 and stderr carries `FEN-3001`

#### Scenario: Example runs against the fake
- **WHEN** `uv run pytest tests/consistency -k netlist` runs
- **THEN** `netlist`'s `example_args` exit 0 with a valid envelope

#### Scenario: Own reading of module sheets
- **GIVEN** the design of "Two modules, one nested" built into `tmp_path`
- **WHEN** `fenolite netlist <dir> --source fenolite --json` runs
- **THEN** the exit code is 0 and `result.components` lists `U1`, `R1`, `C1` and `R2`
