# python-api Specification

## Purpose
`fenolite.api` runs every command in process with the envelope of `--json`, and gives typed reads of designs and boards and the board analyses, so that a Python program uses Fenolite without a subprocess; the surface is documented in `docs/api.md`.

## Requirements

### Requirement: In-process command runner
`fenolite.api.run(command, *args, cwd=None, seed=None, timestamp=None)` SHALL run the command through the dispatcher of `fenolite` and return a `Reply` whose `exit_code`, `envelope` and `error` are what `fenolite COMMAND ARGS --json` exits with and prints.
- It MUST NOT print, install a signal handler or change the process's working folder.
- `cwd` MUST be the command's working folder.

#### Scenario: Same envelope as the command line
- **GIVEN** every registered command and its `example_args`, with the same seed and timestamp
- **WHEN** `uv run pytest tests/consistency/test_api_run.py -k matches` runs each through `main` and through `run` from another folder
- **THEN** the exit codes, the error objects and the envelopes but `elapsed_ms` are equal, and `run` printed nothing

#### Scenario: Nothing printed
- **WHEN** `uv run pytest tests/unit/api/test_run_api.py -k "read_only or signal"` runs `inspect` and a writing command
- **THEN** file descriptors 1 and 2 hold nothing, and the signal handlers and the working folder are those of before

### Requirement: Mutation protocol in process
A writing command run by `fenolite.api.run` SHALL keep the mutation protocol: without `--confirm` it MUST write nothing (exit 4, or 0 with `--dry-run`), and `--confirm --plan ID` MUST write the reviewed plan under `cwd` only, with its receipt. A plan id MUST name the same staged plan for `run` and for `fenolite` in the same folder.

#### Scenario: Plan, review, write
- **GIVEN** every writing command's `mutation_example_args` and an empty folder the process stands in
- **WHEN** `uv run pytest tests/consistency/test_api_run.py -k "protocol or plan_made"` plans, dry-runs and confirms each with `run`
- **THEN** the folder is unchanged until `--confirm --plan`, the receipt lists the planned files with their digests, nothing lands elsewhere, and `fenolite` writes a plan `run` made

### Requirement: In-process limits
`fenolite.api.run` SHALL refuse with `FEN-2001` (exit 2) `--help` and its abbreviations, `--text`, `restore -` before any read of stdin, and `view --serve` before serving. A `command` that is not a command name, or a keyword given also as its flag, MUST raise `ValueError`, and an argument that is not a `str` MUST raise `TypeError`.

#### Scenario: Terminal-only forms refused
- **WHEN** `uv run pytest tests/unit/api/test_run_api.py -k "help or serve or faults"` runs
- **THEN** each form exits 2 with `FEN-2001` and prints nothing, no stdin is read, and the Python faults raise

### Requirement: Typed design and board reads
`fenolite.api.read_design(path)` SHALL return the `ReadSide` that `equivalent` reads, and `read_board(path)` a frozen `Board` (name, SHA-256, backend, design, board-frame pads, warnings, evidence) of a board file, KiCad project file or folder. A missing path MUST raise `SideMissingError`, and a file that is not a board `SideUsageError`. Neither MUST write a file or start a process.

#### Scenario: Records, not dictionaries
- **WHEN** `uv run pytest tests/unit/api/test_board_api.py -k "read or hermetic"` reads the two-layer board, its folder and a text file
- **THEN** a `Board` and a `ReadSide` with the board's digest come back, the text file raises `SideUsageError`, and no process ran

### Requirement: Typed board analyses
`fenolite.api.connectivity`, `analyze_current` and `analyze_distances` SHALL take a `Board` or a path and return the `ConnectivityReport` or `AnalysisReport` of `fenolite.analysis`, measured with the defaults of `fenolite analyze`. `requirements` MAY be a path of a TOML file. Overlapping cut-outs without the `geo` extra MUST raise `ExtraMissingError` (`FEN-6001`).

#### Scenario: Same measures as analyze
- **WHEN** `uv run pytest tests/unit/api/test_board_api.py -k "command or connectivity or geo"` runs the calls and `fenolite analyze` on the two-layer board
- **THEN** the rows equal the command's rows in order, the connectivity equals the analysis on the board-frame pads, and the overlap raises `ExtraMissingError`

### Requirement: API reference page
`docs/api.md` SHALL list every name of `fenolite.api.__all__` with its signature or fields and say that each is frozen for 1.0.

#### Scenario: Every public name documented
- **WHEN** `uv run pytest tests/unit/api/test_run_api.py -k page` runs
- **THEN** every name of `fenolite.api.__all__` appears on `docs/api.md`
