## ADDED Requirements

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
