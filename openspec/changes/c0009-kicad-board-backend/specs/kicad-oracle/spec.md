## ADDED Requirements

### Requirement: Package kicad-cli runner
`fenolite.backends.kicad.cli` SHALL be the only `kicad-cli` runner in `src`. Every oracle test added from this change on, and every later command, MUST use it. `tools/kicad_token_fuzz.py` keeps its own runner.
- **Finding the binary.** `find_kicad_cli(explicit=None)` MUST try, in order: the explicit path, `FENOLITE_KICAD_CLI`, `kicad-cli` on `PATH`, and the macOS application bundle. It MUST return `None` when the explicit path or `FENOLITE_KICAD_CLI` names a missing file. `cli/cmd_capabilities.py` and `tests/_resources.kicad_cli()` MUST use it.
- **Fresh directory.** `KicadCli.run(args, *, files, env=None)` MUST copy each `files` entry (relative name → file or folder) into a fresh temporary directory, and MUST run `kicad-cli` there with that directory as working directory. It MUST NOT open the caller's files for writing.
- **Environment.** The caller's environment MUST be passed without variables whose names start with `KICAD`, and with `KICAD_CONFIG_HOME` set to an empty folder inside the temporary directory, `LANG=C`, `LC_ALL=C` and the explicit `env` entries.
- **Timeout.** A run that exceeds `timeout` (default 120 s) MUST be killed and give `CliRun.outcome == "timeout"` with `returncode is None`.
- **Result.** `CliRun.outputs` MUST map the relative name of every file the run created or changed (a copy whose SHA-256 differs after the run), other than the configuration folder, to its bytes. The temporary directory MUST be removed afterwards.
- **Sanitising.** In `stdout` and `stderr`, the temporary path MUST be replaced by `<tmp>` and the home directory by `~`.
- **Helpers.** `load_board_svg`, `export_pos_csv`, `export_ipcd356` and `upgrade_board` MUST raise `KicadCliError` on a non-zero exit or a timeout. `upgrade_board` MUST raise `KicadCliVersionError` (`FEN-6002`) when the major is 9. It MUST return the re-saved copy from `outputs`, or the copy's unchanged bytes when the re-save leaves them byte-identical, as `pcb upgrade --force` does for a board already at the current format.

