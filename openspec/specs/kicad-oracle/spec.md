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

### Requirement: Written boards load and count on both majors
`tests/kicad/board/test_triad.py` (markers `needs_kicad`, major-aware) SHALL write the triad of `tests/kicad/board/_triad.py` with `write_board` and check it with the running `kicad-cli`. Every run MUST go through c0009's package runner on a copy in `tmp_path`, with a `{}` project file next to the board, passed through the `files` argument that this change adds to every `KicadCli` helper, and an empty `KICAD_CONFIG_HOME`.
- **Emit check.** Before any `kicad-cli` run, `check_emittable` on the parsed target-9 and target-10 texts, each with its own target, MUST return no issue.
- **Load.** On 9.0.9 the target-9 text, and on 10.0.6 the target-10 text, MUST load with `KicadCli.load_board_svg`.
- **Report.** `read_drc_report` MUST parse the DRC report of each loaded triad.
- **Placements.** `pcb export pos --format csv --side both` MUST list 3 footprints whose references, positions, rotations and sides equal the model, compared through c0009's pos comparison.
- **Counts.** On 10.0.6, the footprint and pad counts of `pcb export stats --format json` MUST equal the model's.
- **Negative control.** On 9.0.9, loading the target-10 text MUST exit 3.
- **Created heads.** The created test board `tests/_boards.py::created_board(4)`, which holds one created entity of every `CANONICAL_ORDER` head, every name of `pcb.FLOOR_HEADS` and the 4-copper layer table, MUST pass the emit check and load: the target-9 text on 9.0.9 and the target-10 text on 10.0.6 (probe ids `pcb-write-heads-9` and `pcb-write-heads-10`).

`tests/kicad/board/test_net_forms.py` SHALL write the triad and `tests/data/kicad/board/two_layer.kicad_pcb` for each target the running major loads. Each text MUST load, and the net partition of `pcb export ipcd356` MUST equal the model's nets (`H-K-TOK-NETNAME`, `H-K-TOK-OBSOLETE`).

`tests/kicad/board/test_genver.py::test_generator_version_variants` SHALL load the triad texts with `generator_version` absent, `"9.0"`, `"10.0"` and `"fenolite-x"`: the target-9 text on both majors and the target-10 text on 10.0.6. Each outcome MUST be recorded under a `pcb-genver-*` probe id (`H-K-GENVER`). The emitted value `"<target>.0"` MUST load.

#### Scenario: Triad on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_triad.py` runs
- **THEN** the target-10 triad and the target-10 created test board load, pos lists `R1` top at 0°, `D1` bottom at 90° and `U1` top at 30° at the model's positions, and `pcb export stats` counts 3 footprints and the model's number of pads

#### Scenario: Triad on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the `kicad-9` job
- **WHEN** `uv run pytest tests/kicad/board/test_triad.py` runs
- **THEN** the target-9 triad and the target-9 created test board load, the triad's pos rows equal the model, and loading the target-10 triad text exits 3

#### Scenario: Authored board in both net forms
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_net_forms.py` runs
- **THEN** `two_layer.kicad_pcb` written for target 9 and for target 10 loads, and each IPC-D-356 export puts `R1` pin 2 and `D1` pin 2 on one net, which the model calls `LED_A`

#### Scenario: Generator version variants recorded
- **GIVEN** `kicad-cli` 9.0.9
- **WHEN** `uv run pytest tests/kicad/board/test_genver.py` runs
- **THEN** the four variants of the target-9 text each record `load` or `reject` under their probe id, and the `"9.0"` variant records `load`

### Requirement: Placed footprints match their library definitions
`tests/kicad/board/test_flip_oracle.py` (markers `needs_kicad`, major-aware) SHALL check `place_footprint` against three independent `kicad-cli` outputs:
- **Bench.** `Mini_R_0603`, `Mini_LED_THT_3mm` and `Mini_QFP-32_7x7mm_P0.8mm` placed at 0°, 30°, 90° and 180° on the top and on the bottom: 24 placements on one board written for the running major in `tmp_path`. The folder holds a `{}` project file, a copy of `tests/data/libs/Mini.pretty` (10.0.6) or `tests/data/libs/Mini_v9.pretty` (9.0.9), and a project `fp-lib-table` whose row `Mini` points at `${KIPRJMOD}/<that folder>`. Every definition MUST be read with `read_footprint(path, library="Mini")` on both majors, so every placement is named `Mini:<name>`. `KICAD_CONFIG_HOME` MUST be empty.
- **Placements.** On both majors, the side and rotation that `pcb export pos --format csv --side both` gives for all 24 placements MUST equal the model (`test_flip_angle`).
- **Pads.** On both majors, every pad record of `pcb export ipcd356`, taken relative to the file's first record, MUST equal `at + R(θ)·stored` relative to that record's model pad within ±2 export units (±5 080 nm) per axis, through c0009's comparison in `tests/kicad/board/_frame.py` (`test_bottom_store`). No absolute bound is asserted, because the export origin is unknown. `R` fields are recorded and not asserted (`test_pad_angles`).
- **Library parity.** On 10.0.6, `pcb drc` MUST report no `lib_footprint_mismatch` for the 24 placements.
- **Negative controls.** Three boards, each with one bottom QFP at 30°: unmirrored bottom children; relative pad angles (θ not added); the footprint written at −θ with every child unchanged. On 10.0.6, each MUST give exactly one `lib_footprint_mismatch`.
- **Missing-table control.** On 10.0.6, an exact placement on a board without `fp-lib-table` MUST give `lib_footprint_issues` (`test_lib_drc`). When it does not, the run MUST be recorded `inconclusive` and the library-parity assertions MUST fail, never pass.
- **KiCad 9.0.** On 9.0.9, the DRC outcomes of the bench, the three controls and the missing-table control MUST be recorded under `pcb-libdrc-*` probe ids, `pcb-libdrc-missing-table` included, and MUST NOT fail the test (`H-K-LIB-DRC`).

Before any oracle uses them, the authored files `tests/data/libs/Mini_v9.pretty/Mini_LED_THT_3mm.kicad_mod` and `Mini_QFP-32_7x7mm_P0.8mm.kicad_mod` MUST pass c0008's `tests/kicad/libs/test_mini_oracle.py` on 9.0.9: they load, and they re-read equal after `fp upgrade --force`.

#### Scenario: Exact placements on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6 and the 24-placement bench
- **WHEN** `uv run pytest tests/kicad/board/test_flip_oracle.py` runs
- **THEN** the report holds no `lib_footprint_mismatch`, every pos row and IPC-D-356 pad matches the model, and each negative control gives exactly one `lib_footprint_mismatch`

#### Scenario: Unmirrored control detected
- **GIVEN** the bottom QFP at 30° written with its children not mirrored about local X
- **WHEN** DRC runs on 10.0.6
- **THEN** the report holds exactly one `lib_footprint_mismatch`, whose item uuid is that footprint's uuid

#### Scenario: Silent library table
- **GIVEN** `kicad-cli` 10.0.6 whose missing-table control reports no `lib_footprint_issues`
- **WHEN** the flip oracle runs
- **THEN** the outcome `inconclusive` is recorded for `pcb-libdrc-missing-table` and `test_lib_drc` fails with a message naming `H-K-LIB-DRC`

#### Scenario: Silent library table on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 whose missing-table control reports no `lib_footprint_issues`
- **WHEN** the flip oracle runs
- **THEN** the outcome is recorded under `pcb-libdrc-missing-table` and `test_lib_drc` does not fail

#### Scenario: Bottom pads on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the `kicad-9` job
- **WHEN** `uv run pytest tests/kicad/board/test_flip_oracle.py` runs
- **THEN** every IPC-D-356 pad of the 12 bottom placements, relative to the first record, lies within ±2 export units per axis of the model, and the DRC outcomes are recorded without failing the test

#### Scenario: Nine-format mini footprints
- **GIVEN** `kicad-cli` 9.0.9
- **WHEN** `uv run pytest tests/kicad/libs/test_mini_oracle.py` runs
- **THEN** `Mini_LED_THT_3mm` and `Mini_QFP-32_7x7mm_P0.8mm` of `Mini_v9.pretty` load and re-read equal after `fp upgrade --force`

### Requirement: DRC verdicts come from the JSON report
Every oracle test and every command that judges a DRC outcome SHALL read it from the JSON report, through `KicadCli.drc` and `read_drc_report`.
- `KicadCli.drc(board, *, files=None, env=None)` MUST run `pcb drc --format json --severity-all -o <out> <board>` through c0009's runner on a copy, and MUST NOT pass `--exit-code-violations`. `DrcRun.report` MUST be `None` when no report was written.
- `KicadCli.drc` MUST pass `env` unchanged to `KicadCli.run`. Its entries reach `kicad-cli` after the runner's own variables: an entry `KICAD_CONFIG_HOME` replaces the runner's empty configuration folder, and the caller's variables whose names start with `KICAD` are still dropped. With `env=None`, `kicad-cli` MUST get the runner's environment unchanged.
- The exit code of `pcb drc` MUST be used only as a load signal.
- A report without violations MUST NOT count as evidence that a library table, a project file or a custom rules file was loaded. Every such proof MUST carry a control that fires only when the file was loaded: the missing-table control here, the canary in the rules proofs.
- `tests/kicad/board/test_drc_report.py::test_drc_json_strict` MUST settle `H-K-DRC-JSON` on both majors: the report parses with `NaN` and `Infinity` rejected, holds the 7 required top-level keys, and `read_drc_report` accepts it. Whether `ignored_checks` is present MUST be recorded per major under the probe id `pcb-drc-ignored-checks`.

#### Scenario: Strict report on both majors
- **GIVEN** the triad written for the running major
- **WHEN** `uv run pytest tests/kicad/board/test_drc_report.py` runs on 9.0.9 and on 10.0.6
- **THEN** each report parses as strict JSON with `source`, `date`, `kicad_version`, `violations`, `unconnected_items`, `schematic_parity` and `coordinate_units`, and `read_drc_report` returns a `DrcReport`

#### Scenario: Exit code is not a verdict
- **GIVEN** a fake `kicad-cli` that exits 0 and writes a report holding one `clearance` violation
- **WHEN** `KicadCli.drc` runs
- **THEN** the arguments hold no `--exit-code-violations`, and `run.report.of_type("clearance")` returns one violation

#### Scenario: No report written
- **GIVEN** a fake `kicad-cli` that exits 3 and writes no report
- **WHEN** `KicadCli.drc` runs
- **THEN** `run.report is None` and `run.run.returncode == 3`

#### Scenario: Extra files next to the board
- **GIVEN** a fake `kicad-cli` that lists its working directory
- **WHEN** `load_board_svg(board, files={"board.kicad_pro": pro, "fp-lib-table": table})` runs
- **THEN** the listing holds the board copy, `board.kicad_pro` and `fp-lib-table`, and the caller's files are unchanged

#### Scenario: Explicit environment entries reach kicad-cli
- **GIVEN** a fake `kicad-cli` that records its environment and writes a report holding one `clearance` violation, a caller environment with `KICAD9_FOOTPRINT_DIR=/caller`, and a folder `D` under `tmp_path`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_cli_runner.py -k drc_env` calls `KicadCli.drc(board, env={"KICAD_CONFIG_HOME": str(D), "KICAD10_FOOTPRINT_DIR": "/libs"})`, then `KicadCli.drc(board)`
- **THEN** the first run records `KICAD_CONFIG_HOME` equal to `D`, `KICAD10_FOOTPRINT_DIR=/libs`, `LANG=C` and no `KICAD9_FOOTPRINT_DIR`; the second records a `KICAD_CONFIG_HOME` inside the run's temporary directory and no `KICAD10_FOOTPRINT_DIR`; and both reports hold the `clearance` violation

### Requirement: Written boards keep read content
`tests/kicad/board/` SHALL prove on the running `kicad-cli` that writing a read board keeps its content:
- **9 → 10** (`test_cross_version.py`, `needs_corpus`, `kicad_min_major(10)`). Every non-heavy demo board whose header maps to major 9 is read and written for target 10. The text MUST load on 10.0.6. The comparison first removes from the source design's `kicad` bags every `Opaque` slot whose fragment is a whole node that a target-10 write removes: the root `(net 0 "")`, `(net 0)` references, and zone `net_name` and `filled_areas_thickness`. The `opaque_count` of the re-read MUST equal the source's count minus the number of slots removed. Its canonical JSON MUST equal the source's after that removal, apart from the board's header bag, net numbers and the fragments of `Opaque` slots, which net-form rewriting and obsolete rows may change inside. Every source fragment that holds no `net` node and no node of an `until_major = 9` row MUST have its digest among the re-read's `opaque_digests`. Same-target writes keep exact equality of `opaque_count`.
- **Refusals** (`test_cross_version.py`). The triad written for 10, read back and written for 9, MUST raise `DowngradeRefusedError`. `tests/data/kicad/tokens/old/old.kicad_pcb` MUST raise `LegacyEditRefusedError`.
- **Lossy embedding** (`test_cross_version.py`). `Mini_R_0603` read from `Mini.pretty` and placed for target 9 MUST raise `LossyWriteError`. With `allow_lossy=True` the write MUST succeed with one `kicad.board.dropped-too-new` warning, and the text MUST load on 9.0.9.
- **uuids** (`test_uuid_keep_written.py::test_uuid_keep_written`, `kicad_min_major(10)`). On 10.0.6, the written triad and its `pcb upgrade --force` copy MUST have equal unmasked `uuid` multisets (`H-K-UUID-KEEP`, Fenolite-written half).
- **Unknown child** (`test_unknown_child.py`). `tests/data/kicad/board/dimension.kicad_pcb` is read, one segment is moved in the model, and the board is written for 9 and for 10. The `dimension` node MUST reappear tree-equal to the source node, at its source index for target 9 and between the same neighbouring items for target 10, whose root has no net table. `opaque_count` MUST be equal for target 9, and equal to the source's count minus the slots removed as for the demos for target 10. Each text MUST load on its major.

#### Scenario: Demo boards converted to 10
- **GIVEN** `kicad-cli` 10.0.6 and the fetched corpus
- **WHEN** `uv run pytest tests/kicad/board/test_cross_version.py -k demos` runs
- **THEN** every major-9 demo written for target 10 loads and re-reads equal apart from header, net numbers and the removed slots, with `opaque_count` lowered by exactly the number of removed slots, or the test fails naming the board

#### Scenario: Written uuids survive a KiCad re-save
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_uuid_keep_written.py` runs
- **THEN** the unmasked `uuid` multiset of the written triad equals that of its upgraded copy

#### Scenario: Unknown child survives a write
- **GIVEN** `dimension.kicad_pcb` read, with one segment moved
- **WHEN** it is written for target 9 and loaded on 9.0.9
- **THEN** the text loads, the `dimension` node is at its source index and tree-equal to the source node, and `opaque_count` equals the source's

### Requirement: Probe results per kicad-cli version
`tests/kicad/_probes.py` SHALL define the closed mapping `PROBES` (probe id → probe function and the majors it runs on) and `run(probe_id) -> str`, memoised per test session. An outcome MUST be one of `load`, `reject`, `present`, `absent`, `equal`, `different`, `inconclusive` and `timeout`.
- Oracle tests MUST assert on `run(…)` rather than run a probe themselves.
- `tests/kicad/test_probe_results.py` MUST run every probe of the running major and compare the outcomes with `docs/evidence/kicad/probes/<version>.json`. `<version>` is the first line of `kicad-cli version` restricted to `[0-9A-Za-z.+-]`.
- With `FENOLITE_PROBES_WRITE=1`, the test MUST write that file instead of comparing.
- A missing file for the running version MUST fail the test with a message naming `FENOLITE_PROBES_WRITE`.
- The file MUST hold only the version, the probe ids and their outcomes, and MUST pass the residue scan.
- The `kicad-9` and `kicad-10` jobs MUST run the comparison in required mode.

#### Scenario: Drift detected
- **GIVEN** a committed `docs/evidence/kicad/probes/10.0.6.json` that records `absent` for `pcb-libdrc-missing-table`
- **WHEN** a run on 10.0.6 yields `present` for that probe
- **THEN** `uv run pytest tests/kicad/test_probe_results.py` fails naming the probe id and both outcomes

#### Scenario: Missing results file
- **GIVEN** a `kicad-cli` whose version has no file under `docs/evidence/kicad/probes/`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs without `FENOLITE_PROBES_WRITE`
- **THEN** it fails with a message naming `FENOLITE_PROBES_WRITE`

#### Scenario: Results regenerated
- **WHEN** `FENOLITE_PROBES_WRITE=1 uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** `docs/evidence/kicad/probes/10.0.6.json` holds one outcome per probe of major 10, and `uv run python tools/residue/scan.py` exits 0

### Requirement: Rules proofs carry a canary
Every oracle test that judges custom rules SHALL run `kicad-cli pcb drc` on a bench that carries the canary, and SHALL pass only when the canary violation is in the DRC JSON report. This covers `tests/kicad/rules/` and every later rules proof that reuses its bench.
- The canary rule MUST be the rule of `tests/data/kicad/tokens/canary/canary.kicad_dru`, read from that file and placed right after `(version 1)`, so that every later rule takes precedence over it. If `H-K-DRU-ORDER` finds that the earlier rule governs on a major, the canary MUST be placed last for that major instead.
- The bench MUST hold the canary pair: two 0.25 mm tracks on nets `CANARY_A` and `CANARY_B` on `F.Cu`, with centres 1 mm apart and at least 10 mm from other copper. The other rules of the bench MUST NOT match them.
- Probe pairs that no later rule governs MUST be more than 3 mm apart, so the canary alone never flags them.
- Benches MUST be built in the test through the model and c0017's `write_board` for the running major, with a `{}` project file next to the board. They MUST NOT be committed.
- DRC MUST run through c0017's `KicadCli.drc` on a copy, with an empty `KICAD_CONFIG_HOME`. It MUST NOT use `--exit-code-violations`. The report MUST be read with c0017's `read_drc_report`, and violations MUST be matched by type and item uuids. The canary violation is the `clearance` violation between the two canary tracks.
- A report without the canary violation MUST fail the test with a message saying the rules file was not loaded. It MUST NOT pass or skip.
- The negative control MUST copy `tests/data/kicad/rules/broken.kicad_dru` (the canary plus a single-quoted rule name) verbatim onto a bench and MUST observe exit 0 without the canary violation on 10.0.6, and on 9.0.9 while `H-K-DRU-QUOTE` holds there. `dru-broken-silent` MUST record the observed outcome on each major. If 9.0.9 loads that file, the 9.0.9 control MUST copy `tests/data/kicad/rules/ten_only.kicad_dru` verbatim instead, which 9.0.9 drops whole (`H-K-TOK-RULES-DRIFT`), and observe the same.
- Each outcome MUST be recorded with c0017's `_probes` helper under a `dru-*` probe id, using c0017's closed outcome set (`present` or `absent` for a violation, `load` or `reject` for a file), and `tests/kicad/test_probe_results.py` MUST compare it with `docs/evidence/kicad/probes/<version>.json` in both KiCad jobs.

#### Scenario: Canary present
- **GIVEN** a bench for the `net` op with a 5 mm rule on net `N1`, a probe pair `N1`/`N2` and a control pair `N3`/`N4`, both 4 mm apart, and the canary
- **WHEN** the test runs on 10.0.6
- **THEN** it passes only because the report holds the `N1`/`N2` violation, no `N3`/`N4` violation, and the canary violation

