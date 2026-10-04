## ADDED Requirements

### Requirement: Second example board
`examples/board_40parts/design.py` SHALL be an authored design of exactly forty parts that builds with no fetch, from the authored mini library through the folder's own `fp-lib-table` and `sym-lib-table`.
- The file MUST start with `# SPDX-License-Identifier: CC0-1.0` and the line stating that it was authored for Fenolite.
- It MUST hold two controllers, twenty resistors and eighteen LEDs, at least two modules, one netclass, a two-copper board of 100 mm × 80 mm and one zone on the bottom copper layer.
- It MUST state its board-wide minimums (clearance, track width, via size) through the rule constructor of the design DSL (c0054), and the built rule set MUST hold them.
- Only the two controllers MUST have a position in the file; they MUST be locked.
- `fenolite build examples/board_40parts/design.py --out <dir> --confirm` MUST exit 0 for `--target 9` and `--target 10`, and `validate` and `erc.lite` MUST report no error on the result.
- `examples/README.md` MUST list the example.

#### Scenario: Forty parts
- **WHEN** `uv run pytest tests/unit/test_examples.py -k board_40parts` loads the design
- **THEN** it holds 40 parts, 2 of them placed and locked, at least 2 modules, and a rule set with the board-wide minimums of the script

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

### Requirement: README describes v0.1
`README.md` SHALL describe what v0.1 does, in the same pull request as the agent guide.
- The status paragraph MUST name the version `0.1`, MUST say what works (the loop of the agent guide on two-layer boards, for KiCad 9.0 and 10.0), MUST link to `docs/release/v0.1.md` for the limits, and MUST NOT hold the words `pre-alpha` or `being bootstrapped`.
- A section `## Install` MUST hold the line `pip install fenolite` and say that it installs no other package; the development install stays under its own heading.
- The file MUST NOT say that Fenolite's output is byte-identical to a file re-saved by KiCad: v0.1 claims tree identity only (`H-K-FMT-INDENT`).
- `tests/unit/test_agent_skill.py` MUST check the three rules above textually.

#### Scenario: Status and install present
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k readme` runs
- **THEN** it passes only if `README.md` names `0.1`, links to `docs/release/v0.1.md` and holds `pip install fenolite` under `## Install`

#### Scenario: Stale status rejected
- **GIVEN** a copy of `README.md` that holds `Status: pre-alpha`
- **WHEN** the README check runs on it
- **THEN** it fails and names `pre-alpha`

