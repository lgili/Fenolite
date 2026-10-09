# release-gate Specification

## Purpose
What a Fenolite release has to prove before it is tagged: a second example board, the acceptance loop on both examples and both KiCad majors, an agent guide whose commands are run by tests, a release record that names the proof and the limits of every acceptance item, a build from a clean checkout, and the version change.

## Requirements

### Requirement: Second example board
`examples/board_40parts/design.py` SHALL be an authored design of exactly forty parts that builds with no fetch, from the authored mini library through the folder's own `fp-lib-table` and `sym-lib-table`.
- The file MUST start with `# SPDX-License-Identifier: CC0-1.0` and the line stating that it was authored for Fenolite.
- It MUST hold two controllers, twenty resistors and eighteen LEDs, at least two modules, one netclass, a two-copper board of 100 mm × 80 mm and one zone that covers the bottom copper layer.
- It MUST state its board-wide minimums (clearance, track width, via size) through the rule constructor of the design DSL (c0054), and the built rule set MUST hold them.
- Only the two controllers MUST have a position in the file; they MUST be locked.
- `fenolite build examples/board_40parts/design.py --out <dir> --confirm` MUST exit 0 for `--kicad-version 9` and `--kicad-version 10`, and `validate` and `erc.lite` MUST report no error on the result.
- `examples/README.md` MUST list the example.

#### Scenario: Forty parts
- **WHEN** `uv run pytest tests/unit/test_examples.py -k board_40parts` loads the design
- **THEN** it holds 40 parts, 2 of them placed and locked, at least 2 modules, and a rule set with the board-wide minimums of the script

#### Scenario: Builds for both targets without a subprocess
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** the same test builds the example for targets 9 and 10 into temporary folders
- **THEN** both builds exit 0 and each writes a project, a board and a rules file

### Requirement: Acceptance loop
`tests/routing/test_acceptance_loop.py::test_loop` SHALL run the loop `build`, `place --strategy grid`, `route`, `fill`, `check`, `export --all --manifest`, `render --svg --png` through the CLI, for `blink_2layer` and `board_40parts` and for targets 9 and 10, on `kicad-cli` 10.0.6 with Freerouting 2.4.1 (`--router freerouting`), the router whose gate passed in c0023 and whose two runs give the same copper (`dsn-repeat`).
- Every command MUST run with `--confirm` in a temporary folder and MUST exit 0.
- `check` MUST report no DRC violation and no unconnected item, no net-assignment difference and an equal round-trip.
- The router MUST run with a limit of 600 s. Copper that `design.py` scripts for nets the router cannot close MUST be counted, and the count MUST be in the release record (`H-K-REL-LOOP40`).
- With `FENOLITE_ACCEPTANCE_WRITE=1`, the test MUST write each finished project to `tests/data/acceptance/<example>_t<target>/`; without it, the test MUST write nothing in the repository.
- Each recorded project MUST have a row in `tests/data/MANIFEST.toml` naming the router and its version and the `kicad-cli` version.

#### Scenario: Loop closes on the blink
- **WHEN** `FENOLITE_REQUIRE=kicad,freerouting uv run pytest tests/routing/test_acceptance_loop.py -k "loop and blink"` runs on 10.0.6
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
- **WHEN** `fenolite build examples/board_40parts/design.py --out <copy> --kicad-version 10 --confirm` runs twice
- **THEN** every file of the copy has the bytes of the recorded project

#### Scenario: Re-netted pad is detected
- **GIVEN** a copy of the recorded blink in which pad 1 of `R1` carries the net `GND`
- **WHEN** `fenolite check <copy>` runs
- **THEN** the exit code is 5 and an issue names `R1`