#### Scenario: Canary absent
- **GIVEN** a `DrcReport` without the canary violation, as DRC gives with exit 0 when KiCad drops the rules file (for example because a rule uses an invented constraint type)
- **WHEN** the hermetic `uv run pytest tests/kicad/rules/test_bench.py` passes that report to `_bench.require_canary`, the check every rules test runs
- **THEN** the call fails the test with a message saying the rules file was not loaded, and neither passes nor skips

#### Scenario: Silent disable reproduced
- **GIVEN** `tests/data/kicad/rules/broken.kicad_dru` copied verbatim onto a bench
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_dialect.py -k broken` runs on 9.0.9 and on 10.0.6
- **THEN** DRC exits 0, the report holds no canary violation, and the probe `dru-broken-silent` records `absent` (on 9.0.9 while `H-K-DRU-QUOTE` holds)

#### Scenario: Probe drift detected
- **GIVEN** a committed `docs/evidence/kicad/probes/10.0.6.json` in which `dru-order-forward` records the outcome `present`
- **WHEN** a run on 10.0.6 records `absent` for that probe
- **THEN** `uv run pytest tests/kicad/test_probe_results.py` fails naming `dru-order-forward` and both outcomes

#### Scenario: Benches never reach the repository
- **WHEN** `uv run pytest tests/kicad/rules -q` runs on the local KiCad 10.0.6
- **THEN** `git status --porcelain` is unchanged afterwards

### Requirement: Net-class rules are enforced by kicad-cli
`tests/kicad/project/test_netclass_drc.py` (marker `needs_kicad`) SHALL prove on the running `kicad-cli` that a net class written by Fenolite is enforced, and SHALL judge every case from the DRC JSON report read with c0017's `read_drc_report`, never from the exit code. A clean report MUST NOT count as evidence that the project or the rules were read.

The bench is built by `tests/_netclass_bench.py` through the model and written with `write_triad` as `bench.kicad_pcb`, `bench.kicad_pro` and `bench.kicad_dru`:
- F.Cu tracks 0.25 mm wide in rows at least 5 mm apart; each of `+3V3`, `SIG1`, `SIG10`, `Net-(R1-Pad1)`, `D[0]`, `IN+`, `VCC_3.3`, the decoys `Net-R1-Pad1`, `D0`, `INN` and `VCC_3V3`, and `SW1_A` runs beside its own `GND` track with a 1.0 mm gap;
- class HV with clearance 2 mm, assigned in the model to `+3V3` and `SIG1`, so that synthesis writes their exact-name patterns; every other row is in `Default`;
- the canary: a 3 mm clearance rule restricted by a `net` condition to `CANARY_A`, whose track runs 0.75 mm from a `CANARY_B` track, at least 10 mm from other copper. The canary is scoped because the unconditional canary of "Rules proofs carry a canary" would flag every 1.0 mm row.

A row's HV violation is a `clearance` violation whose items are that row's two tracks, and the canary violation is the `clearance` violation between the two canary tracks; both MUST be identified by item uuids. Every run MUST go through c0009's `KicadCli` on a temporary copy with an empty `KICAD_CONFIG_HOME`. On 10.0 the target-10 and target-9 sets run; on 9.0 the target-9 set runs, and the target-10 cases are skipped by `kicad_min_major(10)`.
- In every case, the no-project case included, a report without the canary violation MUST fail the test with a message saying the rules file was not loaded, and MUST NOT pass or skip. `kicad-cli` 9.0.9 and 10.0.6 read a `.kicad_dru` next to the board without a project file (measured by this change), so in the no-project case the canary proves that DRC ran the rules while the classes, which live only in the project file, are absent. The outcome MUST be computed by the pure function `judge(report, *, case, design)` of `tests/_netclass_bench.py`, and the failure raised by `assert_loaded(outcome, case)`, so that both are tested without KiCad.
- Each case MUST be a probe of `tests/kicad/_probes.py` with id `pro-<case>-t<target>`, and the tests MUST assert on `run(…)`. The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, so that `tests/kicad/test_probe_results.py` detects a change of behaviour in a later image.

#### Scenario: Full set
- **GIVEN** the bench set for the running major
- **WHEN** `uv run pytest tests/kicad/project/test_netclass_drc.py::test_full_set` runs
- **THEN** the report has the HV violation of `+3V3`, of `Net-(R1-Pad1)` and of `D[0]`, and the canary violation

#### Scenario: No project file
- **GIVEN** the same set without `bench.kicad_pro`
- **WHEN** `test_three_way` runs it
- **THEN** the report has no HV violation and has the canary violation

#### Scenario: Class removed
- **GIVEN** the set synthesised from the bench without class HV
- **WHEN** `test_three_way` runs it
- **THEN** the report has the canary violation and no HV violation

#### Scenario: Minimal project
- **GIVEN** the full set whose `bench.kicad_pro` is cut to its `meta` and `net_settings` keys
- **WHEN** `test_minimal_project` runs it
- **THEN** the HV and canary violations are the same, by type and item uuids, as in the full set

#### Scenario: Patterns as wildcards and regular expressions
- **GIVEN** the full set plus the pattern entries `Net-(R1-Pad1)`, `D[0]`, `IN+`, `VCC_3.3` and `SW?_*`, each for HV, added by the test
- **WHEN** `test_patterns` runs it
- **THEN** the rows of `+3V3`, `SIG1`, the four added names and `SW1_A` have HV violations and the canary fires, the outcomes of the decoy rows `Net-R1-Pad1`, `D0`, `INN` and `VCC_3V3` (expected `present`, S-0046) and of `SIG10` in the full set (expected `absent`) are recorded as the probes `pro-decoys` and `pro-anchor`, and a measurement other than the expected one fails the test until `pattern_matches` and a `-2` successor of `H-K-PRO-PATTERNS` follow it

#### Scenario: Board-setup floor governs
- **GIVEN** the bench with HV clearance 0.5 mm, once with the template floor and once with `board.design_settings.rules.min_clearance` set to `1.5` in `bench.kicad_pro`
- **WHEN** `test_floor` runs both
- **THEN** the first report has no HV violation, the second has the HV violation of every HV row, and the canary fires in both

#### Scenario: Canary missing
- **GIVEN** an authored DRC report text holding the HV violations of the bench and no canary violation, read with c0017's `read_drc_report`
- **WHEN** `uv run pytest tests/unit/test_netclass_bench.py -k canary` judges it as the `full` case and as the `noproject` case
- **THEN** `judge` returns `inconclusive` for both, and `assert_loaded` fails with a message saying the rules file was not loaded

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1` after the project tests
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds `present` for `pro-full-t10`, `absent` for `pro-noproject-t10`, `pro-noclass-t10` and `pro-anchor-t10`, and `equal` for `pro-minimal-t10`

#### Scenario: 9.0 job
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/project -q` runs in the `kicad-9` job
- **THEN** every target-9 case runs and passes, the target-10 cases are skipped by `kicad_min_major(10)`, and none fails

### Requirement: Project files survive kicad-cli runs
`tests/kicad/project/test_project_files.py` (marker `needs_kicad`) SHALL run `pcb drc` through c0017's `KicadCli.drc` and `pcb export svg -l Edge.Cuts --mode-single` through c0009's `KicadCli.run`, each with `files` naming the three files of the target-9 bench set, and SHALL settle `H-K-PRO-PRL` from `CliRun.outputs`, which maps every file a run created or changed in its temporary copy.
- `bench.kicad_pro` MUST be absent from the `outputs` of each run, which means its SHA-256 is unchanged.
- Whether `bench.kicad_prl` is in the `outputs` of each run MUST be recorded in the test output and in `docs/hypotheses.md`.
- The outcomes MUST be the probes `pro-file-drc` and `pro-file-export` (`equal` when `bench.kicad_pro` is absent from `outputs`, `different` otherwise) and `pro-prl-drc` and `pro-prl-export` (`present` when `bench.kicad_prl` is in `outputs`, `absent` otherwise) of `tests/kicad/_probes.py`.
- The test MUST NOT run `kicad-cli` outside `KicadCli`. Files of the repository MUST NOT change: `git status --porcelain` is the same before and after `uv run pytest tests/kicad/project`.

#### Scenario: Project file untouched
- **GIVEN** the target-9 bench set written by `write_triad` into `tmp_path`
- **WHEN** `uv run pytest tests/kicad/project/test_project_files.py::test_prl_and_pro` runs on 10.0.6 and on 9.0.9
- **THEN** `bench.kicad_pro` is in neither run's `outputs`, and whether `bench.kicad_prl` is in each run's `outputs` is reported

#### Scenario: Repository untouched
- **GIVEN** a clean working tree
- **WHEN** `uv run pytest tests/kicad/project -q` runs
- **THEN** `git status --porcelain` prints the same as before, and no `.kicad_prl` exists under the repository

### Requirement: Built projects pass the build oracle
`tests/kicad/build/` (marker `needs_kicad`, major-aware) SHALL prove on the running `kicad-cli` that projects written by `fenolite build` are what the DSL describes. Every case MUST build `examples/blink_2layer/design.py` (or a variant built in the test) into a temporary folder, run `kicad-cli` through c0009's `KicadCli` on a copy with an empty `KICAD_CONFIG_HOME`, and judge DRC only from the JSON report read with c0017's `read_drc_report`, never from the exit code (c0017, "DRC verdicts come from the JSON report").
- **Load.** The target-9 blink MUST load on 9.0.9 and 10.0.6, and the target-10 blink on 10.0.6.
- **Positions.** `pcb export pos` MUST give each part its DSL position plus `BOARD_ORIGIN`, its rotation and its side, compared through c0009's `tests/kicad/board/_frame.py`.
- **Clean DRC.** The report MUST hold no violation of severity `error`. `unconnected_items` are a separate list and are allowed. The only exception MUST be a violation type that the baseline probe shows a clean placement cannot avoid, named in the design with its probe outcome; no exception by severity or count is allowed.
- **Canary.** On a separate copy whose `.kicad_dru` has c0018's canary rule inserted right after `(version 1)` by `tests/kicad/rules/_bench.py::with_canary` (c0018; last on a major where `H-K-DRU-ORDER` says the earlier rule governs), a `clearance` violation absent from the plain run MUST appear. The blink holds no canary pair, so c0018's `require_canary(report, bench)` does not apply: this change's pure judge `tests/_build_judge.py::canary_outcome(plain, canary)` MUST give `present` when such a violation appears and `inconclusive` otherwise, and `assert_loaded(outcome, case)` MUST fail an `inconclusive` case with "rules file not loaded". The unconditional canary MUST NOT share a run with the class case.
- **Violated class.** A variant whose `PWR` class has a 2 mm clearance MUST give a `clearance` violation whose items are the uuids of the two adjacent `U1` pads on `VIN` and `GND`. The same set without `blink.kicad_pro` MUST give no violation for those pads, and the as-built blink MUST give none either. An item uuid that is no pad uuid MUST make the probe `different`, recorded as data for c0020's DRC item attribution.
- **Vendored table.** On 10.0.6, for targets 9 and 10, the built project MUST give no `lib_footprint_issues` and no `lib_footprint_mismatch`, and the same copy without `fp-lib-table` MUST give `lib_footprint_issues`; otherwise the case is `inconclusive`. On 9.0.9 the outcomes MUST be recorded and not asserted while `H-K-LIB-DRC` is open there.
- **Path property.** After `pcb upgrade --force` on 10.0.6, `read_board` of the re-saved board MUST give `properties["fenolite.path"]` equal to the component path for all three footprints, and each property node MUST still hold `(hide yes)`.
- **Probes first.** The cases MUST be probes of c0017's `tests/kicad/_probes.py` with the ids `build-pathprop-t<M>`, `build-libtable-t<M>`, `build-baseline-t<M>`, `build-offboard-t<M>`, `build-canary-t<M>` and `build-class-t<M>` for target `M`. Each probe MUST map its result to one outcome of c0017's closed set, as design Decisions 25 and 26 define it per probe.
- The `pathprop`, `libtable`, `baseline` and `offboard` probes MUST run before the DSL exists, on boards made in the test with `layers.created_layers` and `embed.place_footprint`, and every stop rule of design Decision 25 MUST be applied before the DSL code starts: a refuted `H-K-BUILD-PATHPROP` (either `pathprop` probe) removes the property from the build; a `different` libtable outcome on 10.0.6 makes library parity recorded data; an `absent` (the table is not read) or `inconclusive` libtable outcome on 10.0.6 stops the change until the table form, or the reading of `H-K-LIB-DRC`, is corrected; an error-severity type of a `present` baseline is excluded from the acceptance by name only, never by severity or count.
- The violation types, their severities and the `unconnected_items` count that the `baseline` and `offboard` probes see MUST be recorded as fact rows of `docs/formats/kicad/drc.md` with `H-K-BUILD-TRIAD`, not in the probe files.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, which hold only the version, the probe ids and their outcomes (c0017), so `tests/kicad/test_probe_results.py` detects a change of behaviour. Built files MUST NOT be committed.

#### Scenario: Blink builds clean
- **GIVEN** the blink built for target 10 on the local KiCad 10.0.6
- **WHEN** `uv run pytest tests/kicad/build/test_build_oracle.py::test_blink_builds_clean` runs
- **THEN** the board loads, `pcb export pos` gives `U1`, `R1` and `D1` at their DSL positions plus (100 mm, 100 mm) with their rotations and sides, the DRC report holds no violation of severity `error`, and the canary copy holds a `clearance` violation that the plain run lacks

#### Scenario: Violated class, three ways
- **GIVEN** the blink built for target 9 and its `PWR` variant at 2 mm clearance
- **WHEN** `uv run pytest tests/kicad/build/test_build_oracle.py::test_violated_class` runs on 10.0.6
- **THEN** the variant's report holds the `clearance` violation between the two `U1` pads on `VIN` and `GND`, while the variant without `blink.kicad_pro` and the as-built blink hold none for those pads

#### Scenario: Vendored table with a missing-table control
- **GIVEN** the blink built for target 10, whose `fp-lib-table` has the row `Mini` -> `${KIPRJMOD}/lib/Mini.pretty`
- **WHEN** `uv run pytest tests/kicad/build/test_build_oracle.py::test_vendored_table` runs on 10.0.6
- **THEN** the report holds no `lib_footprint_issues` and no `lib_footprint_mismatch`, and the copy without `fp-lib-table` holds `lib_footprint_issues`

#### Scenario: Path property survives a re-save
- **GIVEN** the blink built for target 10
- **WHEN** `uv run pytest tests/kicad/build/test_build_oracle.py::test_path_property` runs `pcb upgrade --force` on a copy on 10.0.6
- **THEN** `read_board` of the re-saved board gives `properties["fenolite.path"]` equal to `U1`, `R1` and `D1` for the three footprints, each with `(hide yes)`

#### Scenario: Canary missing fails
- **GIVEN** a plain report and a canary-copy report authored in the test, the second holding no `clearance` violation that the first lacks
- **WHEN** the hermetic `uv run pytest tests/unit/test_build_judge.py` passes them to `canary_outcome` and the outcome to `assert_loaded`
- **THEN** the outcome is `inconclusive`, and `assert_loaded` fails with the message "rules file not loaded"

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1` after `uv run pytest tests/kicad/build/test_build_probes.py -rA`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds an outcome for every `build-*` probe of targets 9 and 10

#### Scenario: 9.0 job
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/build -rA` runs in the `kicad-9` job
- **THEN** every target-9 case runs and passes, the vendored-table outcomes are recorded without assertion, and the target-10 cases are skipped by `kicad_min_major(10)`

### Requirement: Drawing sheets are judged by what KiCad draws
Drawing-sheet oracle tests SHALL judge a sheet by the texts and lines that `kicad-cli` draws, never by its exit code: a missing `--drawing-sheet` file or `page_layout_descr_file` falls back silently to the default sheet, with exit 0 and no message (observed on 9.0.9 and 10.0.6 on 2026-10-01, `H-K-WKS-FALLBACK`).
- `tests/kicad/sheets/_svg.py` SHALL provide `read_sheet_svg(text) -> SheetSvg(width_mm, height_mm, texts, paths)`, using only the standard library: the page size from the SVG `width` and `height` in millimetres, every hidden searchable `<text>` with its string and anchor, and every straight segment of the `<path>` elements (`H-K-WKS-SVG`). Its tests MUST run on an authored SVG snippet without `kicad-cli`.
- `tests/kicad/sheets/_sheet_bench.py` SHALL provide `DRAWING_SHEET_ERROR = "Error loading drawing sheet"` and `export_sheet_svg(board, sheet, *, files=None)`, which runs `pcb export svg <board> -l Edge.Cuts --mode-single [--drawing-sheet <sheet>]` through c0009's `KicadCli.run`, with the board, the sheet and any project in `files`.
- A sheet case MUST be `reject` when the output holds `DRAWING_SHEET_ERROR`. Otherwise, comparing its drawn text multiset with the default-sheet control of the same board in the same session, it MUST be `absent` when the two are equal (silent fallback); `load` when they differ and the case's marker text, when it has one, is drawn; and `different` when they differ but the marker is not drawn (KiCad drew a sheet other than the case's).
- Every session MUST run the default-sheet control (`wks-default`, no `--drawing-sheet`) and the positive control `tests/data/kicad/tokens/skeleton.kicad_wks` (`wks-control`). When the positive control is not `load`, or the default control draws no text, every sheet case of the session MUST be `inconclusive`.
- A semantic case MUST be `equal` when every drawn text and line matches the prediction of `fenolite.templates.layout` and `resolve_text`, computed with the page size read from the SVG: a text's x within 0.01 mm and its y within half its text height, and line ends within 0.01 mm. Otherwise it MUST be `different`.
- The living requirement "Load check per file kind" and the token fuzz harness are unchanged.

#### Scenario: Silent fallback is not a load
- **GIVEN** a `--drawing-sheet` path naming a file that does not exist
- **WHEN** the case runs on 10.0.6 and `kicad-cli` exits 0 without the message
- **THEN** the outcome is `absent`, not `load`

#### Scenario: Broken sheet rejected
- **GIVEN** the authored probe sheet of `wks-broken`, which holds `(frobnicate 1)` as an item
- **WHEN** the case runs
- **THEN** the outcome is `reject`, whatever the exit code

#### Scenario: Marker missing is not a load
- **GIVEN** a fake run without the message whose drawn texts differ from the default control but lack the case's marker
- **WHEN** it is classified
- **THEN** the outcome is `different`

#### Scenario: Failed control makes the session inconclusive
- **GIVEN** a session in which the skeleton control is not `load`
- **WHEN** any sheet case of that session is classified
- **THEN** its outcome is `inconclusive`

#### Scenario: SVG reader on an authored snippet
- **GIVEN** an authored SVG with `width="297.0022mm"`, two hidden `<text>` elements and one `<path d="M10 10 L20 10">`
- **WHEN** `uv run pytest tests/kicad/sheets/test_svg_reader.py` runs
- **THEN** `read_sheet_svg` returns `width_mm == Decimal("297.0022")`, the two strings with their anchors, and the segment (10, 10, 20, 10)

### Requirement: One drawing sheet serves several sizes on both majors
`tests/kicad/sheets/test_sheet_acceptance.py` (`needs_kicad`, major-aware) SHALL prove v0.1 acceptance item 4: one `.kicad_wks` per shipped example, produced by `fenolite template build`, is drawn as predicted on every listed size, with the same bytes on both majors.
- For `iso5457_generic` (or `a_series_generic` after the naming gate) on A4 and A3 boards, and for `letter_generic` on Letter and Tabloid boards, each board MUST be written by `write_board` (target 10 on 10.0.6, target 9 on 9.0.9) with that size in `Board.sheet` and a `TitleBlock` whose seven fields are non-empty, and exported with `--drawing-sheet` under c0009's isolated runner.
- For each size the output MUST lack `DRAWING_SHEET_ERROR`; the drawn hidden-text multiset MUST equal the texts of `layout` resolved by `resolve_text` for that title block, the board's paper name as written and its file name; it MUST differ from the default-sheet control of the same board in the same session; and every predicted line MUST be found among the SVG path segments within 0.01 mm.
- The same run MUST hold the controls: the generated sheet with `(frobnicate 1)` inserted is `reject`; a missing `--drawing-sheet` file and a project whose `page_layout_descr_file` names a missing file are `absent`; `skeleton.kicad_wks` is `load`. A control with another outcome MUST fail the test.
- `tests/kicad/sheets/test_project_sheet.py` MUST write, with `write_triad`, a created board with `Board.sheet = SheetFrameRef("A3", drawing_sheet="frame.kicad_wks")`, a `TitleBlock` and one parameter, beside the generated sheet named `frame.kicad_wks`, and MUST find, without `--drawing-sheet`, the predicted texts with the title-block values and the parameter (`H-K-PRO-WKS`).
- The exit code MUST NOT be read. The tests MUST pass on the local 10.0.6 and in the pinned 9.0.9 image, and in the `kicad-10` and `kicad-9` jobs.

#### Scenario: Acceptance on both majors
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/sheets/test_sheet_acceptance.py -rA` runs on the local 10.0.6 and inside the pinned 9.0.9 image
- **THEN** every example and size passes with all controls, and the `.kicad_wks` bytes used are the same in both runs