### Requirement: Release record
`docs/release/v0.1.md` SHALL be the record of the v0.1 acceptance, and `tests/unit/test_release_record.py` SHALL guard it.
- The record MUST hold a table with the header `| item | statement | proof | job | result |` covering each of the eight acceptance items with at least one row.
- `proof` MUST be a path under `tests/`, optionally followed by `::` and a test name, and the guard MUST fail when the file or the function does not exist.
- `result` MUST be one of `met`, `met with a recorded limit`, `not met`, `pending`. The guard MUST fail for a `pending` row when `fenolite.__version__` is `0.1.0`, and for a `met with a recorded limit` row with no entry for its item under `## Recorded limits`.
- The record MUST also hold: the CI run of the release commit, the versions of `kicad-cli` and of the router, the manual checks with their dates (a footprint moved in KiCad's editor and kept by a rebuild; a live agent session with its model, turns and exit codes, labelled `UNVERIFIED`), `## Recorded limits`, `## Deferred after v0.1`, and `## Verdict`.
- `## Verdict` MUST be written by the maintainer only; an agent leaves it `pending`.

The record MUST state these limits, and the guard MUST fail when one is missing or when its row says `met`:
- **Item 2 (corpus round trips).** The numbers MUST be copied from `docs/evidence/kicad-rt2.md`: RT0 and RT1 on the 21 readable non-heavy demo boards and the 3 third-party boards; the 2 rows tagged `heavy` are not run in CI; one demo file is malformed at its tag and is not round-tripped; RT2 is `not judged` on a board whose DRC report KiCad does not repeat (one board when recorded); RT2 on 9.0.9 covers the 5 `rt2-9` rows only. The entry MUST hold the words `heavy`, `not judged` and `rt2-9`.
- **Item 5 (schemas).** The row for "every output validates against the `v0` schemas" MUST be `met with a recorded limit`, and its entry MUST hold the sentence `envelope, error and manifest schemas only`: an envelope names `fenolite.<command>.v0`, and no schema file for a command's `result` exists under `schemas/`.
- **Residue scan.** The record MUST say that the residue scan of v0.1.0 ran with the `public gate only`, in CI, in the release workflow and over the history, and that the private gate was not run for v0.1.0.
- **Container refill.** The record MUST say that `H-K-CLI-DOCKER` is `verified locally only`, with the date, the Docker version, the image digest and the `kicad-cli` version of the run, and that no CI job runs `tests/kicad/fill/test_docker_cli.py`.
- **Board outlines.** The record MUST say that 3 of the 21 readable non-heavy demo boards do not chain into a closed outline without a snapping tolerance, that `place` reports `place.no-outline` on them, and that `H-G-EDGE-EXACT` and `H-G-PLACE-OUTLINE` stay `INFERRED`.

`## Deferred after v0.1` MUST list `per-command result schemas` and `outline snapping tolerance` (the 1 µm tolerance and the chaining of footprint edge items), each with the milestone the roadmap gives it. It MUST NOT list the DSL rule constructor, which c0054 delivers in v0.1.

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

#### Scenario: Schema row cannot say met
- **GIVEN** a copy of the record whose item 5 schema row has the result `met`
- **WHEN** the guard runs on it
- **THEN** it fails and names the sentence `envelope, error and manifest schemas only`

#### Scenario: Item 2 limits required
- **GIVEN** a copy of the record whose item 2 entry under `## Recorded limits` lacks `not judged`
- **WHEN** the guard runs on it
- **THEN** it fails and names item 2

#### Scenario: Limits and deferrals are named
- **WHEN** `uv run pytest tests/unit/test_release_record.py -k limits` reads the committed record
- **THEN** it passes only if the record holds `H-K-CLI-DOCKER` with `verified locally only`, the words `public gate only`, `H-G-EDGE-EXACT` and `H-G-PLACE-OUTLINE`, and both `per-command result schemas` and `outline snapping tolerance` under `## Deferred after v0.1`

#### Scenario: Rule constructor is not deferred
- **GIVEN** a copy of the record that lists `DSL rule constructor` under `## Deferred after v0.1`
- **WHEN** the guard runs on it
- **THEN** it fails and names the entry

### Requirement: Release build and local checks
The release artefacts SHALL be built from the tagged commit in a clean checkout, and never from the maintainer's working tree.
- A clean checkout is one of: the release workflow's checkout, a fresh clone of the tag, or `git worktree add <dir> <tag>`. The maintainer's working tree MAY hold uncommitted or untracked files; that is not a condition of the release.
- `docs/release/v0.1.md` MUST hold a section `## Release build` that states this rule and the commands.
- Before the version commit, the build MUST be rehearsed once: `git worktree add <dir> HEAD`, then `uv build` in `<dir>`; the result (the two file names and the count of files in the source distribution) is written in that section.
- `uv run python tools/residue/scan.py --history` MUST be run before the version commit and MUST report no hit. `docs/evidence/residue-history.md` MUST gain one row with the tag `v0.1.0`, the scanned head commit in the commit range, the private gate `not run` and `0` hits, and its first paragraph MUST say that the private gate is optional and was not run for v0.1.0.
- `make hooks` SHALL install `tools/hooks/pre-commit`, which scans the staged files with the public patterns and needs no other file.
- `tests/unit/test_release_record.py` MUST fail when `fenolite.__version__` is `0.1.0` and `docs/evidence/residue-history.md` has no `v0.1.0` row, or when that row claims the private gate `on`.

#### Scenario: Build rehearsed in a clean worktree
- **GIVEN** a main checkout with one untracked file `stray.txt`
- **WHEN** `git worktree add <dir> HEAD` and then `uv build --out-dir <dir>/dist` in `<dir>` run
- **THEN** the build succeeds and the source distribution holds no `stray.txt`

#### Scenario: Record states the build rule
- **WHEN** `uv run pytest tests/unit/test_release_record.py -k build` runs
- **THEN** it passes only if the record has `## Release build` and that section holds `git worktree add` and the words `never from the working tree`

#### Scenario: History row required
- **GIVEN** `__version__ == "0.1.0"` and a copy of `docs/evidence/residue-history.md` with only the `v0.0.1.dev0` row
- **WHEN** the guard runs on it
- **THEN** it fails and names `docs/evidence/residue-history.md`

#### Scenario: Row may not claim the private gate
- **GIVEN** a `v0.1.0` row whose private gate column says `on`
- **WHEN** the guard runs on it
- **THEN** it fails and names the column

#### Scenario: Hook installed
- **GIVEN** the main checkout after `make hooks`
- **WHEN** `test -x "$(git rev-parse --git-common-dir)/hooks/pre-commit"` runs
- **THEN** it exits 0

### Requirement: Version 0.1.0
The version SHALL become `0.1.0` in one commit, after every row of the release record has a result and the build rehearsal and the history row are recorded.
- `src/fenolite/__init__.py` MUST hold `__version__ = "0.1.0"`, and `packaging/phenolite/pyproject.toml` MUST hold `version = "0.1.0"` and `dependencies = ["fenolite==0.1.0"]`.
- `CHANGELOG.md` MUST hold `## [0.1.0] - <date>` with the entries that were under Unreleased, and an empty `## [Unreleased]` above it.
- The `[0.1.0]` section MUST hold each `###` heading at most once, and its entries MUST describe what a user of the CLI or the library sees: no entry names a module or function whose name starts with an underscore, and notes about tests, CI or the repository are merged into one closing entry or removed.
- `docs/roadmap.md` MUST show the v0.1 changes as done or moved, with no v0.1 change in the state `roadmap`, and MUST list per-command result schemas under a later milestone.
- No task of this change MUST create a tag, a GitHub Release or a PyPI upload.

#### Scenario: Versions agree
- **WHEN** `uv run pytest tests/unit/test_release_record.py -k version tests/unit/test_pyproject_invariants.py` runs after the version commit
- **THEN** the package version, the alias version, the alias pin and the newest `CHANGELOG.md` heading are all `0.1.0`

#### Scenario: Changelog section is clean
- **WHEN** `uv run pytest tests/unit/test_release_record.py -k changelog` runs
- **THEN** it passes only if no `##` section of `CHANGELOG.md` from `[0.1.0]` upwards repeats a `###` heading, and no entry of `[0.1.0]` holds a backticked name that starts with an underscore
