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
- `KicadCli.drc(board, *, files=None)` MUST run `pcb drc --format json --severity-all -o <out> <board>` through c0009's runner on a copy, and MUST NOT pass `--exit-code-violations`. `DrcRun.report` MUST be `None` when no report was written.
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

