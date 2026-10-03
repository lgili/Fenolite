## ADDED Requirements

### Requirement: Second example board
`examples/board_40parts/design.py` SHALL be an authored design of exactly forty parts that builds with no fetch, from the authored mini library through the folder's own `fp-lib-table` and `sym-lib-table`.
- The file MUST start with `# SPDX-License-Identifier: CC0-1.0` and the line stating that it was authored for Fenolite.
- It MUST hold two controllers, twenty resistors and eighteen LEDs, at least two modules, one netclass, a two-copper board of 100 mm × 80 mm and one zone on the bottom copper layer.
- Only the two controllers MUST have a position in the file; they MUST be locked.
- `fenolite build examples/board_40parts/design.py --out <dir> --confirm` MUST exit 0 for `--target 9` and `--target 10`, and `validate` and `erc.lite` MUST report no error on the result.
- `examples/README.md` MUST list the example.

#### Scenario: Forty parts
- **WHEN** `uv run pytest tests/unit/test_examples.py -k board_40parts` loads the design
- **THEN** it holds 40 parts, 2 of them placed and locked, and at least 2 modules

#### Scenario: Builds for both targets without a subprocess
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** the same test builds the example for targets 9 and 10 into temporary folders
- **THEN** both builds exit 0 and each writes a project, a board and a rules file

### Requirement: Acceptance loop
`tests/routing/test_acceptance_loop.py::test_loop` SHALL run the loop `build`, `place --strategy grid`, `route`, `fill`, `check`, `export --all --manifest`, `render --svg --png` through the CLI, for `blink_2layer` and `board_40parts` and for targets 9 and 10, on `kicad-cli` 10.0.6 with the router of c0016's gate verdict.
- Every command MUST run with `--confirm` in a temporary folder and MUST exit 0.
- `check` MUST report no DRC violation and no unconnected item, no net-assignment difference and an equal round-trip.
- The router MUST run with a limit of 600 s. Copper that `design.py` scripts for nets the router cannot close MUST be counted, and the count MUST be in the release record (`H-K-REL-LOOP40`).
- With `FENOLITE_ACCEPTANCE_WRITE=1`, the test MUST write each finished project to `tests/data/acceptance/<example>_t<target>/`; without it, the test MUST write nothing in the repository.
- Each recorded project MUST have a row in `tests/data/MANIFEST.toml` naming the router and its version and the `kicad-cli` version.

#### Scenario: Loop closes on the blink
- **WHEN** `FENOLITE_REQUIRE=kicad,router uv run pytest tests/routing/test_acceptance_loop.py -k "loop and blink"` runs on 10.0.6
- **THEN** the seven commands exit 0 for targets 9 and 10, and `check` reports no unconnected item

#### Scenario: Loop closes on forty parts
- **WHEN** the same test runs with `-k "loop and board_40parts"`
- **THEN** the seven commands exit 0 for both targets, and the test prints the number of nets closed by the router and by script copper

#### Scenario: Nothing written without the flag
- **WHEN** the test runs without `FENOLITE_ACCEPTANCE_WRITE`
- **THEN** `git status --short tests/data/acceptance` prints nothing

### Requirement: Finished boards pass on both majors
`tests/kicad/acceptance/test_finished.py` SHALL check every recorded project of `tests/data/acceptance/` on the running `kicad-cli`; a target-10 project MUST be skipped on 9.0.x with the reason `target 10 on kicad-cli 9`.
- **Check.** `fenolite check <project>` MUST exit 0 with no DRC violation, no unconnected item, no net-assignment difference and an equal round-trip.
- **Rebuild.** `fenolite build <design.py> --out <copy> --dry-run` over a copy of the recorded project MUST plan no write; `--confirm` twice MUST leave every file byte-equal to the recorded one.
- **Moved footprint.** After `fenolite place <copy> --strategy manual --move R1=<x>,<y> --confirm` and a rebuild, `R1` MUST be at the moved position, and every track, via and zone fill MUST be byte-equal to the one before the rebuild.
- **Negative tests.** A copy with one pad re-netted and a copy with a track between two nets MUST each make `check` exit 5 with an issue that names the reference or the position.
- **Exports.** `fenolite export <copy> --out <tmp> --all --manifest --dry-run` and `fenolite render <copy> --out <tmp> --svg --dry-run` MUST exit 0 with a non-empty plan.

#### Scenario: Recorded blink on 9.0.9
- **WHEN** `uv run pytest tests/kicad/acceptance/test_finished.py -k "blink and t9"` runs inside the pinned 9.0.9 image
- **THEN** every check above passes

#### Scenario: Recorded boards on 10.0.6
- **WHEN** `uv run pytest tests/kicad/acceptance/test_finished.py` runs on 10.0.6
- **THEN** the four projects pass every check