#### Scenario: Wrong prediction fails
- **GIVEN** a test copy of `layout` that moves one predicted text by 1 mm
- **WHEN** the acceptance comparison runs on the same SVG
- **THEN** it fails naming that text and the size

#### Scenario: Project key draws the sheet
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/sheets/test_project_sheet.py` runs on 10.0.6 and on 9.0.9
- **THEN** it passes, and the drawn texts include the title and the parameter value of the design

### Requirement: Drawing sheet and paper semantics are probed
The drawing-sheet and paper probes SHALL be entries of c0017's `tests/kicad/_probes.py` `PROBES`, run on majors 9 and 10, with their outcomes pinned in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`.
- The sheet of every probe MUST be an authored CC0 fixture `tests/data/kicad/sheets/probe_*.kicad_wks`, declared with `origin = "authored"` in `tests/data/MANIFEST.toml`, except: `wks-default`, `wks-missing-file`, `wks-pro-missing` and `pcb-paper-*`, which use no sheet file; `wks-control`, which uses c0007's `tests/data/kicad/tokens/skeleton.kicad_wks`; and `wks-accept-*`, which use the sheets that `fenolite template build` writes.
- Every probe except `wks-accept-*` MUST run, and its outcome MUST be compared with the expected outcome of the table below and with the corner, repeat, scope, token, value and paper rules of the `design-model`, `kicad-file-backend` and `sheet-templates` requirements, before the model code of the change that adds this requirement (c0012) is written. `wks-accept-*` run with the acceptance test. `pcb-paper-*` and `wks-tokens` are re-run, with the same expected outcomes, on boards written by `write_board` once the board code exists.

| probe | expected outcome | hypothesis |
|---|---|---|
| `wks-svg-shape` | `present` | `H-K-WKS-SVG` |
| `wks-default`, `wks-control` | `present`, `load` | controls |
| `wks-broken` | `reject` | `H-K-WKS-FALLBACK` |
| `wks-missing-file`, `wks-pro-missing` | `absent` | `H-K-WKS-FALLBACK` |
| `wks-corners` | `equal` | `H-K-WKS-CORNER` |
| `wks-repeat` | `equal` | `H-K-WKS-REPEAT` |
| `wks-percent` | `equal` | `H-K-WKS-PCT` |
| `wks-page1only`, `wks-notonpage1` | `present`, `absent` | `H-K-WKS-PAGE1` |
| `wks-tokens`, `wks-undefined-var` | `equal`, `present` | `H-K-WKS-VARS` |
| `wks-value-<atom>`, `wks-value-unknown` | `load`, `reject` | `H-K-WKS-VALUES` |
| `wks-bitmap-corrupt` | `present` | `H-K-WKS-BITMAP` |
| `wks-bitmap` | `load` | `H-K-WKS-BITMAP` |
| `wks-bitmap-clean` | `absent` | `H-K-WKS-BITMAP` |
| `wks-resolution` | `different` | `H-K-WKS-RES` (refuted by the spike; superseded by `H-K-WKS-RES-2`) |
| `wks-resolution-exact` | `equal` | `H-K-WKS-RES-2` |
| `pcb-paper-<name>` except `custom` | `equal` | `H-K-PCB-PAPER-2` |
| `pcb-paper-custom` | `different` | `H-K-PCB-PAPER` (refuted by the spike; superseded by `H-K-PCB-PAPER-2`) |
| `pcb-paper-custom-mil`, `pcb-paper-custom-fraction` | `equal` | `H-K-PCB-PAPER-2` |
| `wks-pro-relative`, `wks-pro-kiprjmod` | `present` | `H-K-PRO-WKS` |
| `wks-accept-<example>-<size>` | `equal` | acceptance item 4 |

