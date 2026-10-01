# kicad-oracle Specification

## Purpose
Use `kicad-cli` 9.0 and 10.0 as external oracles: pinned Docker images, an isolated environment per run, per-kind load checks, and the token fuzz harness whose committed results prove each inventory row on each major. Facts and sources: `docs/formats/kicad/versions.md`.
## Requirements
### Requirement: Load check per file kind
`tools/kicad_token_fuzz.py` SHALL decide whether `kicad-cli` loads a case file with one command per kind, and SHALL record the outcome `load`, `reject`, `timeout` or `inconclusive`:

| kind | command | outcome `load` when |
|---|---|---|
| board | `pcb export svg <file> -l Edge.Cuts --mode-single -o <out>.svg` | exit 0 and the SVG exists |
| footprint | `fp export svg <dir>.pretty -o <existing dir>` | exit 0 and an SVG exists |
| worksheet | `pcb export svg <skeleton board> --drawing-sheet <file> …` | exit 0 and the output lacks `Error loading drawing sheet` |
| rules | `pcb drc --format json -o <r>.json` on the canary board with `canary.kicad_pro` and the rules file | the canary violation is present in the JSON report |

Any other result SHALL be `reject`. The harness MUST NOT pass `--exit-code-violations`. A worksheet or rules case SHALL be `inconclusive` when its own positive control did not load in the same run. The canary board SHALL be a 9.0-format board (header `20241229`) with the numbered net table and two tracks on nets 1 and 2, and its clearance rule SHALL use a value with a unit (`3mm`).

#### Scenario: Board rejected with exit 3
- **GIVEN** a board case containing an invented top-level token
- **WHEN** the harness runs it on `kicad-cli` 10.0.6
- **THEN** the outcome is `reject` and `exit_code` is `3`

#### Scenario: Footprint library failure
- **GIVEN** a footprint case with an invented token inside a pad
- **WHEN** the harness runs it
- **THEN** the outcome is `reject` and `exit_code` is `2`

#### Scenario: Missing SVG is not a load
- **GIVEN** a footprint run that exits 0 but writes no SVG
- **WHEN** the harness classifies it
- **THEN** the outcome is `reject`

#### Scenario: Silently disabled rules detected
- **GIVEN** a rules case whose file contains the canary rule and a rule with an invented constraint type
- **WHEN** the harness runs it and the DRC report lacks the canary violation
- **THEN** the outcome is `reject`, although `kicad-cli` exited 0

#### Scenario: Worksheet error detected from the message
- **GIVEN** a worksheet case containing an invented token
- **WHEN** `kicad-cli` exits 0 and prints `Error loading drawing sheet`
- **THEN** the outcome is `reject`

### Requirement: Isolation and time limits
Each case SHALL run in a fresh temporary directory holding only the case files, because `kicad-cli` writes a `.kicad_prl` next to a board. The harness MUST NOT write inside the repository except to the results directory given with `--write`. Every `kicad-cli` invocation SHALL have a timeout (default 120 s); a timed-out invocation yields outcome `timeout`, which never matches an expectation.

In every mode the harness SHALL run `kicad-cli` with `KICAD_CONFIG_HOME` set to an empty directory under the run's temporary directory, `LANG=C` and `LC_ALL=C`, and SHALL record these variables in the results header, so that the user's language, default drawing sheet and settings cannot change an outcome.

#### Scenario: Repository untouched
- **GIVEN** a clean working tree and committed results for the local `kicad-cli`
- **WHEN** `uv run python tools/kicad_token_fuzz.py --check docs/evidence/kicad/token-fuzz` runs
- **THEN** `git status --porcelain` is unchanged afterwards

#### Scenario: Hung process
- **GIVEN** a fake `kicad-cli` that sleeps longer than `--timeout 1`
- **WHEN** a case runs
- **THEN** the outcome is `timeout` and the harness exits 5