#### Scenario: Isolated environment
- **GIVEN** a fake `kicad-cli` script that records its environment and working directory, and a caller environment with `LANG=de_DE.UTF-8` and `KICAD10_FOOTPRINT_DIR=/x`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_cli_runner.py -k env` runs a command
- **THEN** the recorded environment has `LANG=C`, `LC_ALL=C`, a `KICAD_CONFIG_HOME` inside the run's temporary directory and no `KICAD10_FOOTPRINT_DIR`, and the working directory is the temporary directory

#### Scenario: Source folder unchanged
- **GIVEN** a folder holding a board, and a fake `kicad-cli` that writes `x.kicad_prl` and an output next to its input
- **WHEN** `run` copies the board and the fake runs
- **THEN** the SHA-256 of every file in the source folder is unchanged, no file was added to it, and `outputs` holds the two created files

#### Scenario: Input changed in place
- **GIVEN** a fake `kicad-cli` that rewrites its input board in place, as `pcb upgrade --force` does
- **WHEN** `run` copies the board as `b.kicad_pcb` and the fake runs
- **THEN** `outputs["b.kicad_pcb"]` holds the rewritten bytes, and the caller's board is unchanged by SHA-256

#### Scenario: Timeout
- **GIVEN** a fake `kicad-cli` that sleeps longer than `timeout=1`
- **WHEN** `run` is called
- **THEN** `outcome == "timeout"`, `returncode is None`, and the temporary directory no longer exists

#### Scenario: Sanitised output
- **GIVEN** a fake `kicad-cli` that prints the absolute path of its input and the home directory
- **WHEN** `run` returns
- **THEN** `stdout` contains `<tmp>/` and `~` and no absolute path of the machine

#### Scenario: Missing override
- **GIVEN** `FENOLITE_KICAD_CLI` naming a file that does not exist
- **WHEN** `find_kicad_cli()` is called
- **THEN** it returns `None`, although `kicad-cli` may be on `PATH`

#### Scenario: Unchanged re-save
- **GIVEN** a fake `kicad-cli` whose `pcb upgrade --force` exits 0 and leaves its input unchanged
- **WHEN** `KicadCli(path).upgrade_board(board)` is called
- **THEN** it returns the bytes of `board`, and the run's `outputs` holds no entry for the copy

#### Scenario: Upgrade refused on KiCad 9
- **GIVEN** a fake `kicad-cli` whose `version` prints `9.0.9`
- **WHEN** `KicadCli(path).upgrade_board(board)` is called
- **THEN** `KicadCliVersionError` is raised with `cli_code == "FEN-6002"`, and `kicad-cli` is not run with `pcb upgrade`

### Requirement: Typed board reads agree with kicad-cli exports
`tests/kicad/board/` SHALL confirm the typed board reader against KiCad's own exports, through the package runner:
- **Placements** (`test_board_frame.py::test_pos`). Each row of `pcb export pos --format csv --side both --units mm` MUST match a footprint of the model by reference: x equal to `PosX` and y equal to minus `PosY` at the printed precision, side, and rotation modulo 360° on both sides. Duplicate references are compared as multisets, and footprints with `exclude_from_pos_files` are skipped. Bottom rotations are also recorded as data for `H-G-FLIP`. The export frame (origin, Y direction, units, angle range) is a fact of `docs/formats/kicad/board.md`.
- **Pads** (`test_board_frame.py::test_ipcd356`). The `317` and `327` records of `pcb export ipcd356` are compared with the model's pads:
  - Via records (`ref == "VIA"`) MUST be skipped and counted.
  - Every other record MUST match a model pad on the key (reference cut to 6 characters, pad number cut to 4), as the export truncates both. When several records or pads share a key, each record MUST match a distinct pad of that key, the nearest one within the bound.
  - Positions MUST be compared relative to a reference pad, the first record whose key is unique in the export and in the model: each record's offset from it MUST equal the model's within ±2 export units per axis.
  - Pads that the export puts on one net MUST be on one model net, and the reverse.
  - The counts of via records, truncated keys and ambiguous keys are recorded for the census. `R` fields are recorded and not asserted.
- **Loads** (`test_board_loads.py`). `rebuild_board` output MUST load with `KicadCli.load_board_svg`.
- **Upgraded copies** (`test_board_upgraded.py`, `kicad_min_major(10)`, `needs_corpus`). The upgrade set is the 16 non-heavy 10.0.6 demos and the 3 third-party boards. Their `pcb upgrade --force` copies MUST read with no error issue from `read_board` and pass RT1. For each of the 16 demos, the unmasked `uuid` multiset of the copy MUST equal that of the original (`H-K-UUID-KEEP`, demo half). The census of the third-party copies counts as origin `third-party`.

Coverage MUST be:
- the 21 readable non-heavy demo boards (tags 10.0.6 and 9.0.9.1) on `kicad-cli` 10.0.6 (local and `kicad-10`);
- the authored board `tests/data/kicad/board/two_layer.kicad_pcb` on 10.0.6 and on 9.0.9 (`kicad-9`, which fetches no corpus).

#### Scenario: Placements of the authored board on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the `kicad-9` job
- **WHEN** `uv run pytest tests/kicad/board/test_board_frame.py -k "pos and fixture"` runs
- **THEN** `R1` is on top at (20 mm, 15 mm) with rotation 90, and `D1` is on the bottom at (35 mm, 15 mm) with rotation 30 modulo 360

#### Scenario: Pads of the demo boards on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6 and the fetched corpus
- **WHEN** `uv run pytest tests/kicad/board/test_board_frame.py -k ipcd356` runs
- **THEN** every non-via record of each of the 21 readable non-heavy demos matches a distinct model pad within the bound, the net partitions are equal, and the via, truncated-key and ambiguous-key counts are recorded

#### Scenario: Rebuilt boards load
- **GIVEN** `kicad-cli` 10.0.6 and the fetched corpus
- **WHEN** `uv run pytest tests/kicad/board/test_board_loads.py` runs
- **THEN** `load_board_svg` exits 0 for the rebuild of each of the 21 readable non-heavy demo boards and of the authored board

#### Scenario: uuids survive a KiCad re-save
- **GIVEN** `kicad-cli` 10.0.6 and the fetched corpus
- **WHEN** `uv run pytest tests/kicad/board/test_board_upgraded.py -k uuid_keep` runs
- **THEN** each demo's `uuid` multiset equals its upgraded copy's, or the test fails naming the board and the first differing uuid

#### Scenario: Wrong model detected
- **GIVEN** a model of the authored board in which `D1.rotation` was changed to 0
- **WHEN** the pad comparison runs against the board's IPC-D-356 export
- **THEN** it fails naming `D1` pin 2