- `pcb-paper-<name>` MUST compare the SVG page size with `PAPER_SIZES`: within 0.05 mm for `A0` … `A5`, and exactly for the `User` form of the whole-mil sizes Letter, Legal and Tabloid, in the orientation written. `pcb-paper-custom` compares `(paper "User" 300 200)` exactly with 300 × 200 mm, and its `different` outcome is the refutation of `H-K-PCB-PAPER`; `pcb-paper-custom-mil` and `pcb-paper-custom-fraction` compare `(paper "User" 300 200)` and `(paper "User" 300.5 200.25)` exactly with each dimension truncated to a whole mil of 0.0254 mm (`H-K-PCB-PAPER-2`, measured by the spike on 9.0.9 and 10.0.6 on 2026-10-02).
- `wks-resolution` compares the start of `probe_resolution`'s line (written 50.0006 mm) with the truncated micrometre, and its `different` outcome is the refutation of `H-K-WKS-RES`; `wks-resolution-exact` compares it with the value as written, within 0.0001 mm (`H-K-WKS-RES-2`).
- A probe whose outcome differs from this table MUST NOT be overridden: `layout` MUST follow the measurement on both majors, and a successor hypothesis row with suffix `-2` MUST record it (c0014's "Refuted rows keep their id").
- `wks-bitmap-corrupt` holds a `pngdata` whose bytes are not a PNG. Its outcome MUST be `present` when its output holds at least one line (the decoder line) that the output of `wks-control` lacks. `wks-bitmap` holds a 1x1 authored PNG and MUST be classified like any sheet case. `wks-bitmap-clean` runs no `kicad-cli`: it reads the memoised outputs of `wks-bitmap`, `wks-bitmap-corrupt` and `wks-control` of the same session, and MUST be `absent` when no line that `wks-bitmap-corrupt` adds over `wks-control` appears in the output of `wks-bitmap`, and `present` otherwise. Each probe thus has one outcome. A `load` verdict alone cannot tell a good bitmap from a bad one, because KiCad loads the rest of the sheet either way.
- Each hypothesis MUST become `KICAD-VERIFIED (9.0.x, 10.0.x)` only when its probes give the expected outcome on both majors; otherwise it stays `INFERRED` with the reason. Bitmap loading stays `INFERRED` when `wks-bitmap-corrupt` is not `present` or `wks-bitmap-clean` is not `absent` on a major. Bitmap plotting stays `INFERRED` (S-0075).

#### Scenario: Probe outcomes pinned
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/test_probe_results.py` runs in the `kicad-9` and `kicad-10` jobs
- **THEN** it passes, and both probe files hold an outcome for every `wks-*` and `pcb-paper-*` probe of their major

#### Scenario: Probe tests run first
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/sheets/test_sheet_probes.py -rA` runs on 10.0.6 and in the pinned 9.0.9 image
- **THEN** each probe test asserts on `run(<probe id>)` and passes with the outcome of the table

#### Scenario: Paper size measured
- **GIVEN** a board written with `SheetFrameRef("Tabloid")`
- **WHEN** the probe `pcb-paper-tabloid` runs
- **THEN** the SVG page is 431.8 x 279.4 mm and the outcome is `equal`

### Requirement: Board-setup minimums are proved by kicad-cli
`tests/kicad/project/test_minimums_drc.py` (marker `needs_kicad`) SHALL prove on the running `kicad-cli` that the five keys of `lowering.MINIMUM_KEYS` are read, that a minimum above the `min` of a board-wide custom rule governs it, and that the project Fenolite writes lets the rule values take effect, and SHALL measure whether a custom clearance rule without a condition overrides a larger class clearance. Every case MUST be judged from the DRC JSON report read with c0017's `read_drc_report`, by violation type and item uuid, never by exit code.

The bench is built by `tests/_minimum_bench.py` through the model and written with `write_triad` as `bench.kicad_pcb`, `bench.kicad_pro` and `bench.kicad_dru`:
- one probe item per kind, each at least 4 mm from other copper, and each between the bench rule of its kind and the minimum of the template runs below (the template value, and 0.2 mm for `min_clearance`): two 0.25 mm tracks with a 0.15 mm gap (`clearance`), a 0.15 mm track (`track_width`), a via of 0.45 mm diameter and 0.24 mm drill (`via_diameter`), a via of 0.6 mm diameter and 0.25 mm drill (`hole_size`), and a 0.25 mm track whose copper edge is 0.35 mm from the board edge (`edge_clearance`);
- a row of class HV (clearance 2 mm) beside a `GND` track with a 1.0 mm gap, and a model class `Default` with clearance 0.05 mm, so that no class value flags a probe item;
- five board-wide rules of severity `error` and priority 0: `clearance` 0.1 mm, `track_width` 0.1 mm, `via_diameter` 0.35 mm, `hole_size` 0.2 mm and `edge_clearance` 0.2 mm;
- the canary of c0010's net-class bench: a 3 mm `clearance` rule on `net CANARY_A` with priority 1, so that it is written last, and a `CANARY_A` track 0.75 mm from a `CANARY_B` track, at least 10 mm from other copper.

The violation type of each kind MUST be the one c0018 observed for its custom rule: `clearance`, `track_width`, `via_diameter`, `drill_out_of_range` and `copper_edge_clearance`. Four runs MUST be made per target, each through c0009's `KicadCli` on a temporary copy with an empty `KICAD_CONFIG_HOME`:
- `keys-template`: the bench without its five board-wide rules, with the five keys at the template's values and `min_clearance` set to `0.2` by the test;
- `keys-lowered`: the same, with the five keys set by the test to `0.1`, `0.1`, `0.35`, `0.2` and `0.2`;
- `rules-template`: the bench with its rules, with the five keys reset by the test as in `keys-template`;
- `rules-lowered`: the bench as `write_triad` writes it.

Each run MUST be the source of probes of `tests/kicad/_probes.py`: `pro-min-<run>-<kind>-t<target>` for each kind (`present` when the probe item has its violation, `absent` otherwise), `pro-min-class-t<target>` (the HV row in `rules-lowered`) and `pro-min-class-control-t<target>` (the HV row in `keys-template`). Target-10 runs MUST run on major 10, and target-9 runs on majors 9 and 10.
- A run without the canary violation MUST give `inconclusive` for each of its probes, and the test MUST then fail with a message saying that the rules file was not loaded; it MUST NOT pass or skip. The outcomes MUST be computed by pure functions of `tests/_minimum_bench.py`, tested without KiCad.
- For each kind of `MINIMUM_KEYS[target]`, the tests MUST assert `present` in `keys-template` and `absent` in `keys-lowered` and `rules-lowered`. They MUST assert `present` for `pro-min-class-control`. For `rules-template` they MUST assert `present` exactly when the kind's entry of `lowering.FLOOR_OVER_RULES` holds the running major, and for `pro-min-class` `absent` exactly when `lowering.RULES_OVER_CLASSES` holds it.
- A measurement that disagrees MUST fail the test until the table in `rules-model` ("Conflicts with board-setup minimums are reported" or "Class clearances against board-wide clearance rules are reported") and a `-2` successor of the hypothesis follow it. A `present` outcome in `rules-lowered` stops the change: the written project does not let a rule take effect.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, so that `tests/kicad/test_probe_results.py` detects a change of behaviour in a later image.
- This bench departs from "Rules proofs carry a canary" in two points, as c0010's net-class bench does: the canary is scoped to `CANARY_A` and written last, because a board-wide `clearance` rule written after an unconditional canary would govern the canary pair; and the project is the one `write_triad` writes, because it is under test. Every other part of that requirement applies.

#### Scenario: Keys read
- **GIVEN** the target-10 bench on the local `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/project/test_minimums_drc.py::test_keys` runs
- **THEN** each probe item has its violation in `keys-template` and none in `keys-lowered`, and the canary fires in both

#### Scenario: Minimum over a lower rule
- **GIVEN** the `rules-template` run of the same bench, and `FLOOR_OVER_RULES` holding both majors for every key
- **WHEN** `test_floor_over_rules` runs
- **THEN** each probe item has its violation, the hole probe's being `drill_out_of_range`, and the canary fires

#### Scenario: Written project lets the rules take effect
- **GIVEN** the `rules-lowered` run, whose project holds `min_through_hole_diameter == JsonNumber("0.2")`
- **WHEN** `test_written` runs
- **THEN** no probe item has its violation and the canary fires

#### Scenario: Custom rule against a class clearance
- **GIVEN** the HV row in the `keys-template` and `rules-lowered` runs, and `RULES_OVER_CLASSES` holding both majors
- **WHEN** `test_rules_over_classes` runs
- **THEN** the HV row has its `clearance` violation in `keys-template` and none in `rules-lowered`, and the outcomes are recorded as `pro-min-class-control-t10` and `pro-min-class-t10`

#### Scenario: Canary missing
- **GIVEN** an authored DRC report text holding the violation of every probe item and no canary violation, read with c0017's `read_drc_report`
- **WHEN** `uv run pytest tests/unit/test_minimum_bench.py -k canary` judges it for each run
- **THEN** every outcome is `inconclusive`, and `assert_loaded` fails with a message saying the rules file was not loaded

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1` after the minimum tests
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds an outcome for every `pro-min-*` probe of targets 9 and 10

#### Scenario: 9.0 job
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/project -q` runs in the `kicad-9` job
- **THEN** every target-9 case runs and passes, and the target-10 cases are skipped by `kicad_min_major(10)`

### Requirement: Vendored projects and user properties pass the oracle
`tests/kicad/build/` (marker `needs_kicad`, major-aware) SHALL prove on the running `kicad-cli` that a built project whose footprints come from global or template rows is self-contained once they are vendored, and that user properties written by the build load and survive. Every case MUST build a blink variant into a temporary folder, run `kicad-cli` through c0009's `KicadCli.run` on a copy, and judge DRC only from the JSON report read with c0017's `read_drc_report`, never from the exit code (c0017, "DRC verdicts come from the JSON report").
- **Bench.** `tests/kicad/build/_vendorcases.py` makes, in a temporary folder:
  - a fake global library: a copy of the CC0 `tests/data/libs/Mini_v9.pretty` and `Mini_v9.kicad_sym`, named by the rows `Mini` of the global tables `<D>/<M>.0/fp-lib-table` and `sym-lib-table` of a configuration folder `D`, for both majors;
  - `D_alt`, the same with a copy whose `Mini_R_0603` pad `1` is moved 0.05 mm along X;
  - the blink built from a folder without project tables, with `config_home=D`: not vendored (c0011's rule, later `vendor="project"`), and vendored, with its placed footprints copied into `lib/Mini.pretty/` and one project row (by file copies of the bench while the probes run before this change's build code, later by `vendor="all"`);
  - the property board, whose user properties are appended through `embed.with_property` before `embed.place_footprint` (through the model API while the probes run first, later by the build).
- **Configuration.** A configuration folder MUST reach `kicad-cli` only as the explicit `env` entry `KICAD_CONFIG_HOME` of `KicadCli.run`; every other run uses the runner's empty configuration folder.
- **Probes first.** The cases MUST be probes of c0017's `tests/kicad/_probes.py`. Each probe maps its result to one outcome of c0017's closed set, and the `-t9` probes run on majors 9 and 10, the `-t10` probes on major 10:
  - `vendor-global-t<M>`: `equal` when the vendored build gives no `lib_footprint_issues` and no `lib_footprint_mismatch` while the build that is not vendored gives one `lib_footprint_issues` for each footprint; `absent` when `lib_footprint_issues` remain with vendoring; `different` when a `lib_footprint_mismatch` appears; `inconclusive` when the build that is not vendored gives no `lib_footprint_issues`; `reject` when no report is written.
  - `vendor-shadow-t<M>` (with `D_alt`): `present` when the build that is not vendored gives exactly one `lib_footprint_mismatch` (the control: the global table was read) and the vendored build gives none; `absent` when the vendored build gives it too; `inconclusive` when the control gives none.
  - `vendor-hide-t<M>` (with `D`): the vendored build with `Mini_LED_THT_3mm.kicad_mod` removed from `lib/Mini.pretty/`. `present` when it gives exactly one `lib_footprint_issues`, for `D1`, while the build that is not vendored gives no library violation with `D` (the control); `absent` when it gives none; `inconclusive` when the control gives a library violation.
  - `vendor-props-t<M>`: the vendored property board, with user properties on `R1` (two, one value holding `"`, `\` and `µ`) and on `D1` (bottom side). `equal` when its report holds no `lib_footprint_issues` and no `lib_footprint_mismatch`, as the plain vendored build's; `different` otherwise; `reject` when no report is written.
  - `vendor-resave-t<M>` (major 10): after `pcb upgrade --force` of that board, `present` when `read_board` gives every user property with its value and every user property node keeps `(hide yes)`; `absent` otherwise; `reject` when the upgrade fails.
  - `vendor-dupname-t10` (major 10): the vendored board with, inserted by text after `R1`'s last property, a second `Datasheet` property and the properties `datasheet` and `reference`. After `pcb upgrade --force`, `present` when one `Datasheet` node remains, holding the inserted value, and `datasheet` and `reference` are kept; `absent` when two `Datasheet` nodes remain; `different` otherwise.
- **Stop rules,** applied before any build code of this change is written: a `vendor-global` outcome other than `equal`, on either major, stops the vendoring half until the table form is corrected; a `vendor-props` outcome other than `equal` stops the property half until the property form is corrected. The `vendor-shadow`, `vendor-hide`, `vendor-resave` and `vendor-dupname` outcomes change no behaviour: they are recorded and written into `docs/dsl.md` and the format pages, and the reserved names stay whatever `vendor-dupname` gives.
- **Acceptance.** `tests/kicad/build/test_vendor_oracle.py` asserts the expected outcomes: `test_global_vendored` (`equal`), `test_shadow` (`present`), `test_hidden_items` (`present`), `test_user_properties` (`equal`, and `present` for the re-save on 10.0.6) and `test_duplicate_field_name` (`present`, 10.0.6). Target 9 runs on 9.0.9 and 10.0.6, target 10 on 10.0.6.
- **Official libraries.** Where they are installed (marker `needs_libs`), `tests/libs/test_build_official.py` MUST build `examples/blink_official/design.py` into `tmp_path` with the default vendoring and, with `needs_kicad` too, `kicad-cli pcb drc` on that folder with an empty configuration MUST give no `lib_footprint_issues` and no `lib_footprint_mismatch`. Only counts are recorded, and nothing built from it is committed (`ip-hygiene`).
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, which hold only the version, the probe ids and their outcomes (c0017). The facts go to `docs/formats/kicad/libraries.md` and `board.md` as rows with `H-K-VENDOR-*`. Built files and library copies MUST NOT be committed.

#### Scenario: Vendored global footprints pass the library check
- **GIVEN** the blink built from the fake global library for target 10
- **WHEN** `uv run pytest tests/kicad/build/test_vendor_oracle.py::test_global_vendored` runs on 10.0.6
- **THEN** the vendored build's report holds no `lib_footprint_issues` and no `lib_footprint_mismatch`, and the build that is not vendored gives three `lib_footprint_issues`

#### Scenario: The project row wins over the global row
- **GIVEN** the vendored blink and the configuration folder `D_alt`
- **WHEN** `uv run pytest tests/kicad/build/test_vendor_oracle.py::test_shadow` runs on 10.0.6 and on 9.0.9
- **THEN** the build that is not vendored gives exactly one `lib_footprint_mismatch` for `R1`, and the vendored build gives none

#### Scenario: Items missing from the vendored library are not taken from the global one
- **GIVEN** the vendored blink without `lib/Mini.pretty/Mini_LED_THT_3mm.kicad_mod`, and the configuration folder `D`
- **WHEN** `uv run pytest tests/kicad/build/test_vendor_oracle.py::test_hidden_items` runs
- **THEN** the report holds exactly one `lib_footprint_issues`, for `D1`

#### Scenario: User properties survive a re-save
- **GIVEN** the vendored blink with user properties built for target 9
- **WHEN** `uv run pytest tests/kicad/build/test_vendor_oracle.py::test_user_properties` runs on 10.0.6
- **THEN** its report holds no library violation, and after `pcb upgrade --force` `read_board` gives `R1` the value with `"`, `\` and `µ` unchanged, and every user property node holds `(hide yes)`

#### Scenario: A duplicate field name is merged
- **WHEN** `uv run pytest tests/kicad/build/test_vendor_oracle.py::test_duplicate_field_name` runs on 10.0.6
- **THEN** after the re-save `R1` holds one `Datasheet` node with the inserted value, and the `datasheet` and `reference` properties are unchanged

#### Scenario: 9.0 job
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/build/test_vendor_oracle.py -rA` runs in the `kicad-9` job
- **THEN** every target-9 case without a re-save runs and passes, and the re-save, duplicate-name and target-10 cases are skipped by `kicad_min_major(10)`

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1` after `uv run pytest tests/kicad/build/test_vendor_probes.py -rA`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds an outcome for every `vendor-*` probe of majors 9 and 10

#### Scenario: Official libraries where they are installed
- **GIVEN** the official libraries found by the `needs_libs` census and a local `kicad-cli` 10.0.6
- **WHEN** `uv run pytest -m "needs_libs and needs_kicad" tests/libs/test_build_official.py -rA` runs
- **THEN** the official blink built into `tmp_path` holds its three footprints under `lib/`, its report holds no `lib_footprint_issues` and no `lib_footprint_mismatch`, and `uv run pytest tests/residue/test_official_libs.py` passes

### Requirement: Check project copy set
`fenolite.backends.kicad.projectset` SHALL plan, without writing anything, the closed set of project files that `kicad-cli pcb drc` reads, and c0009's runner SHALL copy them through c0017's `KicadCli.drc(board, files=…)`.
- **Board.** `resolve_board(path) -> Path` MUST accept a `.kicad_pcb` file; a `.kicad_pro` file (the board of the same stem); or a folder holding exactly one `.kicad_pro` (the board of its stem), or else exactly one `.kicad_pcb`. A folder with several candidates or none MUST raise `ProjectResolutionError` (`cli_code` `FEN-2001`) whose `candidates` list them. A missing path or board MUST raise a `FenoliteError` with `cli_code` `FEN-3001`.
- **Included.** `project_set(path, *, max_bytes=MAX_COPY_BYTES) -> ProjectSet` MUST include, under names relative to the board's folder: the board; `<stem>.kicad_pro` and `<stem>.kicad_dru` when present (`has_project`, `has_rules`), because KiCad reads rules only with a project file next to the board (`H-K-TOK-RULES-SILENT`) and pairs them by stem (`H-K-CHECK-COPYSET`); the top-level `fp-lib-table`, read with c0008's `read_lib_table`, and each library folder that a row names as `${KIPRJMOD}/<rel>` inside the root, under `<rel>`; and the drawing sheet named at `WORKSHEET_POINTER = "/pcbnew/page_layout_descr_file"` of the project (read with c0010's `read_project` and `_json.get`) when it is a `${KIPRJMOD}` or relative path inside the root.
- **Never included.** `.kicad_prl`, `.kicad_sch`, `sym-lib-table`, backups, `fp-info-cache`, `.fenolite/` and every other file. Absolute library rows and an absolute drawing-sheet path MUST stay as written and be read in place by KiCad.
- **Skips.** Each named file or folder that is not copied MUST give a `SkippedFile(name, reason)`: `outside-root`, `variable` (a variable other than `${KIPRJMOD}`), `relative` (a library row without a variable), `missing`, `nested-table` (a `Table` row), `too-large`, or `reserved-name` (a name whose first path part is `config`, which c0009's runner reserves for `KICAD_CONFIG_HOME` and refuses in `files`).
- **Size.** `MAX_COPY_BYTES` MUST be `256 * 2**20`. The board, project, rules file and table MUST always be included. The drawing sheet, then the library folders in table order, MUST be skipped with `too-large` when adding them would bring the total over `max_bytes`.
- `H-K-CHECK-COPYSET` MUST be settled before `projectset.py` is final: DRC on the copy set gives the same violations and unconnected items as DRC on a copy of the whole project folder. If it is refuted, the missing kind MUST join the include list.

#### Scenario: Closed include list
- **GIVEN** `tests/_projects.py::authored_project(tmp_path, major=10, decoys=True)`, with a `${KIPRJMOD}` library row, `notes.txt`, a `sym-lib-table` and a `.kicad_prl`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_projectset.py -k include` calls `project_set` on it
- **THEN** the keys of `files` are exactly the board, `<stem>.kicad_pro`, `<stem>.kicad_dru`, `fp-lib-table` and the library folder, `skipped` is empty, and the folder snapshot is unchanged

#### Scenario: Skipped rows
- **GIVEN** an `fp-lib-table` with rows `${KIPRJMOD}/../Other.pretty`, `${MYLIBS}/X.pretty`, `Rel.pretty`, `${KIPRJMOD}/config/Y.pretty` (an existing folder) and one `Table` row
- **WHEN** `project_set` runs
- **THEN** `skipped` holds the reasons `outside-root`, `variable`, `relative`, `reserved-name` and `nested-table`, and none of the five is in `files`

#### Scenario: Size limit
- **GIVEN** the authored project and `max_bytes` smaller than its library folder
- **WHEN** `project_set(path, max_bytes=…)` runs
- **THEN** the library folder is skipped with `too-large`, and the board, project, rules file and table are in `files`

#### Scenario: Ambiguous folder
- **GIVEN** a folder holding `a.kicad_pcb` and `b.kicad_pcb` and no project file
- **WHEN** `resolve_board(folder)` is called
- **THEN** `ProjectResolutionError` is raised with `cli_code == "FEN-2001"` and both boards in `candidates`

#### Scenario: Copy set equals the folder
- **GIVEN** the authored built project with a KiCad-written `.kicad_prl`, a `sym-lib-table` and `notes.txt`
- **WHEN** `uv run pytest tests/kicad/check/test_copy_set.py::test_copy_set_equals_folder` runs on 9.0.9 and on 10.0.6
- **THEN** both runs give equal multisets of (type, severity, excluded, sorted item uuids) over violations and unconnected items, and the probe `check-copyset` records `equal`

### Requirement: Check canary injection
`fenolite.backends.kicad.canary` and `fenolite.backends.kicad.oracle.KicadOracle` SHALL prove, with a canary run of its own on a major of `CANARY_TWO_RUN` and in the counted run otherwise, whether a project's custom rules were loaded, with a canary scoped to its own nets and placed only in temporary copies (exempt from c0018's "Fenolite lowers only the design's rules").
- **Applicability.** The canary MUST apply only when the copy set holds both `<stem>.kicad_pro` and `<stem>.kicad_dru`. Otherwise the state MUST be `not-applicable`.
- **Rule.** `canary_rule_text(major)` MUST build the rule `CANARY_RULE_NAME = "fenolite_check_canary"`, a `clearance` of `CANARY_MIN_NM = 3_000_000` on net `FENOLITE_CANARY_A`, with c0018's `rulemap.rule_nodes` for that major. It MUST return `None` when `SELECTOR_SUPPORT["net"]` lacks the major. `append_rule(rules: bytes, rule_text: str, *, major) -> bytes` MUST place it where it takes precedence over the user's rules: after them when the later rule governs (`H-K-DRU-ORDER`), or where c0018's measured `rule_order` puts the governing rule on that major. It MUST keep every byte of the user's file, and MUST raise `CanaryError("names-taken")` when those bytes already contain `CANARY_RULE_NAME`. When the placement needs the `(version N)` offset and the bytes do not parse, it MUST append the rule at the end, and KiCad's verdict on the broken file stands.
- **Tracks.** `inject_board(data: bytes, *, file="") -> bytes` MUST insert two `segment`s of width `CANARY_WIDTH_NM = 250_000` on `F.Cu`, on nets `FENOLITE_CANARY_A` and `FENOLITE_CANARY_B`, from x = X to x = X + 2 mm at y = 0 and y = `CANARY_PITCH_NM` (1 mm). X is M + `CANARY_MARGIN_NM` (25 mm). M is the largest absolute number of the `at`, `xy`, `start`, `end`, `mid` and `center` nodes outside footprints, plus twice the largest one inside footprints. Their uuids MUST be `CANARY_UUIDS`, `uuid5(FENOLITE_NS, "kicad-canary:A")` and `uuid5(FENOLITE_NS, "kicad-canary:B")`. Their children MUST follow c0017's `CANONICAL_ORDER["segment"]`, and their net form the board's own (c0017, "Net form per target").
- **Text insertion.** The board MUST be parsed with `sexpr.parse_bytes`, so invalid UTF-8 raises `FormatError`, and the canary MUST be inserted as UTF-8 text at the byte offsets of the parsed nodes: in the numbered form, two `net` rows with fresh numbers before the root child that follows the last root `net` row; the segments before the root's closing parenthesis. Every other byte and every net number MUST be kept.
- **Proven per major.** `CANARY_SUPPORT` MUST hold exactly the majors whose committed probe files record `check-canary-fired` = `present` and `check-canary-broken` = `absent`, and `CANARY_TWO_RUN` every major that records `check-canary-neutral` = `different` and every major on which the register row of `H-K-CHECK-CANARY` records a corpus board whose stripped canary report differs from its plain report in runs that each repeat. Both start empty.
- **Inconclusive.** The state MUST be `inconclusive` with one reason: `placement-unproven` (the major is not in `CANARY_SUPPORT`), `selector-unproven`, `clearance-ignored` (the project sets `/board/design_settings/rule_severities/clearance` to `ignore`), `names-taken` (the rule name, a canary net name or a canary uuid is already used), `board-unparsed` (`inject_board` raised `FormatError`), `extent-too-large` (X + 2 mm over 2 000 mm), `no-front-copper`, `no-report` (KiCad wrote no report), or `clearance-limit` (decided after the run: the report of the canary run holds no canary pair and is saturated, see **Report limit**). When the state is decided before the run, the copy set MUST be passed unchanged.
- **Verdict.** `canary_fired(report)` MUST be true when a `clearance` violation's items are exactly the two canary uuids. `strip_canary(report)` MUST remove every violation and unconnected item that names a canary uuid and MUST return their count.
- **Report limit.** `kicad-cli` stops reporting `clearance` violations near 499 per run, and on a board with more the canary pair competes for a place, so it can be missing from a run that loaded the rules (`H-K-DRC-LIMIT`). `CLEARANCE_REPORT_LIMIT` MUST be `499`. `clearance_saturated(report) -> bool` MUST be true when the report holds at least `CLEARANCE_REPORT_LIMIT` violations of type `clearance`, the canary's own included. When the report of the canary run holds no canary pair, the state MUST be `inconclusive` with reason `clearance-limit` if `clearance_saturated` is true for that report, and `absent` otherwise. The oracle MUST NOT repeat the canary run to get another answer.
- **Oracle.** `KicadOracle(cli)` MUST have `name = "kicad"`, `version()`, `major()` and `drc(project) -> DrcOutcome`. `drc` MUST stage the canary board and rules in a private temporary folder outside the project and call `KicadCli.drc(<staged or original board>, files=<project.files without the board key, the rules entry replaced by the staged rules when staged>)`, so the board is passed only positionally. It MUST read the report with c0017's `read_drc_report` and strip the canary. `tool_writes` MUST be the names in `CliRun.outputs` other than the report. `oracle.EVIDENCE` MUST start `INFERRED` (`H-K-CHECK-COPYSET`, `H-K-CHECK-CANARY`) and MUST become `KICAD-VERIFIED` only when both rows are `KICAD-VERIFIED (9.0.x, 10.0.x)`. `DrcOutcome.evidence` MUST be the level and hypotheses of `Evidence.combine(drc.EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>` when a report exists, and `UNVERIFIED` otherwise. On a major where a row is refuted, it MUST cite the row's latest registered successor instead (`H-K-CHECK-CANARY-3` today). It MUST NOT pass `--exit-code-violations`.
- **Neutrality.** `H-K-CHECK-CANARY` MUST be settled on both majors. A major in `CANARY_TWO_RUN` MUST run DRC twice (a plain run gives the report, the canary run gives the verdict), and the register row MUST record it.

#### Scenario: Canary fires
- **GIVEN** the authored built project and the native `two_layer` project, each with a one-rule `<stem>.kicad_dru`
- **WHEN** `uv run pytest tests/kicad/check/test_canary.py::test_canary_fires` runs on 9.0.9 and on 10.0.6
- **THEN** each report holds exactly one `clearance` violation between the two canary uuids, and the probe `check-canary-fired` records `present`

#### Scenario: Canary is neutral
- **GIVEN** the same projects
- **WHEN** `uv run pytest tests/kicad/check/test_canary.py::test_canary_neutral` compares a canary run, stripped, with a run without the canary
- **THEN** the multisets of (type, severity, excluded, sorted item uuids) are equal, and the probe `check-canary-neutral` records `equal`

#### Scenario: Two runs on large boards
- **GIVEN** on 10.0.6 the 21 readable non-heavy demo boards with a `{}` project and a `(version 1)` rules file, where the canary tracks change other violations
- **WHEN** `uv run pytest tests/kicad/check/test_canary.py::test_two_run_demo_boards` runs `KicadOracle.drc` on each
- **THEN** the report, from the plain run, holds no canary item (`canary_removed` = 0), and the canary state is `fired`, or `inconclusive` with reason `clearance-limit` on a board whose report is saturated (`kicad-demo-10-0-6-pcb-01` and `-13`); on every other board it is `fired`

#### Scenario: Broken rules silence the canary
- **GIVEN** `tests/data/kicad/rules/broken.kicad_dru` as `<stem>.kicad_dru` (`ten_only.kicad_dru` on 9.0.9 if `H-K-DRU-QUOTE` is refuted there)
- **WHEN** `uv run pytest tests/kicad/check/test_canary.py::test_canary_broken_rules` runs on both majors
- **THEN** the report holds no canary violation, the state is `absent`, and the probe `check-canary-broken` records `absent`

#### Scenario: Ignored clearance severity silences the canary
- **GIVEN** the authored built project whose `<stem>.kicad_pro` sets `/board/design_settings/rule_severities/clearance` to `ignore`
- **WHEN** `uv run pytest tests/kicad/check/test_canary.py::test_canary_ignored` runs the canary copy on both majors, and `KicadOracle.drc` runs on the same project
- **THEN** the report holds no canary violation, the probe `check-canary-ignored` records `absent`, and the oracle's state is `inconclusive` with reason `clearance-ignored`

#### Scenario: Support follows the probe files
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_canary.py -k support` reads `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`
- **THEN** `CANARY_SUPPORT` and `CANARY_TWO_RUN` equal the majors that the recorded `check-canary-*` outcomes give

#### Scenario: Unproven major
- **GIVEN** `CANARY_SUPPORT` patched to an empty set and a fake `kicad-cli`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k unproven` runs `KicadOracle.drc` on the authored project
- **THEN** the state is `inconclusive` with reason `placement-unproven`, and the board and rules file passed to `kicad-cli` are byte-equal to the originals

#### Scenario: User bytes kept
- **GIVEN** the bytes of `tests/data/kicad/board/two_layer.kicad_pcb`, and a copy with byte `0xFF` inside a string
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_canary.py -k inject` calls `inject_board` twice
- **THEN** both results are equal, removing the inserted spans gives the original bytes, and every net number is unchanged; the copy raises `FormatError` (`invalid UTF-8`), never `UnicodeDecodeError`

#### Scenario: Names already taken
- **GIVEN** a board that already has a net named `FENOLITE_CANARY_A`, and `CANARY_SUPPORT` and `SELECTOR_SUPPORT["net"]` patched to hold the fake's major
- **WHEN** `KicadOracle.drc` runs on its project with a fake `kicad-cli`
- **THEN** the state is `inconclusive` with reason `names-taken`, and the report is still read

#### Scenario: Staging outside the project
- **GIVEN** a fake `kicad-cli` that records its arguments and writes `x.kicad_prl`, and `CANARY_SUPPORT` and `SELECTOR_SUPPORT["net"]` patched to hold its major
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py` runs `KicadOracle.drc` on the authored project
- **THEN** the copied rules file starts with the user's bytes and contains `fenolite_check_canary`, no argument is `--exit-code-violations`, the project folder snapshot is unchanged, and `tool_writes` is `("x.kicad_prl",)`

#### Scenario: A saturated report gives no verdict
- **GIVEN** a fake `kicad-cli` whose canary run reports 499 `clearance` violations and no canary pair, and another whose canary run reports 498
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k saturated` runs `KicadOracle.drc` on each
- **THEN** the first state is `inconclusive` with reason `clearance-limit`, the second is `absent`, and each fake saw two `pcb drc` runs

### Requirement: Subcommand matrix from help text
`fenolite.backends.kicad.helpmatrix` SHALL tell which `kicad-cli` subcommands and options exist by reading `kicad-cli <words> --help` pages, run through c0009's `KicadCli`, because even `--help` writes a configuration folder (observed on 10.0.6).
- `parse_help(text) -> HelpPage | None` MUST read the `Usage:` line: its `{a,b,…}` group gives a group's subcommands, and its `[--name …]` groups give a leaf's long options. It MUST return `None` when no `Usage:` line is found. The grammar MUST be recorded in `docs/formats/kicad/cli.md` from observed runs (`H-K-CLI-HELP`); no KiCad or argument-parser source is read, and unit tests use authored synthetic pages.
- `MATRIX` MUST be a closed tuple of `MatrixEntry(command, options)`: `pcb drc` (`--format`, `--severity-all`, `--schematic-parity`, `--refill-zones`, `--save-board`), `pcb upgrade`, `pcb import`, `pcb render`, `pcb export ipcd356`, `pos`, `svg`, `gerbers`, `drill`, `stats`, `ipc2581` and `odb`, `fp upgrade`, `sym upgrade`, `sch erc`, `sch export netlist` and `jobset run`.
- `command_matrix(cli) -> CommandMatrix(version, rows, unparsed)` MUST give one boolean row per command and per option of `MATRIX`. A command exists when its last word is a subcommand of its parent's page; an option exists when it is an option of the command's page. A page that does not parse MUST be listed in `unparsed`, and its rows MUST be left out of `rows`.
- Each row MUST be recorded as the probe `check-help-<words>[-<option>]`, such as `check-help-pcb-drc-refill-zones`, with outcome `present` or `absent`.

#### Scenario: Group page
- **GIVEN** the authored page `Usage: kicad-cli pcb [--help] {drc,export,upgrade}`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_helpmatrix.py -k group` calls `parse_help`
- **THEN** `subcommands` is `{"drc", "export", "upgrade"}`

#### Scenario: Leaf page
- **GIVEN** the authored page `Usage: kicad-cli pcb drc [--help] [--format VAR] [--severity-all] INPUT_FILE`
- **WHEN** `parse_help` is called
- **THEN** `options` is `{"--help", "--format", "--severity-all"}`

#### Scenario: Page without a usage line
- **WHEN** `parse_help("Error: unknown command")` is called
- **THEN** it returns `None`

#### Scenario: Matrix matches the documented command sets
- **GIVEN** kicad-cli 9.0.9 in the pinned image and 10.0.6 locally
- **WHEN** `uv run pytest tests/kicad/check/test_help_matrix.py::test_matrix_matches_facts` runs on each
- **THEN** every `MATRIX` page parses; `pcb import`, `pcb upgrade` and `pcb drc --refill-zones` and `--save-board` are present exactly on 10.0.6 (agreeing with `H-K-00` and `H-K-01`); `pcb drc --format`, `--severity-all`, `pcb export ipcd356`, `pos` and `svg` are present on both; and every row is recorded as a `check-help-*` probe

### Requirement: Preserved layouts pass the oracle
`tests/kicad/lens/` (marker `needs_kicad`, major-aware) SHALL prove on the running `kicad-cli` that a rebuild keeps a layout edited outside Fenolite. Every case MUST build `examples/blink_2layer/design.py` into a temporary folder, edit its board with `tests/_layout_edit.py::edit_blink` (`D1` moved 4 mm to the right; one segment on `F.Cu` from `R1` pad 2 to a via, and one segment on `B.Cu` from that via to `D1` pad 2, all on `LED_A`, with fixed uuids), run `kicad-cli` through c0009's `KicadCli` on copies with an empty `KICAD_CONFIG_HOME`, and judge DRC only from the JSON report read with c0017's `read_drc_report`, never from the exit code.
- **Re-save.** On 10.0.6 (`kicad_min_major(10)`), the edited target-10 board MUST be re-saved with `pcb upgrade --force` (`KicadCli.upgrade_board`, S-0022) before the rebuild, as the stand-in for a save in the KiCad GUI. KiCad 9.0 has no `pcb upgrade` (S-0037), so the target-9 cases, and every case on 9.0.9, rebuild the edited text.
- **Survival.** On the rebuilt board, `pcb export pos` MUST give `D1` at its moved position and `U1` and `R1` at theirs, compared through c0009's `tests/kicad/board/_frame.py`. The rebuilt board MUST hold both segments and the via of the edit with the same uuids, end points, widths, layers and net name. Its DRC report MUST hold the same multiset of (type, severity) pairs and the same number of `unconnected_items` as the report of the edited (or re-saved) board.
- **Identity.** A second rebuild MUST write every file with the bytes of the first.
- **Downgrade.** A target-9 blink whose board was re-saved by 10.0.6 MUST be refused when rebuilt with `--kicad-version 9` (exit 7, `FEN-7002`), and MUST rebuild with `--kicad-version 10`.
- **Probes first.** Before the lens code exists, `tests/kicad/lens/test_lens_probes.py` MUST run, as probes of c0017's `tests/kicad/_probes.py`:
  - `lens-resave-t10` (major 10): `present` when, after `pcb upgrade --force` of the edited target-10 board, `D1` keeps its uuid and its `fenolite.path` property and the two segments and the via keep their uuids, and `absent` otherwise;
  - `lens-rewrite-t9` (majors 9 and 10) and `lens-rewrite-t10` (major 10): `equal` when the edited board, read with `read_board` and written by `write_board` for its own target, gives a DRC report with the same (type, severity) multiset and `unconnected_items` count as the edited board, and `different` otherwise.
  - Stop rules: an `absent` outcome stops the change until the matching keys are revised, because matching rests on them; a `different` outcome stops it until the changed types are explained and recorded in `docs/formats/kicad/drc.md`.
- `lens-keep-t9` (majors 9 and 10) and `lens-keep-t10` (major 10) MUST record the survival outcome: `equal` when every survival check holds and `different` otherwise.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json` (c0017), and built files MUST NOT be committed.

#### Scenario: Moved footprint survives a re-save on 10.0.6
- **GIVEN** the blink built for target 10 on the local KiCad 10.0.6, edited by `edit_blink` and re-saved with `pcb upgrade --force`
- **WHEN** `uv run pytest tests/kicad/lens/test_preserve_oracle.py::test_moved_footprint_survives` rebuilds it
- **THEN** `pcb export pos` gives `D1` 4 mm right of its `place()` position, both segments and the via are present with their uuids, and the DRC reports of the re-saved and rebuilt boards hold the same (type, severity) multiset and `unconnected_items` count

#### Scenario: Target 9 on 9.0.9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/lens -rA` runs in the `kicad-9` job
- **THEN** the target-9 cases run and pass on the edited text, and the re-save and downgrade cases are skipped by `kicad_min_major(10)`

#### Scenario: Second rebuild identical
- **GIVEN** the rebuilt folder of the re-saved target-10 case
- **WHEN** the build runs again
- **THEN** every file keeps its bytes

#### Scenario: Downgrade refused after a 10.0 save
- **GIVEN** the blink built for target 9, edited by `edit_blink` and re-saved by `pcb upgrade --force` on 10.0.6
- **WHEN** it is rebuilt with `--kicad-version 9 --dry-run`, and then with `--kicad-version 10 --confirm`
- **THEN** the first exits 7 with `FEN-7002`, and the second exits 0 with `D1` at its moved position

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds an outcome for `lens-resave-t10`, `lens-rewrite-t9`, `lens-rewrite-t10`, `lens-keep-t9` and `lens-keep-t10`

### Requirement: Netlist oracle from IPC-D-356
`fenolite.backends.kicad.oracle.KicadOracle.netlist(project, *, board) -> NetlistOutcome` SHALL run `pcb export ipcd356` through c0009's `KicadCli.export_ipcd356(<board path>, files=<project files without the board key>)`, read the text with `read_ipcd356`, and match its records to the pads of `board` with `fenolite.backends.kicad.padnets.match_pads(board, export)`.
- **Matching.** Via records (`ref == "VIA"` and an empty pin) MUST be skipped and counted. Every other `317` or `327` record MUST be paired with a distinct pad of `board` whose key (reference cut to `REF_WIDTH = 6` characters, pad number cut to `PIN_WIDTH = 4`) equals the record's, the nearest one within `BOUND_UNITS = 2` export units per axis, with positions taken relative to an anchor record whose key is unique in the export and in the board. This is c0009's comparison, moved from `tests/kicad/board/_frame.py` into `src`; `_frame.pad_report` MUST call `match_pads` and keep its behaviour.
- **Assignments.** `export_netlist(board, export) -> PadNetList` (source `export`) MUST give each paired record as `PadAssignment(f"{ref}-{number}", <record net>)`, with the pad's full reference and number. When two or more net names of `board` share their last `NET_WIDTH = 14` characters, the export cannot tell those nets apart, so every pad on them MUST become `Uncovered(element, "net-label-ambiguous")`.
- **Coverage.** A numbered pad of `board` that no record is paired with MUST become `Uncovered(element, "not-exported")`. A record paired with no pad MUST become `Uncovered(f"{ref}-{pin}", "unmatched-record")`, with the export's truncated fields.
- **Failures.** A non-zero exit, a missing export or a `FormatError` from `read_ipcd356` MUST give `netlist=None` and the message, and a timeout MUST give `outcome="timeout"`; no exception is raised, and nothing is written under `project.root`.
- **Evidence.** `NetlistOutcome.evidence` MUST be `Evidence.combine(padnets.EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>`, and `UNVERIFIED` without an export. `padnets.EVIDENCE` MUST start `INFERRED` (`H-K-NET-IPC`) and MUST become `KICAD-VERIFIED` only when that row is `KICAD-VERIFIED (9.0.x, 10.0.x)`.

#### Scenario: Authored project on both majors
- **GIVEN** c0013's authored built project for the running major
- **WHEN** `uv run pytest tests/kicad/check/test_netlist_oracle.py -k partition` runs on 9.0.9 and on 10.0.6
- **THEN** every numbered pad is assigned, `compare(board_netlist(design), outcome.netlist)` gives no difference, and the probe `netlist-partition` records `equal`

#### Scenario: Colliding long net names
- **GIVEN** an authored board whose nets `/A/LONG_SIGNAL_NAME` and `/B/LONG_SIGNAL_NAME` each join two pads
- **WHEN** `uv run pytest tests/kicad/check/test_netlist_oracle.py -k collision` runs `KicadOracle.netlist` on 9.0.9 and on 10.0.6
- **THEN** the four pads are `Uncovered` with reason `net-label-ambiguous`, the comparison with the board gives no difference, and the probe `netlist-label-collision` records `equal` when the export gives both nets one label and `different` otherwise

#### Scenario: Frame test unchanged
- **GIVEN** `tests/kicad/board/_frame.py::pad_report` calling `padnets.match_pads`
- **WHEN** `uv run pytest tests/kicad/board/test_board_frame.py -k ipcd356` runs with `FENOLITE_CENSUS_OUT` set, on 10.0.6 with the corpus and on 9.0.9 for the authored board
- **THEN** it passes, and the matched, via, truncated-key and ambiguous-key counts it writes equal those that `docs/evidence/kicad-board-read.md` records for 10.0.6

#### Scenario: Export failure
- **GIVEN** a fake `kicad-cli` whose `pcb export ipcd356` exits 3 without writing, and another that sleeps longer than the timeout
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k netlist` runs `KicadOracle.netlist`
- **THEN** the first gives `netlist is None` and a message, the second `outcome == "timeout"`, and neither raises

### Requirement: RT2 oracle
`fenolite.backends.kicad.oracle.KicadOracle.rt2(project) -> Rt2Outcome` SHALL produce the DRC reports that RT2 compares, without the check canary.
- **Re-dump.** The board MUST be read with `read_board`, rebuilt with `rebuild_board` and printed with `dumps`. The text MUST be staged under the board's own name in a private temporary folder outside `project.root`, removed afterwards.
- **Normalisation.** When the running major is 10 or more and the oracle was built with `rt2_normalise=True`, the default of `KicadOracle(cli, *, rt2_normalise=True)`, the original and the re-dump MUST each be re-saved with `KicadCli.upgrade_board` before DRC, and `normalised` MUST be true. On 9.0, which has no `pcb upgrade`, and with `rt2_normalise=False`, the files MUST be checked as they are, and `normalised` MUST be false.
- **Runs.** `KicadCli.drc` MUST run twice on the original, normalised or not, and once on the re-dump, each with the project files other than the board. `--exit-code-violations` MUST NOT be passed.
- **Repeats.** KiCad does not repeat its own report on boards with hundreds of violations (`H-K-RT2-STABLE-2`). When the entries of the re-dump report (`DrcReport.entries()`, with the run's temporary folder left out of the descriptions) differ from those of the first report of the original, the oracle MUST run DRC `RT2_REPEATS = 3` more times on the original and as many on the re-dump, appending the reports to `before` and to `repeats`, so that the caller can tell a difference from KiCad's own spread. When they are equal, no further run happens and `repeats` is empty.
- **Failures.** A board that Fenolite cannot read, a failed re-save or a run without a report MUST give the reports obtained so far and the message, and a timeout MUST give `outcome="timeout"`; no exception is raised.
- **Evidence.** `Rt2Outcome.evidence` MUST be `Evidence.combine(drc.EVIDENCE, RT2_EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>`, further combined with `NORMALISE_EVIDENCE` (`KICAD-VERIFIED`, `H-K-FMT-RESAVE`) when `normalised` is true, and `UNVERIFIED` when a report is missing. `RT2_EVIDENCE` MUST start `INFERRED` (`H-K-RT2-STABLE`) and MUST become `KICAD-VERIFIED` only when that row is `KICAD-VERIFIED (9.0.x, 10.0.x)`.

#### Scenario: Normalised on 10
- **GIVEN** a fake `kicad-cli` whose `version` prints `10.0.6` and that records its arguments
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k rt2` runs `KicadOracle(cli).rt2(project)` on the authored project
- **THEN** the fake saw two `pcb upgrade --force` runs and three `pcb drc` runs, `normalised` is true, and `before` holds two reports

#### Scenario: No normaliser on 9
- **GIVEN** the same fake printing `9.0.9`
- **WHEN** `rt2` runs
- **THEN** the fake saw no `pcb upgrade` run and three `pcb drc` runs, and `normalised` is false

#### Scenario: Both sides repeated when the re-dump differs
- **GIVEN** a fake `kicad-cli` printing `9.0.9` whose third `pcb drc` run writes one violation more than the others
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k repeats` runs `rt2`
- **THEN** the fake saw nine `pcb drc` runs, `before` holds five reports and `repeats` three; with equal reports it saw three runs and `repeats` is empty

#### Scenario: Normalisation turned off
- **GIVEN** the 10.0.6 fake and `KicadOracle(cli, rt2_normalise=False)`
- **WHEN** `rt2` runs
- **THEN** no `pcb upgrade` run happens and `normalised` is false

#### Scenario: No canary and no writes
- **GIVEN** a fake that copies every board it receives to a log folder outside the project
- **WHEN** `rt2` runs on a project with a `<stem>.kicad_pro` and a `<stem>.kicad_dru`
- **THEN** no logged board holds a `FENOLITE_CANARY_A` net, the logged rules file equals the user's, and the project snapshot is unchanged

### Requirement: DRC finding facts proved per major
`tests/kicad/check/test_drc_facts.py` (markers `needs_kicad`, major-aware) SHALL settle `H-K-DRC-TYPES`, `H-K-PRO-SEV` and `H-K-DRC-UUID` on 9.0.9 and 10.0.6, with projects that `tests/kicad/check/_fixtures.py` writes into `tmp_path`, and SHALL record each outcome as a probe of c0017's `PROBES`:
- **Types.** The bridging-track project MUST give a `shorting_items` violation, the authored built project without its `R1`–`D1` track an `unconnected_items` entry, and the positive-control bench a `clearance` violation (probes `drc-type-shorting-items`, `drc-type-unconnected-items` and `drc-type-clearance`, outcome `present`). With `/board/design_settings/rule_severities/<type>` set to `ignore` in the project, the same run MUST give no entry of that type (probes `drc-type-<type>-ignored`, outcome `absent`). The `drc-type-clearance-ignored` run is the one exception to "Rules proofs carry a canary", because ignoring `clearance` also removes the canary's violation: it MUST follow a `drc-type-clearance` run of the same bench, on the same major and in the same session, whose canary fired; it MUST differ from that run only in the project key, which the test re-reads; and on 10.0.6 its report MUST list `clearance` in `ignored_checks` (design Decision 20).
- **Severities.** With the key set to `warning`, every entry of that type MUST have severity `warning`, and with `error`, severity `error` (probes `drc-sev-<type>-warning` and `drc-sev-<type>-error`, outcome `equal`). On 10.0.6 an ignored key MUST appear in `ignored_checks` (probes `drc-ignored-checks-<type>`, run on major 10 only); the 9.0.9.1 report schema has no such key (S-0056).
- **Item uuids.** Every item uuid of those entries MUST be a uuid of the written board, and the pad items MUST be the expected pads: `R1` pad 2 for the bridging track, and `R1` pad 2 and `D1` pad 2 for the missing track (probe `drc-item-uuids`, outcome `equal`).
- Oracle tests MUST assert on `run(…)`, and both probe files MUST be regenerated with `FENOLITE_PROBES_WRITE=1`.

#### Scenario: Types on both majors
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and 10.0.6 locally
- **WHEN** `uv run pytest tests/kicad/check/test_drc_facts.py -k types` runs on each
- **THEN** each of the three types is `present` with the default project and `absent` with its key set to `ignore`

#### Scenario: Severities follow the project
- **GIVEN** the bridging-track project with `shorting_items` set to `warning`
- **WHEN** `uv run pytest tests/kicad/check/test_drc_facts.py -k severities` runs on both majors
- **THEN** every `shorting_items` violation has severity `warning`, and `fenolite check` reports `kicad.drc.shorting-items` as a warning

#### Scenario: Ignored checks listed on 10
- **GIVEN** `kicad-cli` 10.0.6 and the bridging-track project with `shorting_items` set to `ignore`
- **WHEN** the same test runs
- **THEN** `report.ignored_checks` contains `shorting_items`

#### Scenario: Pads named by their file uuids
- **GIVEN** the bridging-track and missing-track projects
- **WHEN** `uv run pytest tests/kicad/check/test_drc_facts.py -k uuids` runs on both majors
- **THEN** the probe `drc-item-uuids` records `equal`, and `finding_issues` gives `where` values holding `R1-2`, and `D1-2` for the missing track

### Requirement: Corpus round trips RT0 to RT2
`tests/kicad/check/test_corpus_rt.py` (markers `needs_kicad`, `needs_corpus`, `slow`) SHALL run RT0, RT1 and RT2 over the corpus for v0.1 acceptance item 2.
- **Set.** On major 10: the 21 readable non-heavy demo boards (tags 10.0.6 and 9.0.9.1), and copies of `third-party-pcb-01`, `-02` and `-03` re-saved once with `KicadCli.upgrade_board` from the cached files (corpus-policy, "Upgraded copies keep their origin"). On major 9: exactly the rows tagged `rt2-9` (corpus-policy, "RT2 rows for KiCad 9.0").
- **Project.** Each board MUST be checked in a folder that c0013's `demo_project` writes into `tmp_path`, with a `{}` project and a `(version 1)` rules file; the cache MUST NOT be written.
- **Levels.** RT0 MUST hold: `tree_equal(parse(dumps(parse(t))), parse(t))`. RT1 MUST hold: `run_checks` with the stages `roundtrip` and `roundtrip.rt2` and `KicadOracle(cli, rt2_normalise=…)` gives `roundtrip` status `ok` with `opaque_equal` true, so `opaque_count` reappears after the write. RT2 MUST never fail: `roundtrip.rt2` has status `ok`, and either `summary.holds` is true or the stage says that RT2 is not judged (`summary.judged` false with `summary.unstable` above 0), because KiCad did not repeat its own report on that board. `rt2_normalise` MUST be false for `third-party-pcb-02`, whose two upgrades differ (`H-K-FMT-RESAVE`), and true otherwise.
- **Record.** For each board, the three verdicts, `opaque_count`, `normalised`, `judged`, `runs`, `before`, `after`, `unstable`, `differences` and the seconds MUST be written through `tests/_boards.py::census` and copied into `docs/evidence/kicad-rt2.md`, as ids and counts only. The page MUST name the boards on which RT2 was not judged.
- **Missing rows.** On major 9 with `kicad` in `FENOLITE_REQUIRE`, a cache that is present but lacks an `rt2-9` row MUST fail the test, naming the row, instead of skipping that row. An absent cache MUST keep the `needs_corpus` skip of corpus-policy "Skip markers"; in the `kicad-9` job the fetch step fails first when a row cannot be fetched (`ci-baseline`, "KiCad 9.0 oracle job").

#### Scenario: Every board on 10.0.6
- **GIVEN** the `rt0` corpus cached and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/check/test_corpus_rt.py -rA` runs
- **THEN** all 24 boards pass RT0 and RT1, RT2 holds or is not judged on each and fails on none, and `third-party-pcb-02` reports `normalised` false

#### Scenario: The rt2-9 rows on 9.0.9
- **GIVEN** the `kicad-9` job with the `rt2-9` rows cached
- **WHEN** its `uv run pytest tests/kicad -q -rA` step runs the test
- **THEN** the five boards pass RT0 and RT1, RT2 holds or is not judged on each with `normalised` false, and the other rows are skipped

#### Scenario: Missing row on 9.0
- **GIVEN** `kicad-cli` 9.0.9, `FENOLITE_REQUIRE=kicad`, and a cache that holds four of the five `rt2-9` rows
- **WHEN** the test runs
- **THEN** it fails naming the fifth row

#### Scenario: Absent cache on 9.0
- **GIVEN** `kicad-cli` 9.0.9, `FENOLITE_REQUIRE=kicad`, and `FENOLITE_CORPUS_CACHE` naming an empty folder
- **WHEN** the test runs
- **THEN** it is skipped with the message `run: uv run python tools/corpus_fetch.py`

#### Scenario: Cache and repository untouched
- **WHEN** the test runs on either major
- **THEN** `git status --porcelain` and the SHA-256 of every cached file are unchanged afterwards

### Requirement: Export runs through the package runner
`KicadCli.export(args, board, *, files=None, out) -> CliRun` and `KicadCli.render(board, *, side, width, height, files=None) -> CliRun` SHALL run `kicad-cli` through `KicadCli.run`: inputs copied to a fresh temporary directory, the isolated environment, and the created files returned in `CliRun.outputs`.
- `export` MUST create the folder `out` inside the run directory before the run, so that the run does not depend on `kicad-cli` creating it.
- Neither method MUST raise for a non-zero exit; the caller reads `returncode`.
- `KicadOracle.plot(project) -> PlotOutcome` MUST run the views of "Render views" on the project's copy set and return, per view, its name, size and SHA-256; a view that fails MUST be absent from `views` and named in `message`. The SHA-256 of an SVG view MUST leave out its `<title>` line, where `kicad-cli` 9.0 writes the date, so that two plots of one board give equal outcomes.
- `backends.base` MUST gain `PlotView`, `PlotOutcome` and the protocol `Plotter`, all frozen dataclasses or protocols without a dependency on `backends.kicad`.

#### Scenario: Output folder exists for the run
- **GIVEN** a fake `kicad-cli` that fails when its `-o` folder is missing
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_cli_export.py` calls `KicadCli.export([...], board, out="gerbers")`
- **THEN** the run exits 0 and `outputs` holds the fake's files under `gerbers/`

#### Scenario: Non-zero exit is returned
- **GIVEN** a fake `kicad-cli` that exits 1 for `pcb render`
- **WHEN** `KicadCli.render(board, side="top", width=400, height=300)` runs
- **THEN** no exception is raised and `returncode` is 1

#### Scenario: Plot outcome holds no bytes
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k plot` calls `KicadOracle.plot` with a fake
- **THEN** each view holds `name`, `bytes` (a count) and `sha256`, and the outcome holds no temporary path

### Requirement: Exports are probed on both majors
`H-K-EXPORT-FILES`, `H-K-EXPORT-REPEAT` and `H-K-EXPORT-RENDER` SHALL be settled on `kicad-cli` 9.0.9 and 10.0.6 by `tests/kicad/export/test_export_probes.py` before `exports.plan` relies on them, as the probes `export-files-<kind>`, `export-repeat-<kind>` (for `gerbers`, `drill`, `pos`, `ipcd356`), `export-render-png` and `export-render-svg`.
- `test_files` MUST compare the produced file names with the expected set for `two_layer.kicad_pcb` and for the authored project.
- `test_repeat` MUST export twice and compare `content_sha256` per file; it MUST also record, per kind, whether the two runs were byte-equal, in `docs/evidence/kicad-export.md`.
- `test_render` MUST read the PNG header: the width and the height MUST be above zero and at most the requested ones (`kicad-cli` 9.0.9 and 10.0.6 write 368 × 280 for 400 × 300).
- A line that differs between two runs and matches no prefix in `VOLATILE_PREFIXES` MUST fail `test_repeat` and name the line's first 40 bytes.
- `tests/kicad/export/test_export_oracle.py::test_blink_loop` MUST run `fenolite export --all --manifest --confirm` and `fenolite render --svg --png --confirm` on the built blink on both majors and check the manifest against the written files.

#### Scenario: File sets
- **WHEN** `uv run pytest tests/kicad/export/test_export_probes.py::test_files` runs on 9.0.9 and on 10.0.6
- **THEN** the four `export-files-*` probes record `equal` on both

#### Scenario: Content hashes repeat
- **WHEN** `uv run pytest tests/kicad/export/test_export_probes.py::test_repeat` runs on both majors
- **THEN** the four `export-repeat-*` probes record `equal`

#### Scenario: Headless render
- **WHEN** `uv run pytest tests/kicad/export/test_export_probes.py::test_render` runs on 10.0.6 and inside the pinned 9.0.9 image
- **THEN** `export-render-svg` records `present` on both, and `export-render-png` records `present` or `absent` per major with the tool's message

#### Scenario: Blink exports on both majors
- **WHEN** `uv run pytest tests/kicad/export/test_export_oracle.py::test_blink_loop` runs on both majors
- **THEN** the manifest lists every written artefact with its hash, and the built project folder is unchanged

### Requirement: Board-frame queries agree with kicad-cli
`tests/kicad/frame/` (marker `needs_kicad`, major-aware) SHALL check `board_pads` and `placed_extent` against the running `kicad-cli` on the frame bench `tests/kicad/frame/_framebench.py`. The bench MUST hold `Mini_R_0603`, `Mini_LED_THT_3mm`, `Mini_QFP-32_7x7mm_P0.8mm` (from `Mini_v9.pretty` for target 9, `Mini.pretty` for target 10) and the authored CC0 footprints of `tests/data/libs/Frame.pretty`, placed with `place_footprint` at 0°, 90°, 180°, 270° and 30° on both sides (a footprint that `place_footprint` refuses to mirror, the trapezoid one, on the top side only), each pad on its own net, written for the running major with a project `fp-lib-table`, a rules file that sets every clearance to 0.2 mm (written with c0018's `write_rules`), and an empty `KICAD_CONFIG_HOME`. DRC MUST be judged only from the JSON report read with `read_drc_report`.
- **Positions** (`test_pad_positions`): every non-via `317` and `327` record of `pcb export ipcd356` MUST match one `board_pads` record by reference and pin, the differences between records MUST equal those of the records' `position` within ±2 export units per axis, and within ±1 unit for pads whose stored angle is a multiple of 90° (the export rounds each record to a unit), and the `R` field MUST equal `(−rotation) mod 360°` in degrees. This extends the data of `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE` and `H-G-PAD-ANGLE-ABS` to 180° and 270°.
- **Copper entries** (`H-G-FRAME-SHAPE`): for each `circle`, `rect`, `oval`, `roundrect` and filled-polygon `custom` pad of the `Frame_Shapes` placements of the bench (pads with free room around them), two probe vias of another net, one along an edge normal and one along a corner diagonal, MUST be placed where their exact distance to the pad's copper entries is 0.2 mm minus 20 µm (near board) or plus 20 µm (far board), found by bisection with exact integer tests. On the near board each probe MUST give exactly one `clearance` violation naming its uuid; on the far board none MUST.
- **Extents** (`H-G-FRAME-CRTYD-2`, the successor of `H-G-FRAME-CRTYD`): pairs of bench footprints whose `placed_extent` faces overlap by 20 µm MUST give one `courtyards_overlap` violation per pair, and pairs 20 µm apart none, for rectangle, line-loop and circle courtyards on both sides, at 0° and 30°. For circle courtyards the overlap MUST be 40 µm: their extent is an outer polygon, and KiCad reports two circle courtyards only beyond about 10 µm of real overlap (`docs/evidence/kicad-frame.md`). The second footprint of a pair is moved along X from the first contact, found by bisection with `polygons_intersect`.
- **Probes**, in `tests/kicad/_probes.py` for majors 9 and 10: `pcb-frame-shape-near` (`present` when every near probe fires once, `different` otherwise), `pcb-frame-shape-far` (`absent` when none fires), `pcb-frame-crtyd-overlap` (`present` when every pair fires once) and `pcb-frame-crtyd-gap` (`absent` when none fires). An outcome other than the expected one MUST stop the change until the entry or extent rule is revised and the row is refuted with a successor.

#### Scenario: Pad positions on both majors
- **GIVEN** the frame bench written for the running major
- **WHEN** `uv run pytest tests/kicad/frame/test_frame_oracle.py::test_pad_positions` runs on the local KiCad 10.0.6 and in the `kicad-9` job
- **THEN** every pad record matches, including the footprints at 180° and 270° on the bottom

#### Scenario: Clearance canary
- **WHEN** `uv run pytest tests/kicad/frame/test_frame_oracle.py::test_shape_canary` runs
- **THEN** `run("pcb-frame-shape-near")` is `present` and `run("pcb-frame-shape-far")` is `absent`

#### Scenario: Courtyard canary
- **WHEN** `uv run pytest tests/kicad/frame/test_frame_oracle.py::test_courtyard_canary` runs
- **THEN** `run("pcb-frame-crtyd-overlap")` is `present` and `run("pcb-frame-crtyd-gap")` is `absent`

### Requirement: Script copper passes the oracle
`tests/kicad/frame/` SHALL prove on the running `kicad-cli` that copper resolved from intents loads, keeps its uuids and connects its pads, using builds of `examples/blink_routed/design.py`.
- **Uuids** (`H-G-FRAME-UUID`), probes run before `resolve_copper` exists, on a board whose tracks and vias carry copper uuids set in the test: `pcb-frame-uuid-9` (majors 9 and 10: the target-9 board loads, `load`), `pcb-frame-uuid-10` (major 10: the target-10 board loads) and `pcb-frame-uuid-keep` (major 10: after `pcb upgrade --force`, every track and via keeps its uuid, `equal`). A `reject` or `different` outcome MUST stop the change until the uuid scheme is revised (design, "Risks").
- **Route** (`H-G-FRAME-ROUTE`): `pcb-frame-route` (majors 9 and 10: the routed blink's report holds no `unconnected_items` entry and no `clearance` or `shorting_items` violation naming a script item, `absent`), `pcb-frame-route-cut` (majors 9 and 10: the same board without the `led_a` segment that reaches `D1` gives exactly one unconnected item, `present`) and `pcb-frame-route-moved` (majors 9 and 10: the build whose `D1` was moved 4 mm along Y by `tests/_layout_edit.py::move_footprint` and then rebuilt (a move along X brings the `led_a` track within 0.06 mm of `D1` pad 1, a real clearance violation), `absent` as for `pcb-frame-route`; on major 10 the target-10 board is re-saved with `pcb upgrade --force` before the rebuild, and on major 9 the edited target-9 text is rebuilt, because 9.0 has no `pcb upgrade` (S-0037)).
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, and built files MUST NOT be committed.

#### Scenario: Copper uuids survive a re-save
- **WHEN** `uv run pytest tests/kicad/frame/test_copper_oracle.py -k uuid` runs on the local KiCad 10.0.6
- **THEN** `pcb-frame-uuid-9` and `pcb-frame-uuid-10` are `load` and `pcb-frame-uuid-keep` is `equal`

#### Scenario: Routed nets are connected
- **WHEN** `uv run pytest tests/kicad/frame/test_copper_oracle.py -k route` runs on 10.0.6 and in the `kicad-9` job
- **THEN** on both majors `pcb-frame-route` and `pcb-frame-route-moved` are `absent` and `pcb-frame-route-cut` is `present`

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds an outcome for each `pcb-frame-*` probe of major 10

### Requirement: Library table probes
`tests/kicad/libs/test_lib_tables_drc.py` (marker `needs_kicad`, major-aware) SHALL settle the library-resolution hypotheses with the probes below. Each probe SHALL be registered in `tests/kicad/_probes.py` for majors 9 and 10, and SHALL run `KicadCli.drc(board, files=…, env=…)` ("DRC verdicts come from the JSON report"), never `KicadCli.run` directly.
- **Board.** Every probe uses c0017's altered control `_bench.control(target, _bench.CONTROLS["unmirrored"])`, written for the running major by `_bench.write(…, table=False)`. Its one footprint, `Mini:Mini_QFP-32_7x7mm_P0.8mm`, differs from its library footprint, so a found library gives exactly one `lib_footprint_mismatch`. `<lib>` is a copy of `_triad.library(target)`: `Mini.pretty` on 10, `Mini_v9.pretty` on 9. Every table uses the syntax of the running major.
- **Outcome.** It names whether `lib_footprint_issues` is reported:
  - `absent`: no `lib_footprint_issues` and exactly one `lib_footprint_mismatch`, so the library was found and compared;
  - `present`: at least one `lib_footprint_issues` and no `lib_footprint_mismatch`;
  - `different`: any other report; `reject`: no report; `timeout`: the run timed out;
  - `inconclusive`: for every probe, when `pcb-libdrc-missing-table` is not `present`.
- **Probes.**

| probe id | layout |
|---|---|
| `pcb-libtable-relpath-project` | project row `Mini` with uri `<lib>` (relative, no variable); `<lib>` lies next to the board, in the working directory |
| `pcb-libtable-relpath-nested` | project row `Sub` of type `Table` with uri `${KIPRJMOD}/sub/fp-lib-table`; that nested table's row `Mini` has uri `<lib>`, and `<lib>` lies next to the board |
| `pcb-libtable-relpath-nested-folder` | the same, with the nested row's uri `../<lib>`: relative to the nested table's folder |
| `pcb-libtable-relpath-global` | no project table; `env` sets `KICAD_CONFIG_HOME` to a folder D whose `<M>.0/fp-lib-table` has the row `Mini` with uri `<lib>`; `<lib>` lies next to the board, not next to that table |
| `pcb-libtable-relpath-cwd` | board and project table (row `Mini`, uri `<lib>`) in the subfolder `proj/` of the working directory; `<lib>` lies in the working directory |
| `pcb-libtable-relpath-project-folder` | the same, with `<lib>` in `proj/`, next to the board |
| `pcb-libtable-nested` | the same `Table` row; the nested row `Mini` has uri `${KIPRJMOD}/<lib>` |
| `pcb-libtable-fallback` | project row `Mini` with uri `${KICAD9_FOOTPRINT_DIR}/<lib>`; `env` sets `KICAD10_FOOTPRINT_DIR` to a folder holding `<lib>` |
| `pcb-libtable-fallback-defined` | the same, and `env` also sets `KICAD9_FOOTPRINT_DIR` to an empty folder |
| `pcb-libtable-confighome` | no project table; `env` sets `KICAD_CONFIG_HOME` to a folder D whose `<M>.0/fp-lib-table` has the row `Mini` with the absolute path of a folder `<lib>` |
| `pcb-libtable-confighome-flat` | the same table at `D/fp-lib-table` |
| `pcb-libtable-common` | `env` sets `KICAD_CONFIG_HOME` to D; `D/<M>.0/kicad_common.json` defines `FENOLITE_PROBE_LIBS`, in `environment.vars`, as a folder holding `<lib>`; project row `Mini` with uri `${FENOLITE_PROBE_LIBS}/<lib>` |
| `pcb-libtable-common-env` | the same, and `env` also sets `FENOLITE_PROBE_LIBS` to an empty folder |

- **Working directory.** `KicadCli.drc` runs `kicad-cli` in the folder of the board. The two probes whose project is the subfolder `proj/` therefore pass the arguments of `KicadCli.drc`, with the board named `proj/<board>`, to `KicadCli.run`; every other probe runs through `KicadCli.drc(board, files=…, env=…)`.
- **Configuration files.** D is passed as the `env` entry `KICAD_CONFIG_HOME` of `KicadCli.drc`, because the runner refuses `files` under its `config` folder. D is always a new, empty temporary folder, never the user's configuration folder. Before writing `kicad_common.json`, the `common` probes run `KicadCli.drc` once with D empty. When that run wrote `D/<M>.0/kicad_common.json`, the probe adds the variable to its `environment.vars`; otherwise it writes `{"environment": {"vars": {…}}}`. Which case occurred SHALL be written with `_boards.census` to the file named by `FENOLITE_CENSUS_OUT`.
- **Observation.** `test_common_file_layout` SHALL run `KicadCli.drc` once with `env` setting `KICAD_CONFIG_HOME` to an empty folder under `tmp_path`, and record with `_boards.census` whether `<M>.0/kicad_common.json` was written and whether its `environment` object holds `vars`. It records key names only, never values, and asserts nothing. No KiCad source code is read for the layout of this file.
- **Isolation.** Tested variables reach `kicad-cli` only through the `env` argument of `KicadCli.drc`, and the runner still drops the caller's `KICAD*` variables. Every folder outside the runner's temporary directory is a temporary folder of the probe, removed afterwards. Nothing is written to the repository, except the results files with `FENOLITE_PROBES_WRITE=1`.
- **Settling on 10.0.6.** `test_relpath` asserts `absent` for `pcb-libtable-relpath-project`, `-relpath-nested`, `-relpath-global` and `-relpath-cwd`, and `present` for `pcb-libtable-relpath-nested-folder` and `-relpath-project-folder`: a relative uri is resolved against the working directory, and neither the folder of the table nor the project folder counts. `test_fallback` asserts `absent` for `pcb-libtable-fallback` and `present` for `pcb-libtable-fallback-defined`. `test_nested` asserts `absent`. `test_config_home` asserts `absent` for `pcb-libtable-confighome` and `present` for `pcb-libtable-confighome-flat`. `test_common_vars` asserts `absent` for `pcb-libtable-common` and `present` for `pcb-libtable-common-env`. An `inconclusive` outcome MUST fail the test with a message naming `H-K-LIB-DRC`.
- **Settling on 9.0.9.** `test_nested` asserts `present` for `pcb-libtable-nested`, on the authored board without corpus. Every other 9.0.9 outcome is recorded by its probe id and MUST NOT fail a test.

#### Scenario: Nested table on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6, where `pcb-libdrc-missing-table` is `present`
- **WHEN** `uv run pytest tests/kicad/libs/test_lib_tables_drc.py -k nested` runs
- **THEN** `pcb-libtable-nested` is `absent`: the report holds no `lib_footprint_issues` and exactly one `lib_footprint_mismatch`

#### Scenario: Nested table on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the `kicad-9` job, and a probe that uses no corpus file
- **WHEN** `uv run pytest tests/kicad/libs/test_lib_tables_drc.py -k nested` runs
- **THEN** `pcb-libtable-nested` is `present`

#### Scenario: Relative uris
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `test_relpath` runs
- **THEN** `pcb-libtable-relpath-project`, `pcb-libtable-relpath-nested`, `pcb-libtable-relpath-global` and `pcb-libtable-relpath-cwd` are `absent`, and `pcb-libtable-relpath-nested-folder` and `pcb-libtable-relpath-project-folder` are `present`

#### Scenario: Fallback only for an undefined variable
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `test_fallback` runs
- **THEN** `pcb-libtable-fallback` is `absent` and `pcb-libtable-fallback-defined` is `present`

#### Scenario: Configuration folder of the major
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `test_config_home` runs
- **THEN** `pcb-libtable-confighome` is `absent` and `pcb-libtable-confighome-flat` is `present`

#### Scenario: Process variable wins over kicad_common.json
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `test_common_vars` runs
- **THEN** `pcb-libtable-common` is `absent` and `pcb-libtable-common-env` is `present`

#### Scenario: Layout of kicad_common.json observed
- **GIVEN** `kicad-cli` 10.0.6, an empty folder under `tmp_path` as `KICAD_CONFIG_HOME`, and `FENOLITE_CENSUS_OUT` naming a file under a temporary folder
- **WHEN** `test_common_file_layout` runs
- **THEN** that file records whether `10.0/kicad_common.json` was written and whether its `environment` object holds `vars`, with key names only

#### Scenario: Silent library check
- **GIVEN** a run in which `pcb-libdrc-missing-table` is not `present`
- **WHEN** a `pcb-libtable-*` probe runs on 10.0.6
- **THEN** its outcome is `inconclusive`, and the test that asserts on it fails naming `H-K-LIB-DRC`

#### Scenario: Outcomes pinned per version
- **GIVEN** the committed `docs/evidence/kicad/probes/10.0.6.json` and `docs/evidence/kicad/probes/9.0.9.json`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on 10.0.6 and on 9.0.9
- **THEN** it passes on both, and each file holds an outcome for every `pcb-libtable-*` id

#### Scenario: Repository untouched
- **WHEN** `uv run pytest tests/kicad/libs/test_lib_tables_drc.py` runs on 10.0.6
- **THEN** `git status --porcelain` is unchanged afterwards

### Requirement: Footprint fields pass the field oracle
`tests/kicad/board/test_field_oracle.py` (markers `needs_kicad`, major-aware) SHALL settle the field frames, the DRC items of fields and `place_outside` with `pcb drc` canaries on the running `kicad-cli`, and `tests/kicad/board/test_field_probes.py` SHALL record the same facts first, on boards written as text in the test.
- **Benches.** Boards MUST be built in the test through the model: `Mini_R_0603` and `Mini_QFP-32_7x7mm_P0.8mm` placed with `place_footprint` (from `Mini_v9.pretty` for target 9 and from `Mini.pretty` for target 10), references of ten characters in 1 mm text, fields set with `set_field` or `place_outside`, and an outline with optional cut-outs, written with `write_board` for target 9 on both majors and also for target 10 on 10.0.6. A bench MAY hold several footprints, each with its own cut-out, since every verdict is read from the items of one field. Each folder MUST hold a project file whose `board.design_settings.rules.min_silk_clearance` is 0.1 mm, and `KICAD_CONFIG_HOME` MUST be empty. Benches MUST NOT be committed.
- **Reading the report.** DRC MUST run through `KicadCli.drc`. A field's item MUST be matched by its uuid, the field's `native_ids["kicad"]`, and only `silk_edge_clearance` violations are judged.
- **Anchors.** A `Reference` that crosses the board edge, on top footprints at 0°, 30° and 90° and on bottom footprints at 0°, 30° and 90°, MUST give one `silk_edge_clearance` whose field item has the description `Reference field of <reference>` and the position that `field_anchor` gives, within 10 nm per axis (`H-K-FIELD-FRAME`, `H-K-FIELD-DRC`).
- **Moved inside.** Each of those fields moved inside the board with `set_field` MUST give no violation, in a report that holds the violation of a crossing control on the same board.
- **Angle.** On a footprint at 90° whose field anchor lies 2 mm below the top edge, a `Reference` at board angle 0° MUST give no violation, and one at board angle 90° MUST give one.
- **Justification and mirror.** With the anchor 1 mm inside the left edge, `h_justify` `left` MUST give no violation and `right` one on the top side, and the reverse for a mirrored field on the bottom side (`H-K-FIELD-JUSTIFY`).
- **Keep-upright.** A left-justified `Reference` at board angle 180°, with its anchor 1 mm inside the left edge, MUST give no violation, and one when the test inserts `(unlocked yes)` into its node.
- **Hidden.** A hidden `Reference` that crosses the edge MUST give no violation for it.
- **Outside.** For each `side`, on top and bottom footprints at 0°, 30° and 90°, a field set by `place_outside` with the default gap MUST give no violation on a board whose outline holds a cut-out equal to the box `B` of that footprint ("Footprint field helpers"), and a control MUST give one: its anchor lies 0.1 mm inside `B` on the top and bottom sides, and 1 mm inside `B` on the left and right sides, because sideways the ink of a text starts about 0.27 mm from its anchor (`H-K-FIELD-OUTSIDE`).
- **Silence on 9.0.** The crossing control written with `min_silk_clearance` 0 MUST be recorded under the probe `field-edge-zero`; the outcome expected is `absent` on 9.0.9 and `present` on 10.0.6, and it MUST NOT fail the test.
- **Re-save.** On 10.0.6, a target-10 bench whose fields were moved, turned, hidden, resized and justified MUST read back with equal fields after `pcb upgrade --force`, compared by the uuid of each property, since a re-save may write the footprints in another order (`H-K-FIELD-RESAVE`).
- **Probes.** Every outcome MUST be recorded under a `field-*` probe id of c0017's `PROBES` and compared with `docs/evidence/kicad/probes/<version>.json` in both KiCad jobs. When a probe contradicts the frame of `design-model` "Footprint fields", the change MUST stop until its design is amended.

#### Scenario: Anchor of a bottom field
- **GIVEN** `kicad-cli` 10.0.6 and a bottom `Mini_R_0603` at 30° whose `Reference` crosses the left edge
- **WHEN** `uv run pytest tests/kicad/board/test_field_oracle.py -k anchors` runs
- **THEN** the report holds one `silk_edge_clearance` whose item with the field's uuid lies within 10 nm of `field_anchor`

#### Scenario: Moved inside with a live control
- **GIVEN** the same bench on 9.0.9, with the field moved inside the board and a second footprint whose `Reference` crosses the edge
- **WHEN** the test runs
- **THEN** the report holds the control's violation and none for the moved field

#### Scenario: Mirror reverses the justification
- **GIVEN** a bottom footprint whose mirrored `Reference` has its anchor 1 mm inside the left edge
- **WHEN** DRC runs on each major with `h_justify` `left` and then `right`
- **THEN** `left` gives one violation and `right` none

#### Scenario: Outside the courtyard on both majors
- **GIVEN** the outside benches written for target 9
- **WHEN** `uv run pytest tests/kicad/board/test_field_oracle.py -k outside` runs on 10.0.6 and inside the 9.0.9 image
- **THEN** no field set by `place_outside` gives a violation, and every control gives one

#### Scenario: Silent edge check on 9.0
- **GIVEN** `kicad-cli` 9.0.9 and the crossing control with `min_silk_clearance` 0
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs
- **THEN** `field-edge-zero` matches the outcome recorded for 9.0.9, and no field test fails because of it

### Requirement: Zone settings pass the oracle
The meaning of zone settings SHALL be proved with `kicad-cli` on benches built through the model API and written by `write_board` for the running major. Every run MUST go through c0009's runner on copies. The probes MUST be recorded per version ("Probe results per kicad-cli version").
- **Bench.** `tests/kicad/zones/_zonebench.py` builds the zone canary: a two-layer 40 × 30 mm board; a `GND` pour on `F.Cu` over a 2 × 2 mm SMD pad and a 1.7 mm round THT pad on `GND`; a 1 × 1 mm SMD pad and a 1.7 mm THT pad on `SIG`; a closed `SIG` track ring around an island of the pour; and two `SIG` tracks that leave a 0.2 mm channel of pour between their clearances. Each case sets the zone settings, a pad's or a footprint's `zone_connect`, or a `.kicad_dru` rule.
- **Probes first (10.0.6).**
  - `zone-defaults-t10`: a zone written without `connect_pads`, `min_thickness` and `fill`, re-saved by `pcb upgrade --force`, holds the children that `zones.emit_settings(ZoneSettings(), filled=False, locked=False, major=10)` gives.
  - `zone-fat9`, on both majors: in the Gerber that `pcb export gerbers -l B.Cu` plots for `created_board()` written for target 9, the region of zone `GND_POUR` has the extreme coordinates of its fill polygon. A copy without `(filled_areas_thickness no)` reaches `min_thickness / 2` further on each side.
  - Stop rule: when either outcome differs, the defaults or the target-9 form are corrected from the observation before group 3 of the tasks starts.
- **Refill (10.0.6).** `pcb drc --refill-zones --save-board` runs on copies. The saved board is read with `read_board`, and its fills are measured with c0005's exact predicates (`point_in_ring`, exact crossings of segments):
  - A thermal zone gives four spokes, on the axes of the SMD pad and at 45° on the round THT pad, with the corners of the relief ring clear. `solid` puts every probe of both pads in the fill, and `none` puts none there. `thru_hole_only` is solid on the SMD pad and thermal on the THT pad.
  - A pad's `zone_connect` 0 to 3 overrides the zone. A footprint's `zone_connect` 2 makes its pads solid, unless a pad says otherwise.
  - The gap between the fill and each `SIG` pad lies in [c, c + 5 µm]. c is the larger of the zone clearance and the clearance that the `Default` class (0.2 mm) or a `.kicad_dru` rule gives.
  - The spoke width equals `thermal_spoke_width`, and the gap of the relief equals `thermal_gap`, each within 1 µm.
  - The island is removed for `always`, kept as an `island` fill for `never`, kept for `below_area` with 10 mm², and removed for `below_area` with 50 mm².
  - The channel is filled with `min_thickness` 0.15 mm, and empty with 0.25 mm.
  - A hatched fill of 1 mm bars and 1.5 mm holes at 0° has bars and holes of those widths within 5 µm.
- **9.0.9.** The board of every case, written for target 9, MUST load: `pcb drc` exits 0 and writes a report. `zone-fat9` MUST hold.
- **Build.** The blink pour variant of `design-dsl` "Zones in a build" MUST load on both majors. On 10.0.6, its refilled board MUST hold a `GND` fill on `B.Cu`.
- **Fact recorded for the copper check.** Probe `zone-clearance-drc`, on 10.0.6: `pcb drc` without refill reports a `clearance` violation for an authored fill 0.3 mm from a `SIG` pad when the zone clearance is 0.5 mm, and none when it is 0.1 mm. Fenolite's behaviour does not depend on this probe.

#### Scenario: Connection modes on 10.0.6
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/zones/test_zone_oracle.py -k connection -rA` runs
- **THEN** the thermal, solid, none and `thru_hole_only` cases and the pad and footprint overrides give the probe patterns above

#### Scenario: Clearance in force
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/zones/test_zone_oracle.py -k clearance -rA` runs
- **THEN** the measured gap lies in [c, c + 5 µm] for a zone clearance of 0.3 mm (c is 0.3 mm), for 0.1 mm (c is 0.2 mm, from the class), and for 0.3 mm with a 0.6 mm rule on `SIG` (c is 0.6 mm)

#### Scenario: Thermal geometry, islands and minimum thickness
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/zones/test_zone_oracle.py -k geometry -rA` runs
- **THEN** the spoke width, the relief gap, the four island cases, the two channel cases and the hatch widths match the rules above

#### Scenario: Defaults and the target-9 plot
- **WHEN** `uv run pytest tests/kicad/zones/test_zone_probes.py -rA` runs on 10.0.6, and in the pinned 9.0.9 image
- **THEN** `zone-defaults-t10` gives `equal` on 10.0.6, and `zone-fat9` gives `equal` on both majors

#### Scenario: Every form loads on 9.0.9
- **GIVEN** the pinned 9.0.9 image
- **WHEN** `uv run pytest tests/kicad/zones/test_zone_oracle.py -k load -rA` runs
- **THEN** every case board written for target 9, and the target-9 blink pour variant, load with exit 0 and a DRC report

#### Scenario: Probe outcomes pinned
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py -q` runs on 10.0.6 and in the 9.0.9 image
- **THEN** it passes, and `docs/evidence/kicad/probes/10.0.6.json` and `9.0.9.json` hold the outcomes of the `zone-*` probes of their major

### Requirement: Via re-net probe
`tests/kicad/copper/test_via_renet.py` (markers `needs_kicad`, major-aware) SHALL record on 9.0.9 and 10.0.6 what KiCad does with a via whose copper touches a track of another net (`H-K-VIA-RENET`). The benches MUST be built with c0018's `tests/kicad/rules/_rulebench.Builder`, written with `write_board` for the running major, with a `{}` project and the rules text `(version 1)` next to them. Each holds a 0.6 mm via of net `GND` whose disc overlaps a 0.25 mm `F.Cu` track of net `VIN` by 0.05 mm:
- **Padded.** The track ends on pad 1 of a placed `Mini_R_0603`, which is on `VIN`; there is no other `GND` copper. This is the reported case.
- **Tied.** The padded bench, and a `GND` track that joins the via to pad 1 of a second `Mini_R_0603`, on `GND`: both nets own a pad.
- **Dangling.** No footprint: the via and the track only.
- **Anchored.** No footprint: the dangling bench with a `GND` track ending at the via's centre.
- **Probes**, each `present` or `absent`:
  - `copper-renet-export` (padded) and `copper-renet-tied-export`: the IPC-D-356 export (`KicadCli.export_ipcd356`, read with `read_ipcd356`) lists the bench's only via record under `VIN`;
  - `copper-renet-drc` (padded), `copper-renet-dangling-drc`, `copper-renet-anchored-drc`, and on 9.0 only `copper-renet-tied-drc`: the DRC report (`KicadCli.drc`, `read_drc_report`) holds a `shorting_items` violation naming the via's uuid;
  - `copper-renet-dangling-merged` and `copper-renet-anchored-merged`: the DRC report describes the via and the `VIN` track with one net name (the name in square brackets of an item's description);
  - `copper-renet-resave` (padded) and `copper-renet-dangling-resave`, on 10.0 only: after `KicadCli.upgrade_board`, `read_board` gives the via the net of the `VIN` track.
- **What is not pinned.** A probe MUST have one outcome on every run of a version. Two outcomes were measured to differ between runs of one unchanged bench and MUST NOT be probes; `docs/formats/kicad/copper.md` records their counts as supporting data: which of the two net names a cluster without pads takes (and so the via's export net on the dangling and anchored benches on 10.0), and whether 10.0.6 reports the `shorting_items` violation of the tied bench.
- The DRC types that name the via's uuid MUST be recorded, sorted, per bench and per major in `docs/formats/kicad/copper.md` as supporting data.
- `H-K-VIA-RENET` MUST become `KICAD-VERIFIED` on a major only when `copper-renet-export` records `present`, `copper-renet-drc` records `absent` and, on 10.0, `copper-renet-resave` records `present`. Otherwise the row MUST record the observed outcomes, be marked refuted on that major, and name a `-2` successor stating them. No requirement of this change depends on the outcome.

#### Scenario: Re-net recorded on both majors
- **WHEN** `uv run pytest tests/kicad/copper/test_via_renet.py` runs on 9.0.9 and on 10.0.6
- **THEN** the eight probes of 9.0.9 and the nine of 10.0.6 hold `present` or `absent`, and `uv run pytest tests/kicad/test_probe_results.py` passes against the committed `docs/evidence/kicad/probes/<version>.json`

#### Scenario: Fenolite flags the bench
- **GIVEN** the design of the dangling bench
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k renet_bench` runs `check_copper` on it
- **THEN** it reports one `copper.short` naming the via and the track, on `F.Cu`

### Requirement: Copper verdict parity canaries
`tests/kicad/copper/test_copper_parity.py` (markers `needs_kicad`, major-aware) SHALL compare the verdicts of `check_copper` with those of `kicad-cli pcb drc` on authored benches, on 9.0.9 and 10.0.6 (`H-K-COPPER-SHAPES`, `H-K-COPPER-RESOLVE`) and on 10.0.6 for zone fills (`H-K-COPPER-ZONES`).
- **Benches.** A bench whose rows need a project setting (net classes or the board minimum) MUST be written through c0010's triad path with the canary of c0010's `tests/_netclass_bench.py`, scoped by a `net` condition to `CANARY_A`, as c0010's net-class oracle does, because the unconditional canary rule would govern every pair over the classes; a custom rule of such a bench MUST come after the canary rule. Every other bench MUST follow "Rules proofs carry a canary" with `_rulebench.Builder` and a `{}` project, its rules selecting the probe nets only, so the canary pair stays under the canary rule. This change extends `_rulebench.Builder` with `arc_pair`, `via_pair`, `pad_track`, `tht_track` and `fill_track` rows, and with net classes and model rules, which both kinds of bench use. Every bench MUST fail with "rules file not loaded" when its canary violation is missing.
- **Rows.** Per pair kind (track–track, arc–track, via–track, via–via, SMD pad–track with `Mini_R_0603`, pad–pad of two footprints, through-hole pad–track on `B.Cu` with `Mini_LED_THT_3mm`, and, on 10.0.6 with a target-10 board, zone fill–track), one row per edge gap: `c − 10 µm`, `c` and `c + 10 µm`, each pair on two probe nets of its own. An arc pair has no row at `c`: at exactly the clearance its band may report (`copper-check`, "Clearance findings").
- **No overlapping or touching row.** KiCad's verdict on copper of two nets that touches is not repeatable: without a pad on both nets it treats the copper as one net and reports nothing, and with one 10.0.6 reports the short in about half of its runs ("Via re-net probe"). Such rows MUST NOT be compared or pinned; `check_copper`'s shorts are proved by its own exact tests, and the re-net probes record KiCad's side.
- **Zone clearance of the fill rows.** The zone of a fill row MUST carry `(connect_pads (clearance 0))` and `(filled_areas_thickness no)`, inserted by token edit into the written board, so that KiCad's verdict rests on `c` alone: without them KiCad applies its default zone clearance of 0.5 mm to the fill, and `check_copper` does not apply the zone's own clearance (`copper-check`, "Supported cases are documented against KiCad's DRC").
- **Clearance sources.** `c` is given once by a clearance rule on the probe nets (0.2 mm), once by the net class of both nets (0.3 mm), and once by the project's `board.design_settings.rules.min_clearance` above the classes (0.4 mm), set as c0010's `test_netclass_drc.py::test_floor` sets it. The three values differ from each other, and the last two from the template's `Default` class clearance of 0.2 mm, so each source is told from the others.
- **Resolution rows.** A rule below the class value, a rule above it, two classes (the larger governs), a floor above a rule (the rule governs on both majors, `H-K-PRO-MIN-RULE-2`), a rule with severity `ignore`, and an `item_kind track` rule on an arc pair. Each case MUST hold a row that KiCad reports and a row that it does not.
- **Verdicts.** KiCad's verdict for a row MUST be `short` when a `shorting_items` violation names both items' uuids, `clearance` when a `clearance` violation does, and `clean` otherwise (`H-K-DRC-TYPES`, `H-K-DRC-UUID`). Fenolite's verdict MUST come from `check_copper` on the board read back with `read_board`, with the bench's project and rules texts applied by `design_rules_from_texts` for the running major (so the switches follow c0026's tables) and the pads of c0028's frame. They MUST be equal on every row.
- **Boundary.** Rows at `c − 1 µm` and `c − 1 nm` MUST be recorded only, as `copper-boundary-1um` and `copper-boundary-1nm` (`present` when KiCad reports the violation).
- **Zones.** Two filled zones of different nets and equal priority whose outlines overlap on `F.Cu` MUST be recorded on 10.0.6 as `copper-zone-overlap` (`present` when a violation names both zone uuids), as supporting data for the Fenolite rule "Zone outline overlaps" (`copper-check`), which does not depend on it.
- **Probes.** Each pair kind and each resolution case MUST be recorded as `copper-parity-<kind>` or `copper-resolve-<case>`: `equal` when every row agrees, under each clearance source for a pair kind, and `different` otherwise.
- **Hermetic half.** `tests/kicad/copper/test_parity_bench.py` MUST check without `kicad-cli`, for targets 9 and 10, that `check_copper` gives a clearance finding on every row below `c` and none on the others.

#### Scenario: Parity on both majors
- **WHEN** `uv run pytest tests/kicad/copper/test_copper_parity.py` runs on 9.0.9 and on 10.0.6
- **THEN** every `copper-parity-*` and `copper-resolve-*` probe records `equal` (the fill row on 10.0.6 only), and every bench's canary violation is present

#### Scenario: Rule below the class value
- **GIVEN** a pair 0.3 mm apart, both nets in a class of 0.5 mm, and a rule of 0.1 mm on the pair after the canary rule, on a class bench with the scoped canary
- **WHEN** the resolution row runs
- **THEN** KiCad's verdict and that of `check_copper` are equal, and the probe `copper-resolve-rule-below-class` records `equal`

#### Scenario: Missing canary fails
- **GIVEN** a `DrcReport` without the canary violation, as DRC gives when KiCad drops the rules file
- **WHEN** the hermetic `uv run pytest tests/kicad/copper/test_parity_bench.py` passes it to the parity test's verdict helper
- **THEN** the call fails the test with a message saying the rules file was not loaded, and neither passes nor skips

### Requirement: Moved footprints pass the oracle
Footprints moved by `move_footprint`, and the legality verdicts, SHALL be proved on `kicad-cli` 9.0.9 and 10.0.6, probes first:
- **Move.** For the built blink (`examples/blink_2layer`), `pcb export pos` MUST give the requested position, rotation and side after a translation, after rotations to 90° and 30°, and after a flip to the bottom, and the IPC-D-356 pad nets MUST equal those before the move (`H-K-PLACE-MOVE`; probes `place-move-translate`, `place-move-rotate`, `place-move-flip` = `equal`).
- **Touching.** Two courtyards sharing an edge and two sharing a corner MUST be run through `pcb drc`, with a pair overlapping by 20 µm as the positive control in the same board (`H-K-PLACE-TOUCH`; probe `place-touch` records `absent` or `present` for the touching pairs, and is `inconclusive` when the control does not fire).
- **Agreement.** On a bench of six placed parts with known overlapping and clear pairs on both sides, the set of pairs with `place.courtyard-overlap` MUST equal the set of pairs in KiCad's `courtyards_overlap` violations.
- **Rebuild.** A blink variant with two staged parts, placed by `fenolite place --strategy grid --confirm` and built again, MUST keep both placements, report no `layout.unplaced`, and write the same bytes on a second build.

If a move probe records `different`, the fallback of the design (translation only) MUST be applied and recorded in the register row.

#### Scenario: Move proved
- **WHEN** `uv run pytest tests/kicad/place/test_place_probes.py::test_move` runs on 9.0.9 and on 10.0.6
- **THEN** the three probes record `equal`

#### Scenario: Touching settled
- **WHEN** `uv run pytest tests/kicad/place/test_place_probes.py::test_touch` runs on both majors
- **THEN** the control pair gives one `courtyards_overlap`, the probe records the outcome for the touching pairs, and `placement.legality.TOUCHING_OVERLAPS` equals it

#### Scenario: Legality matches DRC
- **WHEN** `uv run pytest tests/kicad/place/test_place_oracle.py::test_legality_matches_drc` runs on both majors
- **THEN** the two sets of pairs are equal

#### Scenario: Placed then rebuilt
- **WHEN** `uv run pytest tests/kicad/place/test_place_oracle.py::test_placed_then_rebuilt` runs on both majors
- **THEN** both parts are inside the outline after `place`, stay where they are after the rebuild, and a second rebuild changes no byte

### Requirement: Routed boards pass the oracle
The KiCadRoutingTools plugin SHALL be proved against `kicad-cli` on 9.0.9 and 10.0.6 at `PINNED_TAG`, feasibility gate first, in tests marked `needs_router` and `needs_kicad`:
- **Arguments and outputs** (`H-K-KRT-CLI`): for the built blink of each target, the tool exits 0, writes its output, the output reads with `read_board`, and routed tracks have the width passed to it.
- **Route** (`H-K-KRT-ROUTE`): after `fenolite route --router kicadroutingtools --confirm` (and `fenolite fill --confirm` on 10.0.6), `pcb drc` of the board's own major MUST report no unconnected item and no violation type of severity error that the unrouted board lacks.
- **Keep** (`H-K-KRT-KEEP`): the tool's output and its input, read with `read_board` and compared without tracks, arcs, vias and provenance, are recorded as `equal` or `different` with what differs.
- **Repeat** (`H-K-KRT-REPEAT`): two runs are compared by the geometry of their tracks and vias, and the outcome is recorded.
- **Loop**: `build`, `route`, `fill` (10.0.6) and `build` again MUST keep every routed item, and a further `build` MUST change no byte.

The outcomes MUST be recorded in `docs/evidence/routing.md` with the tool's version and commit, and MUST NOT be written to `docs/evidence/kicad/probes/`. The gate passes when the route outcome holds on both majors; when it fails on a major, the register row MUST be refuted with a successor that names the nets left unrouted or the violations added.

#### Scenario: Gate on 10.0
- **GIVEN** `FENOLITE_KRT` naming a checkout at `PINNED_TAG`
- **WHEN** `uv run pytest tests/routing/test_krt_gate.py -rA` runs on the local KiCad 10.0.6
- **THEN** `test_cli`, `test_route`, `test_keep` and `test_repeat` record their outcomes, and `test_route` passes with 0 unconnected items

#### Scenario: Gate on 9.0
- **WHEN** the same command runs inside the pinned 9.0.9 image with the tool mounted
- **THEN** `test_route` passes for the target-9 blink without the fill step, and the outcome is recorded

#### Scenario: Loop keeps routes
- **WHEN** `uv run pytest tests/routing/test_route_oracle.py::test_loop` runs on both majors
- **THEN** the rebuilt board holds the routed tracks and vias with their uuids, and the last build writes the bytes of the one before

#### Scenario: Skipped without the tool
- **GIVEN** no `FENOLITE_KRT` and `FENOLITE_REQUIRE` without `router`
- **WHEN** `uv run pytest tests/routing -rs` runs
- **THEN** every test is skipped with a reason naming `FENOLITE_KRT`

### Requirement: Script rule minimums are enforced by kicad-cli
The minimums that a design script declares with `design.rules.minimum` (`design-dsl`, "Rule minimums in the DSL") SHALL be proved by `kicad-cli pcb drc` on built projects (`H-K-DSL-MINIMUM`). `tests/kicad/build/test_script_rules_oracle.py` holds the proof and runs through the package runner on temporary copies.
- The bench MUST be the routed blink of `examples/blink_routed/design.py` built with its script copper: tracks of 0.3 mm, tracks of 0.5 mm on `GND` (class `PWR`), and vias of 0.6 mm with a 0.3 mm drill.
- Each case MUST build the bench twice from scripts that differ only in the value of one minimum: once with a value the copper breaks, once with a value it respects. The verdict MUST come from the DRC JSON report, never from the exit code (`DRC verdicts come from the JSON report`).
- The cases and their violation types MUST be:

  | case | minimum that is broken | minimum that is respected | type |
  |---|---|---|---|
  | board track width | `track_width=mm(0.4)` | `track_width=mm(0.3)` | `track_width` |
  | class track width | `track_width=mm(0.6), netclass="PWR"` | `track_width=mm(0.5), netclass="PWR"` | `track_width` |
  | board via diameter | `via_diameter=mm(0.7)` | `via_diameter=mm(0.6)` | `via_diameter` |
  | board via drill | `via_drill=mm(0.4)` | `via_drill=mm(0.3)` | `drill_out_of_range` |
  | board clearance | `clearance=mm(1)` | `clearance=mm(0.15)` | `clearance` |
  | class clearance | `clearance=mm(1), netclass="PWR"` | `clearance=mm(0.2), netclass="PWR"` | `clearance` |

- The breaking build MUST give at least one violation of the case's type with severity `error`, and the respecting build MUST give none of that type.
- In the class track-width case every violating item MUST be a track of `GND`, the only routed net of the class. In the class clearance case every violation MUST hold at least one item of a net of the class (`GND` or `VIN`).
- No separate canary is needed: the two builds of a case hold the same rules with different values, so a project whose rules `kicad-cli` did not load gives no violation in the breaking build, and the case fails.
- The cases MUST run for target 10 on `kicad-cli` 10.0.x and for target 9 on 9.0.x and 10.0.x (`Major-aware oracle tests`).

#### Scenario: A broken board minimum is reported
- **GIVEN** the routed blink with `design.rules.minimum(track_width=mm(0.4))`
- **WHEN** `uv run pytest tests/kicad/build/test_script_rules_oracle.py -k "board_track_width"` builds it and runs `pcb drc` on 10.0.6
- **THEN** the report holds `track_width` violations of severity `error` on the 0.3 mm tracks, and the same design with `track_width=mm(0.3)` gives no `track_width` violation

#### Scenario: A class minimum governs only its class
- **GIVEN** the routed blink with `design.rules.minimum(track_width=mm(0.6), netclass="PWR")`
- **WHEN** the same test runs the case `class_track_width`
- **THEN** every `track_width` violation names a track of the net `GND`, no track of `LED_DRV` or `LED_A` is reported, and with `track_width=mm(0.5), netclass="PWR"` the report holds no `track_width` violation

### Requirement: Clearance report limit
`H-K-DRC-LIMIT` SHALL be settled on `kicad-cli` 9.0.9 and 10.0.6 by `tests/kicad/check/test_drc_limit.py` on an authored bench, before `KicadOracle.drc` relies on `CLEARANCE_REPORT_LIMIT`.
- **Bench.** `tests/kicad/check/_limitbench.py::limit_project(root, pairs) -> Path` MUST write `tests/data/kicad/board/two_layer.kicad_pcb` with `pairs` more pairs of `F.Cu` tracks, each pair on two nets of its own with a gap of 0.05 mm, a `{}` project and a `(version 1)` rules file. Every byte is authored for Fenolite.
- **Below the limit.** With 300 pairs the plain run MUST report 300 `clearance` violations more than the board without pairs, and the oracle's state MUST be `fired`.
- **At the limit.** With 700 pairs the plain run MUST report at least `CLEARANCE_REPORT_LIMIT` and fewer than 700 `clearance` violations; on 10.0.6 exactly `CLEARANCE_REPORT_LIMIT`.
- **Verdict.** With 700 pairs, each of five `KicadOracle.drc` outcomes MUST be `fired` or `inconclusive` with reason `clearance-limit`, and never `absent`.
- The measured counts per major MUST be recorded in `docs/evidence/kicad-check.md`.

#### Scenario: The count stops near 499
- **GIVEN** the bench with 300 pairs and with 700 pairs
- **WHEN** `uv run pytest tests/kicad/check/test_drc_limit.py -k count` runs on 9.0.9 and on 10.0.6
- **THEN** 300 pairs give 300 more `clearance` violations than no pair, and 700 pairs give at least 499 and fewer than 700 (exactly 499 on 10.0.6)

#### Scenario: A saturated board never reads as rules not loaded
- **GIVEN** the bench with 700 pairs, whose rules file loads
- **WHEN** `uv run pytest tests/kicad/check/test_drc_limit.py -k verdict` runs `KicadOracle.drc` five times on both majors
- **THEN** every state is `fired` or `inconclusive` with reason `clearance-limit`, and none is `absent`

### Requirement: DRC repeatability on the demo boards
`H-K-DRC-REPEAT` SHALL be settled on `kicad-cli` 10.0.6 by `tests/kicad/check/test_canary.py::test_two_run_demo_boards`, which MUST run `KicadOracle.drc` twice on each readable non-heavy demo board, in a folder with a `{}` project and a `(version 1)` rules file, and MUST compare the two outcomes with `tests/_drcrepeat.py`.
- **Strict part.** Each of the two outcomes MUST have `canary_removed` = 0 and a report that names no canary uuid, and its canary state MUST be `fired`; only when its report is saturated (`clearance_saturated`, "Check canary injection") MAY the state instead be `inconclusive` with reason `clearance-limit`. The two outcomes MUST be equal in `outcome`, `returncode` and `tool_writes`, and in `canary` and `canary_reason` unless a report is saturated.
- **Canonical form.** Reports MUST be compared as `DrcReport.entries()`: sorted, without item uuids, with the temporary folder of the run left out of the descriptions. The report order MUST NOT count.
- **Named types.** `UNREPEATABLE_TYPES` MUST be `frozenset({"clearance", "hole_clearance", "unconnected_items"})`. On every board, the entries of every other type MUST be equal between the two runs.
- **Named boards.** `UNREPEATABLE_BOARDS` MUST be the ids `kicad-demo-10-0-6-pcb-01`, `-07`, `-09`, `-11`, `-13` and `-16`. On every other board the whole canonical report MUST be equal.
- **Helper.** `repeat_problems(board_id: str, first: DrcOutcome, second: DrcOutcome) -> list[str]` MUST return one line per difference or broken rule, naming the board and the field, or the type with both counts, and an empty list when the two outcomes agree as stated above. An outcome without a report MUST be a problem.
- **No tolerance by retry.** The test MUST NOT retry, skip or be marked flaky. A board or a type MUST join a named set only with a measurement of at least 15 runs per board recorded in `docs/evidence/kicad-check.md` and in the register row.
- **Record.** `docs/evidence/kicad-check.md` MUST hold, per board and per `kicad-cli` build measured, as ids and counts only: the runs, how often the canary fired, the totals, the count of distinct reports and of distinct orders, the types whose count varies, and the unstable keys per type.

#### Scenario: A stable board repeats exactly
- **GIVEN** `kicad-demo-10-0-6-pcb-17`, which is not in `UNREPEATABLE_BOARDS`
- **WHEN** `uv run pytest "tests/kicad/check/test_canary.py::test_two_run_demo_boards[kicad-demo-10-0-6-pcb-17]"` runs on 10.0.6
- **THEN** both runs give `fired` with no canary item, and `repeat_problems` returns an empty list for the whole report

#### Scenario: A named board repeats outside the named types
- **GIVEN** `kicad-demo-10-0-6-pcb-11`, whose `clearance` count differs between runs
- **WHEN** the same test runs on it
- **THEN** both runs give `fired` with no canary item, and the entries of every type outside `UNREPEATABLE_TYPES` are equal

#### Scenario: A difference outside the named sets fails
- **GIVEN** two authored outcomes for a board in `UNREPEATABLE_BOARDS` that differ in one `track_dangling` entry, and two for another board that differ in one `clearance` entry
- **WHEN** `uv run pytest tests/unit/test_drc_repeat.py -k problems` calls `repeat_problems`
- **THEN** each pair gives one problem naming the board and the type, a pair differing only in report order gives none, a pair differing in the canary state gives a problem naming `canary`, and an `inconclusive` state on a report that is not saturated gives a problem

#### Scenario: The named sets match the record
- **WHEN** `uv run pytest tests/unit/test_drc_repeat.py -k record` reads `docs/evidence/kicad-check.md` and the register row of `H-K-DRC-REPEAT`
- **THEN** both name every id of `UNREPEATABLE_BOARDS` and every type of `UNREPEATABLE_TYPES`

### Requirement: Freerouting routes pass the oracle
The Specctra writer, the session reader and the Freerouting plugin SHALL be proved with Freerouting `PINNED_VERSION` and `kicad-cli` 9.0.9 and 10.0.6, probes first, in tests marked `needs_freerouting`:
- **Accept** (`H-G-DSN-ACCEPT`): Freerouting writes a readable session for the written two-pad board and blink.
- **Units** (`H-G-DSN-UNITS`): after `to_copper`, both ends of the two-pad route lie within 100 nm of the pad centres.
- **Protect** (`H-G-DSN-PROTECT`): with one blink net routed beforehand, no session wire on that net differs from the input.
- **Route** (`H-G-DSN-ROUTE`): after `fenolite route --router freerouting --confirm` (and `fenolite fill --confirm` on 10.0.6), `pcb drc` of the board's major reports no unconnected item and no violation type of severity error that the unrouted board lacks.
- **Repeat** (`H-G-DSN-REPEAT`) and **offline** (`H-G-DSN-OFFLINE`, in a container with `--network none`): outcomes recorded.

The outcomes MUST be recorded in `docs/evidence/routing.md` and `docs/evidence/routing/freerouting-2.4.1.json` with the jar's SHA-256 and the Java version, and MUST NOT be written to `docs/evidence/kicad/probes/`. At day 6 of the time box, `dsn-accept` and `dsn-route-t10` MUST hold; otherwise the change stops and the remaining work is recorded for v0.2a.

#### Scenario: Gate on 10.0
- **GIVEN** `FENOLITE_FREEROUTING_JAR` naming the pinned jar and Java 25
- **WHEN** `uv run pytest tests/routing/test_freerouting_gate.py -rA` runs on the local KiCad 10.0.6
- **THEN** `test_accept`, `test_units`, `test_protect` and `test_route` pass, and `test_repeat` records its outcome

#### Scenario: Gate on 9.0
- **WHEN** `test_route` runs for the target-9 blink with the board judged inside the pinned 9.0.9 image
- **THEN** it passes without the fill step, and the outcome is recorded

#### Scenario: Offline run
- **GIVEN** Docker and the pinned Freerouting image
- **WHEN** `uv run pytest tests/routing/test_freerouting_gate.py::test_offline` runs
- **THEN** the container with `--network none` writes a session, the outcome is `present`, and `FreeroutingRouter.sends_data_offsite` is `False` in the same commit that records it

#### Scenario: Skipped without the tool
- **GIVEN** no `FENOLITE_FREEROUTING_JAR`
- **WHEN** `uv run pytest tests/routing -m needs_freerouting -rs` runs
- **THEN** every test is skipped with a reason naming the variable