#### Scenario: Isolated environment passed to the runner
- **GIVEN** a fake runner that records its environment, and a caller environment with `LANG=de_DE.UTF-8`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_fuzz_harness.py -k env` runs a case
- **THEN** the recorded environment has `LANG=C`, `LC_ALL=C` and a `KICAD_CONFIG_HOME` inside the run's temporary directory, and the results header lists the three variables

### Requirement: Execution modes
The harness SHALL accept `--kicad-cli PATH`. When no path is given, it SHALL use `FENOLITE_KICAD_CLI`, then `kicad-cli` on `PATH`, then the macOS application bundle path. With `--docker IMAGE`, it SHALL re-run itself inside that image, passing the same arguments, with:
- the repository mounted at `/w` and `PYTHONPATH=/w/src`;
- `HOME=/tmp`;
- the invoking user's uid and gid.

It SHALL identify the binary with `kicad-cli version`, SHALL name the results file after the first line of that output restricted to `[0-9A-Za-z.+-]`, and SHALL record the version, the image reference (with digest when given) and the platform in the results. It MUST exit 6 when no usable `kicad-cli` is found, 5 when any outcome differs from its expectation or from the committed results under `--check`, 2 on usage errors, and 0 otherwise.

#### Scenario: No kicad-cli
- **GIVEN** no `kicad-cli` on the machine and no `--docker`
- **WHEN** the harness runs
- **THEN** it exits 6 and prints how to install KiCad or use `--docker`

#### Scenario: Docker mode
- **GIVEN** `--docker kicad/kicad:9.0.9@sha256:<digest>` and an image whose `kicad-cli version` prints `9.0.9`
- **WHEN** the harness runs with `--write <dir>`
- **THEN** it writes `<dir>/9.0.9.json` whose `kicad_cli.image` equals the given reference

#### Scenario: Results drift
- **GIVEN** a committed results file in which one case has outcome `load`
- **WHEN** a fresh run with `--check` yields `reject` for that case
- **THEN** the harness exits 5 naming the example and both outcomes

#### Scenario: Unexpected load reported by a fake runner
- **GIVEN** a fake runner that returns `load` for a case whose expected outcome on 9.0 is `reject`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_fuzz_harness.py -k mismatch` runs the harness with `--write`
- **THEN** the harness exits 5 naming the example

### Requirement: Sanitised results
Recorded `detail` text SHALL be the first line of `kicad-cli` output, with the temporary directory replaced by `<tmp>` and any home directory replaced by `~`. Results files MUST pass the residue scan.

#### Scenario: Temporary path removed
- **GIVEN** `kicad-cli` output naming `/tmp/fuzz-abc123/case.kicad_pcb`
- **WHEN** the case is recorded
- **THEN** `detail` contains `<tmp>/case.kicad_pcb` and no absolute path

### Requirement: Major-aware oracle tests
`tests/_resources.py` SHALL provide `kicad_cli_version()`, returning the running `kicad-cli` version as `(major, minor, patch)` or `None`. The marker `kicad_min_major(N)`, registered in `pyproject.toml`, SHALL skip a test when the running major is below `N`, with a reason naming both majors. Required-resource mode (`FENOLITE_REQUIRE`) MUST NOT turn this skip into a failure.

Every test under `tests/kicad/` that runs `pcb upgrade`, `sch upgrade` or `pcb import`, or loads a 10.0-format fixture unchanged, MUST carry `kicad_min_major(10)`. c0006's `test_escapes_after_upgrade`, `test_resave_equal` and `test_byte_identity_kicad10` SHALL carry it. c0006's `test_lexical_mirror` and `test_number_spellings` SHALL instead rewrite each fixture's header to `FORMAT_VERSIONS[FileKind.BOARD][major]` of the running major in `tmp_path` before loading, leaving fixtures without a header unchanged.

#### Scenario: Older major skips cleanly in required mode
- **GIVEN** `FENOLITE_REQUIRE=kicad` and a fake `kicad-cli` whose `version` prints `9.0.9`
- **WHEN** a test marked `kicad_min_major(10)` runs under `pytester`
- **THEN** it is skipped with a reason naming 10 and 9, and the run exits 0

#### Scenario: c0006 oracle tests on 9.0
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image
- **WHEN** `uv run pytest tests/kicad/test_sexpr_oracle.py` runs
- **THEN** `test_escapes_after_upgrade` is skipped, and `test_lexical_mirror` loads each fixture with header `20241229`