### Requirement: Agent guide is executable
`src/fenolite/agent/skill/SKILL.md` SHALL teach the loop from an empty folder to fabrication files, and its commands SHALL be run by tests.
- The file MUST have front matter with `name` and `description`, MUST be under 200 lines, and MUST hold exactly one fenced block tagged `fenolite-loop` with at most ten lines, each a `fenolite` command.
- The block MUST hold, in this order, `capabilities --brief`, `init blink`, `build` with `--dry-run`, `build` with `--confirm`, `place`, `route --router direct`, `fill`, `check`, `export` and `render`. Every line after the first two MUST name `blink/design.py` or a folder under `blink/`, the project that `init` writes (`agent-guide`, "Starter projects").
- The guide MUST state: `capabilities --brief` first; the exit codes 0 to 7; `--dry-run` before `--confirm`; that a level below `KICAD-VERIFIED` is unconfirmed; what to do for each non-zero exit code (`agent-guide`, "Start page").
- `README.md` MUST hold the same block, and `AGENTS.md` MUST name the guide's path and the command `fenolite guide`.
- `tests/unit/test_agent_skill.py` MUST parse each line of the block with the CLI's own argument parser and fail for an unknown command or flag. It MUST also run the first six lines in an empty temporary folder with `subprocess.run` and `subprocess.Popen` patched to raise; each MUST exit 0 and each envelope MUST hold `evidence.level`.
- `tests/kicad/acceptance/test_skill_block.py` MUST run all the lines in order in an empty temporary folder on the running `kicad-cli`, once with `--kicad-version 9` and once with `--kicad-version 10` added to every line that takes it; a target-10 run is skipped on 9.0.x. Each line MUST exit 0, each envelope MUST hold `evidence.level`, and `check` MUST report no design-rule violation and no unconnected item.
- The guide MUST NOT name a company, a private path or a user name.

#### Scenario: Block parses
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py` runs
- **THEN** it finds one `fenolite-loop` block of at most ten lines, each accepted by the parser, the same block in `README.md`, and the commands in the order above

#### Scenario: A stale flag fails
- **GIVEN** a copy of the guide whose block holds `fenolite route blink/build --engine x`
- **WHEN** the block check runs on it
- **THEN** it fails and names `--engine`

#### Scenario: First six lines need no tool
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k hermetic_prefix` runs the lines up to `route` with subprocess creation patched to raise
- **THEN** each exits 0, `blink/build/blink.kicad_pcb` exists, and the route's `unrouted` list is empty

#### Scenario: Ten commands close the loop
- **WHEN** `uv run pytest tests/kicad/acceptance/test_skill_block.py -rA` runs on 10.0.6, and on 9.0.9
- **THEN** every line exits 0 for each target the running tool can read, every envelope carries `evidence.level`, `check` reports no violation and no unconnected item, and `blink/fab` holds a manifest and at least one Gerber file

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

