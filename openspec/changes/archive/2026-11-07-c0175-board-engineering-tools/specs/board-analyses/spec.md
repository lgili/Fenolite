## MODIFIED Requirements

### Requirement: Analyze command
`fenolite analyze PATH` SHALL be a read-only command (`mutates` false, schema `fenolite.analyze.v0`) in `src/fenolite/cli/cmd_analyze.py`. `PATH` is a board file that a registered backend reads (`backends.registry.for_path`); an Altium board needs no option of its own once a backend reads it.
- Options: `--kinds current,clearance,creepage` (default: all three; on request also `power`, `insulation`, `length`, `ties`, `domains`, `crossings`, `decoupling`, `connectivity`, `bodies`, `relief`, `necks`, `loops`, `balance`, `dead` and `coupling`); `--requirements FILE`; `--temp-rise KELVIN` (a decimal number of at most three decimals); `--copper-thickness LENGTH` and `--copper-thickness LAYER=LENGTH` (repeatable); `--via-plating LENGTH`; `--board-thickness LENGTH`; `--pair NET_A NET_B` (repeatable); `--within LENGTH`; `--arc-tol LENGTH`; and the options of the kinds that need them: `--tie REF`, `--tie-item ID`, `--domains A=GLOB,B=GLOB`, `--sense NET_A,NET_B`, `--barrier REFS`, `--cut X1,Y1,X2,Y2`, `--width LENGTH`, `--render FILE`, `--dead-distance LENGTH`, `--aggressor GLOB` and `--victim GLOB`. Lengths are parsed by `core.units.parse_length` and need a unit.
- Pads MUST come from the backend that read the file when it satisfies c0028's `BoardFrame`; otherwise `pads` is `None`.
- `result` MUST hold `current` and `distances` (the rows of the selected kinds, as JSON objects with the field names of the records), one key per other selected kind holding its rows, `summary`, and `inputs` (the option values in force and `boundary.source`). The rows of `clearance` and `creepage` come from one `analyze_distances` call; an unselected kind is left out of each row.
- The issues of the reports MUST be the envelope's `issues`. An issue of severity `error` gives exit code 5, as "Exit-code vocabulary" says of findings. An unknown kind, a malformed option, `--pair` with one name, or an option of a kind that is not selected MUST be a usage error (`FEN-2001`, exit 2). An unreadable requirements file MUST be `FEN-3004`, exit 3.
- The command MUST run no external tool. It MUST write no file, except the drawing of `--render`, which follows the mutation protocol. `docs/cli-contract.md` MUST document it under the heading `analyze`, with every code.

#### Scenario: Capacity of the example board
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_cmd.py -k example` runs `fenolite analyze tests/data/kicad/board/two_layer.kicad_pcb --kinds current --temp-rise 10 --copper-thickness 35um --json`
- **THEN** the exit code is 0, `result.current` holds one row per track and arc of the board, each `capacity_ma` an integer, and `evidence.level` is `INFERRED` or `UNVERIFIED`

#### Scenario: Requirement not met exits 5
- **GIVEN** an authored board in `tmp_path` with the slot of "Around a slot" and a requirements file asking 12 mm of creepage
- **WHEN** `fenolite analyze <board> --kinds creepage --requirements <file> --json` runs
- **THEN** the exit code is 5 and `issues` holds one `analysis.creepage-below` error

#### Scenario: Read-only and hermetic
- **GIVEN** `subprocess.run` patched to raise and a snapshot of the folder of the board
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_cmd.py -k readonly` runs the command for every kind except with `--render`
- **THEN** it succeeds and the folder is unchanged

#### Scenario: Usage error
- **WHEN** `fenolite analyze <board> --kinds thermal` runs, and `fenolite analyze <board> --kinds current --cut 0mm,0mm,1mm,1mm` runs
- **THEN** each exit code is 2 and stderr holds `FEN-2001`