### Requirement: Environment facts are tested
`tests/kicad/test_environment.py` (marker `needs_kicad`) SHALL settle, and `docs/hypotheses.md` SHALL record with result and date:
- `H-K-00`: `kicad-cli pcb --help` lists `import` when the major is 10 and does not when it is 9;
- `H-K-01`: `kicad-cli pcb drc --help` lists `--refill-zones` and `--save-board` when the major is 10 and neither when it is 9;
- `H-K-02`: in the pinned `kicad/kicad` 9.0.9 and 10.0.6 images, `kicad-cli version` exits 0 and prints a parseable version, whose exact first line is recorded, and the positive baseline exports an SVG;
- `H-K-03`: pads with `(padstack (mode front_inner_back) …)` and `(padstack (mode custom) …)` load on both majors, which the committed fuzz results settle.

#### Scenario: Import command on 10.0
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/test_environment.py -k import` runs
- **THEN** it passes because `import` is listed

#### Scenario: Refill option absent on 9.0
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image
- **WHEN** `uv run pytest tests/kicad/test_environment.py -k refill` runs
- **THEN** it passes because neither `--refill-zones` nor `--save-board` is listed

#### Scenario: Unexpected help text
- **GIVEN** a `kicad-cli` 9.0.x whose `pcb drc --help` lists `--refill-zones`
- **WHEN** the test runs
- **THEN** it fails stating that `H-K-01` must be updated and the zone-fill approach revisited

### Requirement: Version constants confirmed by kicad-cli
`tests/kicad/test_version_constants.py` (marker `needs_kicad`) SHALL upgrade authored 8.0-format files and compare each written header with `FORMAT_VERSIONS` for the running major:
- `fp upgrade --force` and `sym upgrade --force` on both majors;
- `pcb upgrade --force` and `sch upgrade --force`, marked `kicad_min_major(10)`.

It SHALL check that a worksheet with the worksheet constant loads, and that the same worksheet with the constant plus one is reported as created by a newer version. A test also marked `needs_corpus` and `kicad_min_major(10)` SHALL check that 10.0 loads the corpus demo boards with versions `20250513` and `20250907` (`H-K-TOK-DEV`); the `20241030` mapping is settled by the `dev-header-9` control on both majors.

#### Scenario: Footprint constant on 9.0
- **GIVEN** `kicad-cli` 9.0.9 and the authored footprint with header `20240108`
- **WHEN** `fp upgrade --force` rewrites it
- **THEN** the written header equals `FORMAT_VERSIONS[FileKind.FOOTPRINT][9]`

#### Scenario: Board upgrade skipped on 9.0
- **GIVEN** `kicad-cli` 9.0.9, which has no `pcb upgrade`
- **WHEN** `uv run pytest tests/kicad/test_version_constants.py -k board` runs with `FENOLITE_REQUIRE=kicad`
- **THEN** the board test is skipped, not failed

#### Scenario: Constant mismatch
- **GIVEN** a `kicad-cli` whose `sym upgrade` writes a header different from the constant for its major
- **WHEN** the test runs
- **THEN** it fails naming the kind, the major, the constant and the written value

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
- **Upgraded copies** (`test_board_upgraded.py`, `kicad_min_major(10)`, `needs_corpus`). The upgrade set is the 16 non-heavy 10.0.6 demos and the 3 third-party boards. Their `pcb upgrade --force` copies MUST read with no error issue from `read_board` and pass RT1. For each of the 16 demos, every `uuid` of the original that the copy keeps MUST stay on the same kind of item; a `uuid` that disappears MUST belong to a teardrop zone, a footprint's `Footprint` property or an `fp_text` item, and a new `uuid` MUST be on a property (`H-K-UUID-KEEP-2`, demo half; 10.0.6 removes teardrop zones and `Footprint` properties and replaces `fp_text` items on re-save, which refuted `H-K-UUID-KEEP`). The census of the third-party copies counts as origin `third-party`.

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

#### Scenario: uuids of kept items survive a KiCad re-save
- **GIVEN** `kicad-cli` 10.0.6 and the fetched corpus
- **WHEN** `uv run pytest tests/kicad/board/test_board_upgraded.py -k uuid_keep` runs
- **THEN** for each demo, every uuid missing from the upgraded copy belonged to a teardrop zone, a `Footprint` property or an `fp_text` item, every new uuid is on a property, and no kept uuid changes kind; otherwise the test fails naming the board and the first uuid that breaks the rule

#### Scenario: Wrong model detected
- **GIVEN** a model of the authored board in which `D1.rotation` was changed to 0
- **WHEN** the pad comparison runs against the board's IPC-D-356 export
- **THEN** it fails naming `D1` pin 2