#### Scenario: Rebuild is the identity
- **GIVEN** a copy of `tests/data/acceptance/board_40parts_t10`
- **WHEN** `fenolite build examples/board_40parts/design.py --out <copy> --target 10 --confirm` runs twice
- **THEN** every file of the copy has the bytes of the recorded project

#### Scenario: Re-netted pad is detected
- **GIVEN** a copy of the recorded blink in which pad 1 of `R1` carries the net `GND`
- **WHEN** `fenolite check <copy>` runs
- **THEN** the exit code is 5 and an issue names `R1`

### Requirement: Agent guide is executable
`agent/SKILL.md` SHALL teach the v0.1 loop, and its commands SHALL be run by tests.
- The file MUST have front matter with `name` and `description`, MUST be under 200 lines, and MUST hold exactly one fenced block tagged `fenolite-loop` with at most ten lines, each a `fenolite` command on `examples/blink_2layer/design.py` or `build/blink`.
- The guide MUST state: `capabilities` first; the exit codes 0 to 7; `--dry-run` before `--confirm`; that a level below `KICAD-VERIFIED` is unconfirmed; what to do for each non-zero exit code.
- `README.md` MUST hold the same block, and `AGENTS.md` MUST link to the guide.
- `tests/unit/test_agent_skill.py` MUST parse each line of the block with the CLI's own argument parser and fail for an unknown command or flag.
- `tests/routing/test_acceptance_loop.py::test_skill_block` MUST run the lines in order in a temporary folder; each MUST exit 0 and each envelope MUST hold `evidence.level`.
- The guide MUST NOT name a company, a private path or a user name.

#### Scenario: Block parses
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py` runs
- **THEN** it finds one `fenolite-loop` block of at most ten lines, each accepted by the parser, and the same block in `README.md`

#### Scenario: A stale flag fails
- **GIVEN** a copy of the guide whose block holds `fenolite route build/blink --engine x`
- **WHEN** the block check runs on it
- **THEN** it fails and names `--engine`

#### Scenario: Ten commands close the loop
- **WHEN** `FENOLITE_REQUIRE=kicad,router uv run pytest tests/routing/test_acceptance_loop.py::test_skill_block` runs on 10.0.6
- **THEN** every line exits 0, every envelope carries `evidence.level`, and the count of lines is at most ten

### Requirement: Release record
`docs/release/v0.1.md` SHALL be the record of the v0.1 acceptance, and `tests/unit/test_release_record.py` SHALL guard it.
- The record MUST hold a table with the header `| item | statement | proof | job | result |` covering each of the eight acceptance items with at least one row.
- `proof` MUST be a path under `tests/`, optionally followed by `::` and a test name, and the guard MUST fail when the file or the function does not exist.
- `result` MUST be one of `met`, `met with a recorded limit`, `not met`, `pending`. The guard MUST fail for a `pending` row when `fenolite.__version__` is `0.1.0`, and for a `met with a recorded limit` row with no entry under `## Recorded limits`.
- The record MUST also hold: the CI run of the release commit, the versions of `kicad-cli` and of the router, the manual checks with their dates (a footprint moved in KiCad's editor and kept by a rebuild; a live agent session with its model, turns and exit codes, labelled `UNVERIFIED`), the limits of v0.1, and `## Verdict`.
- `## Verdict` MUST be written by the maintainer only; an agent leaves it `pending`.

#### Scenario: Missing proof
- **GIVEN** a copy of the record with a `proof` naming `tests/kicad/acceptance/test_missing.py`
- **WHEN** the guard runs on it
- **THEN** it fails and names the row

#### Scenario: Pending row blocks the version
- **GIVEN** a record with one `pending` row and `__version__ == "0.1.0"`
- **WHEN** `uv run pytest tests/unit/test_release_record.py` runs
- **THEN** it fails and names the item

#### Scenario: All eight items present
- **WHEN** the guard reads the committed record
- **THEN** the items 1 to 8 each have at least one row

### Requirement: Version 0.1.0
The version SHALL become `0.1.0` in one commit, after every row of the release record has a result.
- `src/fenolite/__init__.py` MUST hold `__version__ = "0.1.0"` and `packaging/phenolite/pyproject.toml` `version = "0.1.0"`.
- `CHANGELOG.md` MUST hold `## [0.1.0] - <date>` with the entries that were under Unreleased, and an empty `## [Unreleased]` above it.
- `docs/roadmap.md` MUST show the v0.1 changes as done or moved, with no v0.1 change in the state `roadmap`.
- No task of this change MUST create a tag, a GitHub Release or a PyPI upload.

#### Scenario: Versions agree
- **WHEN** `uv run pytest tests/unit/test_release_record.py -k version` runs after the version commit
- **THEN** the package version, the alias version and the newest `CHANGELOG.md` heading are all `0.1.0`