### Requirement: README describes the released version
`README.md` SHALL describe what the newest release does, in the same pull request as its release record.
- The status paragraph MUST start with `**Status: version 0.3.**`, MUST say what works (a design script becomes a KiCad project with a board and a schematic for KiCad 9.0 and 10.0, the loop of the agent guide on two-layer boards, and KiCad's own checks of the schematic), MUST link to `docs/release/v0.3.md` for the limits, MUST say what is experimental, and MUST NOT hold the words `pre-alpha` or `being bootstrapped`.
- A section `## What version 0.3 does` MUST name the schematic written by `build`, the checks (ERC, netlist, parity), the BOM and placement tables, the manifest, the inspection commands, the kept layout, the reading of Altium files and the writing of Altium files, each with the page that describes it, and MUST send the reader to the release record for what is proved of the Altium reading and writing.
- A section `## Install` MUST hold the line `pip install fenolite` and say that it installs no other package; the development install stays under its own heading.
- The file MUST NOT say that Fenolite's output is byte-identical to a file re-saved by KiCad: only tree identity is claimed (`H-K-FMT-INDENT`).
- `tests/unit/test_agent_skill.py` MUST check the status paragraph, the install section and the byte-identity rule textually.

#### Scenario: Status and install present
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k readme` runs
- **THEN** it passes only if the status paragraph of `README.md` names `0.3`, links to `docs/release/v0.3.md` and says what is experimental, and `pip install fenolite` stands under `## Install`

#### Scenario: Stale status rejected
- **GIVEN** a copy of `README.md` that holds `Status: pre-alpha`
- **WHEN** the README check runs on it
- **THEN** it fails and names `pre-alpha`

#### Scenario: Status of the version before rejected
- **GIVEN** a copy of `README.md` whose status paragraph starts with `**Status: version 0.2.**`
- **WHEN** the README check runs on it
- **THEN** it fails and names the version `0.3`

### Requirement: Version 0.2.0
The version SHALL become `0.2.0` in one commit, the last of change c0093, after every row of `docs/release/v0.2.md` has a result, a `pending` row has its entry under `## Open rows`, and the history row is recorded. A later version of the series `0.2` is a patch release and follows "Patch releases of 0.2".
- At that commit `src/fenolite/__init__.py` MUST hold `__version__ = "0.2.0"`, and `packaging/phenolite/pyproject.toml` MUST hold `version = "0.2.0"` and `dependencies = ["fenolite==0.2.0"]`. At every later commit the three MUST name one version.
- `CHANGELOG.md` MUST hold `## [0.2.0] - <date>` with the entries that were under Unreleased, and `## [0.1.0]` below it, unchanged. Until the maintainer tags, `<date>` is the words `pending the tag`. Above `[0.2.0]` stands `## [Unreleased]`, empty at that commit; between the two only the sections of the patch releases of the series MAY stand, the newest first.
- The `[0.2.0]` section MUST hold each `###` heading at most once and no entry before its first `###` heading. Its entries MUST describe what a user of the CLI or the library sees: no entry names a module or function whose name starts with an underscore, the notes about archived specs are folded into one closing entry, and notes about tests, CI or the repository are merged into that entry or removed.
- The `[0.1.0]` section MUST stay clean by the same two rules (no repeated `###` heading, no underscore name), which `tests/unit/test_release_record.py` checks.
- `docs/roadmap.md` MUST NOT give the state `proposed` to v0.2a, v0.2b or v0.3 in its milestone table, MUST name every change of the three milestones that is not archived, and MUST name the release change.
- No task of this change MUST create a tag, a GitHub Release or a PyPI upload.

#### Scenario: Versions agree
- **WHEN** `uv run pytest tests/unit/test_release_record_v02.py tests/unit/test_release_record.py -k "version or changelog" tests/unit/test_pyproject_invariants.py` runs after the version commit, or after the commit of a patch release
- **THEN** the package version, the alias version and the alias pin are one version of the series `0.2`, and the headings of `CHANGELOG.md` are `Unreleased`, the patch sections of the series with the newest first, `0.2.0`, `0.1.0`

#### Scenario: Changelog section is clean
- **GIVEN** a changelog whose `[0.2.0]` section holds an entry before its first heading, `### Added` twice, two entries about archived specs and an entry naming `` `_private.name` ``
- **WHEN** the changelog check of `tests/unit/test_release_record_v02.py` runs on it
- **THEN** it names each of the four faults

#### Scenario: Section required at the version
- **GIVEN** `__version__ == "0.2.0"` and a changelog with no `[0.2.0]` section
- **WHEN** the same check runs
- **THEN** it fails and names the section

#### Scenario: Stale roadmap state rejected
- **GIVEN** a copy of `docs/roadmap.md` whose milestone row of v0.2a says `proposed on 2026-10-04`
- **WHEN** `uv run pytest tests/unit/test_release_record_v02.py -k roadmap` runs on it
- **THEN** it fails and names v0.2a

### Requirement: Release record of v0.2
`docs/release/v0.2.md` SHALL be the record of the v0.2a and v0.2b acceptance, for the one release `0.2.0` that carries both, and `tests/unit/test_release_record_v02.py` SHALL guard it.
- The record MUST hold three tables with the header `| item | statement | proof | job | result |`: under `## Acceptance of v0.2a`, with at least one row for each of the five items of "v0.2a acceptance" in `docs/roadmap.md`; under `## Acceptance of v0.2b`, with at least one row for each of its three items; and under `## Also in this package`, for the later milestone whose changes ship in the package. A row whose `item` is not a number of its acceptance MUST carry a change id.
- `proof` MUST be a path under `tests/`, optionally followed by `::` and a test name, and the guard MUST fail when the file or the function does not exist. A test MUST NOT be written to make a row pass: a row with no proof is `not met` or `pending`.
- `job` MUST be one or more job ids of `.github/workflows/ci.yml`, separated by commas, and the guard MUST fail for a name that is no job there.
- `result` MUST be one of `met`, `met with a recorded limit`, `not met`, `pending`. The guard MUST fail for a `met with a recorded limit` row with no entry for it under `## Recorded limits`, and for a `not met` or `pending` row with no entry for it under `## Open rows`. An entry names its row in its bold head: `v0.2a item 3`, `v0.2b item 1`, or the change id for a row of the later milestone.
- `## Verdict` MUST be written by the maintainer only; an agent leaves it `pending`. The guard MUST fail when the verdict is anything else while a row is `pending`. The version MAY become `0.2.0` while a row is `pending`: the release is the tag, which follows the verdict.
- The record MUST also hold `## Runs and versions` (a linked CI run, the versions of `kicad-cli`, and a line for the run of the release candidate commit), `## Manual checks`, `## Release build` (the rule and the commands of "Release build and local checks", for the tag `v0.2.0`), `## Deferred after v0.2`, and `## Maintainer's steps`: the open row, the verdict, the pull request from `dev` to `main`, the tag `v0.2.0` on the merge commit, the build from the tagged commit in a clean checkout, the publication.

The record MUST state these limits, and the guard MUST fail when one is missing or when its row says `met`:
- **v0.2a item 3 (RT2 of schematics).** KiCad's ERC is not repeatable item by item on 9.0.9 and 10.0.6, so RT2 compares the kinds of violations (`H-K-ERC-REPEAT-2`, `H-K-ERC-RT2-2`), and it does not see a violation that only moves to another pin of the same sheet and type. The entry MUST hold both ids and the words `kinds of violations` and `another pin`.
- **v0.2b item 1 (the update from the schematic).** `H-K-SCH-UPDATE` is `INFERRED`: one manual run of "Update PCB from Schematic" by the maintainer in 10.0.6. The entry MUST hold the id, `INFERRED` and the words `one manual run`.
- **The examples.** The record MUST say where the clean ERC of each KiCad example is proved, and that the one of `examples/blink_official` is asserted by `tests/libs/test_build_official.py`, which no CI job runs because it needs the official KiCad libraries.
- **Module sheets on 9.0.9.** The record MUST say that one generated design reports one `pin_not_connected` fewer on its readable sheets, and that the loss is inside KiCad's report.
- **Residue scan.** The record MUST say that the residue scan of v0.2.0 ran with the `public gate only` and that the private gate was not run for v0.2.0. `docs/evidence/residue-history.md` MUST hold one row with the tag `v0.2.0`, the private gate `not run` and `0` hits, and the guard MUST fail when `fenolite.__version__` is `0.2.0` and the row is missing, or when the row claims the private gate `on`.

`## Also in this package` MUST say that the record does not claim the acceptance of the later milestone, MUST state, per scope line of the roadmap's Phase 4, whether a test proves it, and MUST hold the known defect as a row that is `not met`: the schematic import gives the components of a repeated sheet no designator per channel, so they share one designator. Its entry under `## Open rows` MUST hold the words `share one designator`.

#### Scenario: Every item present
- **WHEN** `uv run pytest tests/unit/test_release_record_v02.py` reads the committed record
- **THEN** the items 1 to 5 of v0.2a and 1 to 3 of v0.2b each have at least one row, and every proof and every job exists

#### Scenario: Missing item
- **GIVEN** a copy of the record without the rows of v0.2b item 2
- **WHEN** the guard runs on it
- **THEN** it fails and names `v0.2b item 2`

#### Scenario: Missing proof
- **GIVEN** a copy of the record with a `proof` naming `tests/unit/cli/test_missing.py`
- **WHEN** the guard runs on it
- **THEN** it fails and names the row

#### Scenario: Unknown job
- **GIVEN** a copy of the record with a row whose job is `kicad-11`
- **WHEN** the guard runs on it
- **THEN** it fails and names `kicad-11` and `ci.yml`

#### Scenario: Another word
- **GIVEN** a copy of the record with the result `mostly met`
- **WHEN** the guard runs on it
- **THEN** it fails and names the result

#### Scenario: Limit without an entry
- **GIVEN** a copy of the record whose entry for v0.2a item 4 under `## Recorded limits` has another head
- **WHEN** the guard runs on it
- **THEN** it fails and names `v0.2a item 4`

#### Scenario: A row with a fixed limit cannot say met
- **GIVEN** a copy of the record whose RT2 row of v0.2a item 3 has the result `met`
- **WHEN** the guard runs on it
- **THEN** it fails and names `v0.2a item 3`

#### Scenario: Limits are named
- **GIVEN** a copy of the record whose RT2 entry lacks the words `another pin`
- **WHEN** the guard runs on it
- **THEN** it fails and names the words

#### Scenario: Open row without a reason
- **GIVEN** a copy of the record with a `pending` row and no entry for it under `## Open rows`
- **WHEN** the guard runs on it
- **THEN** it fails and names the row

#### Scenario: Verdict over a pending row
- **GIVEN** a copy of the record with one `pending` row and the verdict `Released as v0.2.0.`
- **WHEN** the guard runs on it
- **THEN** it fails and names the pending row; with that row `met` it does not

#### Scenario: The later milestone is not claimed
- **GIVEN** a copy of the record whose repeated-sheet row says `met`
- **WHEN** the guard runs on it
- **THEN** it fails and names the defect

#### Scenario: Maintainer's steps
- **GIVEN** a copy of the record whose steps do not name the pull request from `dev` to `main`
- **WHEN** the guard runs on it
- **THEN** it fails and names the section

#### Scenario: History row required
- **GIVEN** `__version__ == "0.2.0"` and a copy of `docs/evidence/residue-history.md` without the `v0.2.0` row
- **WHEN** the guard runs on it
- **THEN** it fails and names `docs/evidence/residue-history.md`

### Requirement: Patch releases of 0.2
A version `0.2.N` with `N` from 1 SHALL be a patch release: fixes of defects of the release before it, cut from that release's tag on a branch of its own, and never from `dev`. `docs/release/v0.2.md` SHALL record each one under `## Patch releases`, and `tests/unit/test_release_record_v02.py` SHALL guard that section, the changelog and the history page for every patch release the record names, at any later version of the package.
- **Content.** A patch release MUST hold fixes only. Each fix is a change of its own, with a test that fails on the tag of the release before and passes on the fix. A patch release MUST NOT add a command, a flag, a model field or a schema. It MAY add an issue code only where the fix refuses an input for which the release before wrote a wrong file, and its subsection of the record MUST name the code.
- **Branch.** The branch starts at the tag `v0.2.<N-1>` and reaches `main` by a pull request. After the tag `v0.2.N`, `main` MUST be merged into `dev`, so that `dev` holds the fix, the version and the changelog section.
- **Version.** The three version strings of "Version 0.2.0" change together, in the commit of the release change, which adds no behaviour.
- **Changelog.** `CHANGELOG.md` MUST hold `## [0.2.N] - <date>` between `## [Unreleased]` and the section of the release before, so that the sections of the series stand newest first and without a gap above `## [0.1.0]`; while the version is of the series, `## [Unreleased]` is the only section above them. A patch section MUST be clean by the rules of the `[0.2.0]` section. Until the tag, `<date>` is the words `pending the tag`.
- **Record.** `## Patch releases` MUST hold one subsection `### 0.2.N` per patch release, in rising order from `0.2.1` without a gap, and while `fenolite.__version__` is `0.2.N`, one for every patch release up to it. A subsection MUST hold:
  - the defect, in words a user understands: which releases have it, what was written wrong, and which designs are not affected;
  - a table with the header `| item | statement | proof | job | result |` and at least one row. The `item` of a row MUST be the id of the change that made the fix, and MUST NOT be an `item` of the three tables of `0.2.0`, which a patch release does not touch. `proof`, `job` and `result` are held to the rules of "Release record of v0.2": a row that is `met with a recorded limit` needs an entry under `## Recorded limits`, and a row that is `pending` or `not met` an entry under `## Open rows`, each named by the change id;
  - the words `cut from the tag` with the tag it starts from, and the step that merges `main` into `dev`;
  - a line that starts with `**Verdict of 0.2.N.**`, which an agent leaves as `pending`. The guard MUST fail for a verdict other than `pending` while a row of the subsection is `pending`, and for one without a linked CI run in the subsection.
- **Residue.** `docs/evidence/residue-history.md` MUST hold one row with the tag `v0.2.N`, the private gate `not run` and `0` hits for every patch release the record names, as it does for `v0.2.0`, and the guard MUST fail when a row is missing or claims the private gate `on`.

#### Scenario: Patch release recorded
- **WHEN** `uv run pytest tests/unit/test_release_record_v02.py -k patch` reads the committed record, changelog and history page at version `0.2.2`
- **THEN** the record holds `### 0.2.1` and `### 0.2.2`, each with its table, every proof and every job of them exists, the headings of the changelog are `Unreleased`, `0.2.2`, `0.2.1`, `0.2.0`, `0.1.0`, and the history page holds the rows `v0.2.1` and `v0.2.2`

#### Scenario: Version without a subsection
- **GIVEN** the committed record, whose last subsection is `### 0.2.N`, and the version `0.2.<N+1>`
- **WHEN** the guard runs on it
- **THEN** it fails and names `0.2.<N+1>`

#### Scenario: Patch row with a missing proof
- **GIVEN** a copy of the record whose table of one patch release names the proof `tests/unit/lens/test_missing.py`, for each patch release the record names
- **WHEN** the guard runs on it
- **THEN** it fails and names the row

#### Scenario: Patch row taken from the acceptance
- **GIVEN** a copy of the record whose table of one patch release holds a row with the item `c0070`, which is an item of the table of v0.2b, for each patch release the record names
- **WHEN** the guard runs on it
- **THEN** it fails and names `c0070`

#### Scenario: Patch sections out of order
- **GIVEN** a changelog whose headings are `Unreleased`, `0.2.0`, `0.2.1`, `0.1.0`, and one whose headings are `Unreleased`, `0.2.0`, `0.1.0` while the record names `0.2.1`; and, while the record names `0.2.1` and `0.2.2`, a changelog whose headings are `Unreleased`, `0.2.1`, `0.2.2`, `0.2.0`, `0.1.0`, and one without `0.2.2`
- **WHEN** the changelog check runs on each
- **THEN** each fails and names the sections it found

#### Scenario: Verdict of a patch release
- **GIVEN** a copy of the record whose table of `0.2.1` has a `pending` row and whose line says `**Verdict of 0.2.1.** Released as v0.2.1.`
- **WHEN** the guard runs on it
- **THEN** it fails and names the row; with that row `met` and no linked CI run in the subsection it fails and names the run; and with the run linked it passes

#### Scenario: History row of a patch release required
- **GIVEN** a copy of `docs/evidence/residue-history.md` without the row `v0.2.1`, and the committed record
- **WHEN** the guard runs on it
- **THEN** it fails and names `v0.2.1`

### Requirement: Release record of v0.3
`docs/release/v0.3.md` SHALL record the v0.3 acceptance for `0.3.0`, guarded by `tests/unit/test_release_record_v03.py`.
- `## Acceptance of v0.3` and `## Also in this package` MUST hold the table `| item | statement | proof | job | result |`: a row per item 1 to 5 of "v0.3 acceptance", change ids in the second.
- Proofs, jobs, results, limits and open rows follow "Release record of v0.2".
- `## Verdict` is the maintainer's; the guard MUST refuse a verdict over a `pending` row.

#### Scenario: Every item present
- **WHEN** `uv run pytest tests/unit/test_release_record_v03.py` reads the committed record
- **THEN** the items 1 to 5 each have at least one row, and every proof and every job exists

#### Scenario: Missing item
- **GIVEN** a copy of the record without the rows of item 4
- **WHEN** the guard runs on it
- **THEN** it fails and names `v0.3 item 4`

#### Scenario: Verdict over a pending row
- **GIVEN** a copy of the record with one `pending` row and the verdict `Released as v0.3.0.`
- **WHEN** the guard runs on it
- **THEN** it fails and names the pending row

### Requirement: Graduation table of v0.3
`## Graduation of the Altium write` of `docs/release/v0.3.md` SHALL hold a table whose header starts `| kind | file |`, one row per Altium matrix row with a write cell.
- The verdict, `experimental` or `graduated`, MUST agree with `claims.MATRIX`, and the count of ids MUST be the write cell's.
- The section MUST state the maintainer's exception (`exception`, `condition (d)`) and the revalidation it owes (`fenolite kit verify`, `fenolite kit record`, c0148).

#### Scenario: Graduation table agrees with the matrix
- **GIVEN** a copy of the record whose row of `altium_pcbdoc` says `graduated` while the matrix lists its write as experimental
- **WHEN** the guard runs on it
- **THEN** it fails and names `altium_pcbdoc`

### Requirement: Sections of the record of v0.3
`docs/release/v0.3.md` SHALL hold `## Not in 0.3.0`, `## Runs and versions`, `## Manual checks`, `## Recorded limits`, `## Release build`, `## Deferred after v0.3` and `## Maintainer's steps`.
- `## Not in 0.3.0` MUST name c0137, v0.4, c0151, c0152, Part G, X8 and Part V.
- The runs, the limits, the build and the steps MUST say what those of v0.2 say, for the tag `v0.3.0`, and the steps MUST end with the merge of `main` into `dev`.

#### Scenario: What is not in the release
- **GIVEN** a copy of the record whose section `## Not in 0.3.0` does not name c0137
- **WHEN** the guard runs on it
- **THEN** it fails and names `c0137`

### Requirement: Version 0.3.0
The version SHALL become `0.3.0` in the commit of change c0150, in `src/fenolite/__init__.py`, in `packaging/phenolite/pyproject.toml` and in its pin `fenolite==0.3.0`; later commits keep the three equal.
- `CHANGELOG.md` MUST hold `## [0.3.0] - <date>` under an empty `## [Unreleased]`, followed by the 0.2 series, the newest patch first, and clean by the rules of `[0.2.0]`.
- No task of this change creates a tag, a release page or an upload.

#### Scenario: Versions agree
- **WHEN** `uv run pytest tests/unit/test_release_record_v03.py -k "version or changelog" tests/unit/test_pyproject_invariants.py` runs after the version commit
- **THEN** the package version, the alias version and the alias pin are `0.3.0`, and the headings of `CHANGELOG.md` start `Unreleased`, `0.3.0` and a section of the 0.2 series

#### Scenario: A patch section above the release is refused
- **GIVEN** a changelog whose headings are `Unreleased`, `0.2.2`, `0.3.0`, `0.2.1`
- **WHEN** the changelog check of `tests/unit/test_release_record_v03.py` runs on it
- **THEN** it fails and names the order

### Requirement: History row and roadmap of 0.3.0
`docs/evidence/residue-history.md` SHALL hold a row `v0.3.0` with the private gate `not run` and `0` hits, and `docs/roadmap.md` SHALL name the release change.
- The guard MUST fail at `0.3.0` without the row, or when it claims the private gate `on`.
- The milestone row of v0.3 MUST NOT say `proposed`.

#### Scenario: History row required
- **GIVEN** `__version__ == "0.3.0"` and a copy of `docs/evidence/residue-history.md` without the `v0.3.0` row
- **WHEN** the guard runs on it
- **THEN** it fails and names `docs/evidence/residue-history.md`
