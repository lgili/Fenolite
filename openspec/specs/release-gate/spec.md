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
- The status paragraph MUST start with `**Status: version 0.4.**`, MUST say what works (a design script becomes a KiCad project with a board and a schematic for KiCad 9.0 and 10.0, the loop of the agent guide, and KiCad's own checks of the schematic), MUST link to `docs/release/v0.4.md` for the limits, MUST say what is experimental, and MUST NOT hold the words `pre-alpha` or `being bootstrapped`.
- A section `## What version 0.4 does` MUST name the schematic written by `build`, the checks (ERC, netlist, parity), the BOM and placement tables, the manifest, the inspection commands, the kept layout, the reading of Altium files and the writing of Altium files, each with the page that describes it, and MUST send the reader to the release record for what is proved of the Altium reading and writing.
- A section `## Install` MUST hold the line `pip install fenolite` and say that it installs no other package; the development install stays under its own heading.
- The file MUST NOT say that Fenolite's output is byte-identical to a file re-saved by KiCad: only tree identity is claimed (`H-K-FMT-INDENT`).
- `tests/unit/test_agent_skill.py` MUST check the status paragraph, the install section and the byte-identity rule textually.

#### Scenario: Status and install present
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k readme` runs
- **THEN** it passes only if the status paragraph of `README.md` names `0.4`, links to `docs/release/v0.4.md` and says what is experimental, and `pip install fenolite` stands under `## Install`

#### Scenario: Stale status rejected
- **GIVEN** a copy of `README.md` that holds `Status: pre-alpha`
- **WHEN** the README check runs on it
- **THEN** it fails and names `pre-alpha`

#### Scenario: Status of the version before rejected
- **GIVEN** a copy of `README.md` whose status paragraph starts with `**Status: version 0.3.**`
- **WHEN** the README check runs on it
- **THEN** it fails and names the version `0.4`

### Requirement: Version 0.2.0
The version SHALL become `0.2.0` in one commit, the last of change c0093, after every row of `docs/release/v0.2.md` has a result, a `pending` row has its entry under `## Open rows`, and the history row is recorded. A later version of the series `0.2` is a patch release and follows "Patch releases of 0.2".
- At that commit `src/fenolite/__init__.py` MUST hold `__version__ = "0.2.0"`, and `packaging/phenolite/pyproject.toml` MUST hold `version = "0.2.0"` and `dependencies = ["fenolite==0.2.0"]`. At every later commit the three MUST name one version.
- `CHANGELOG.md` MUST hold `## [0.2.0] - <date>` with the entries that were under Unreleased, and `## [0.1.0]` below it, unchanged. Until the maintainer tags, `<date>` is the words `pending the tag`. Above `[0.2.0]` stands `## [Unreleased]`, empty at that commit; between the two only the sections of the patch releases of the series MAY stand, the newest first.
- The `[0.2.0]` section MUST hold each `###` heading at most once and no entry before its first `###` heading. Its entries MUST describe what a user of the CLI or the library sees: no entry names a module or function whose name starts with an underscore, the notes about archived specs are folded into one closing entry, and notes about tests, CI or the repository are merged into that entry or removed.
- The `[0.1.0]` section MUST stay clean by the same two rules (no repeated `###` heading, no underscore name), which `tests/unit/test_release_record.py` checks.
- `docs/roadmap.md` MUST NOT give the state `proposed` to v0.2a, v0.2b or v0.3 in its milestone table, MUST name every change of v0.2a, of v0.2b and of the read part of v0.3 (c0039–c0047) that is not archived, and MUST name the release change.
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

### Requirement: Yardstick board
`examples/yardstick/design.py` SHALL be an authored design of at least 300 parts, written as a user writes a script: an invented controller of eight identical buck channels with an isolated high-voltage sense section, built for KiCad 10 from the official KiCad libraries (change c0119).
- The file MUST start with `# SPDX-License-Identifier: CC0-1.0` and a line stating that it was authored for Fenolite as an example. Beyond the library ids of the official KiCad libraries, it MUST name no company, product or private path.
- It MUST hold a module-level `STAGE = <n>` with n from 1 to 5 ("Yardstick stages"), and the copper layer count of its stage: 4 at stage 1, 6 from stage 2.
- It MUST hold at least 300 parts: a 48-pin QFN controller, eight channel modules made by one function and each holding the same number of parts, a `USB2` interface whose two nets KiCad pairs by name (`H-K-DIFFPAIR-NAMES`), the nets of the high-voltage section in a net class of their own, and at least four mounting holes.
- A channel's references MUST be numbered `n·100 + k` for channel n; the parts outside the channels MUST be numbered below 100.
- Every part MUST be placed by the script; connectors and mounting holes MUST be locked.
- Every value of the circuit, gap and rule MUST be stated once, at the top of the script, as the example's own input, and each MUST carry a comment that says either `chosen for the example` or the id of a public source in `docs/evidence/sources.md`. The values MUST be round ones chosen for the example (supply voltages, the gap, the clearances, the board size), never copied from a board of any organisation.
- **Provenance.** The circuit is invented for Fenolite. `docs/evidence/yardstick.md` MUST record, under `How to read`, the maintainer's statement of 2026-10-07 that the circuit was invented for Fenolite and mirrors no board of any organisation, and `tests/residue` MUST scan `examples/yardstick/`.
- With the libraries of tag 10.0.6 (`needs_libs`), `fenolite build examples/yardstick/design.py --out <dir> --kicad-version 10 --confirm` MUST exit 0 with no issue of severity `error`.
- `examples/README.md` MUST list the example with its stage.

#### Scenario: Structure without a build
- **WHEN** `uv run pytest tests/unit/test_examples.py -k yardstick` loads the script through `fenolite.dsl` without building it
- **THEN** it passes only if the design holds at least 300 parts, eight channel modules of equal size, one `USB2` interface, every part placed, `STAGE` between 1 and 5, and a copper count that matches the stage

#### Scenario: Stage and copper disagree
- **GIVEN** a copy of the script with `STAGE = 1` and `design.board(…, copper=6)`
- **WHEN** the same test runs on the copy
- **THEN** it fails and names `STAGE` and the copper count

#### Scenario: Builds with the official libraries
- **GIVEN** the verified library cache of tag 10.0.6
- **WHEN** `uv run pytest tests/libs/test_yardstick_build.py` builds the example for target 10 into a temporary folder
- **THEN** the build exits 0 with no `error` issue and writes a board, a project and a rules file

#### Scenario: Every value says where it comes from
- **WHEN** `uv run pytest tests/unit/test_examples.py -k yardstick_values` reads the assignments above the first function of the script
- **THEN** it passes only if each has a comment holding `chosen for the example` or an `S-` id that `docs/evidence/sources.md` lists, and `docs/evidence/yardstick.md` holds the statement of provenance with its date

### Requirement: Yardstick stages
The yardstick SHALL grow in five cumulative stages, and `tools/yardstick.py` SHALL hold the table of the stages: for each, the changes it needs and the steps the runner takes.

| stage | needs on `dev`, archived | steps added to the stage before |
|---|---|---|
| 1 | nothing beyond release 0.3.0 | `capabilities`, `build-dry`, `build`, `fill`, `check`, `export`, `render`, `bom`, `pnp`, `manifest`, `rebuild-dry`, `rebuild`, `inspect`, `build-install`, `heavy-read`, `heavy-rt1` |
| 2 | c0100, c0101 | none |
| 3 | c0102, c0103, c0104, c0105, c0111, c0112, c0113, c0114 | `impedance` |
| 4 | c0106, c0107, c0108, c0109, c0110, c0115 | `route-pairs`, `route`, `fill-routed`, `check-routed`, `net`, `analyze` |
| 5 | c0116, c0117, c0118 | `export-package`, `testpoints` |

- `read_stage(path)` MUST read `STAGE` from the script's syntax tree, without running the script. A script without `STAGE`, or with a value outside 1 to 5, MUST make `run` exit 2 with a message that names `STAGE`.
- A stage MUST be set in the example only when every change it needs is archived under `openspec/changes/archive/`, or is named as cut, or as complete for a release (`complete for 0.4: c0100, …`: implemented on the release branch and archived at the release; the coordinator's decision of 2026-10-08), in the `Stages` section of `docs/evidence/yardstick.md`; the part of a cut change MUST then be left out of the example.
- A stage MUST count as reached only after one scheduled run of it has the verdict `passed`; the page MUST then name the date and the run.
- Each stage's additions MUST use the script calls, options and codes of the changes that own them; the yardstick MUST add none of its own. Where two changes offered one thing, the example uses the call that the maintainer's decisions of 2026-10-07 kept: c0102's `design.hole`, c0103's `rule_area`, c0113's `near` rules.
- No stage needs c0096, c0097, c0099, c0120 or c0141. The runner MUST read what they add when it is there (the report-limit mark of c0141, the measures of c0113) and MUST pass without it.

#### Scenario: Stage read without running the script
- **GIVEN** a script whose first statement raises an exception and which holds `STAGE = 2`
- **WHEN** `read_stage` reads it
- **THEN** it returns 2, and the exception is never raised

#### Scenario: Stage without its changes
- **GIVEN** the example with `STAGE = 2` while `c0100-board-layer-count` is not archived and the page names no cut
- **WHEN** `uv run pytest tests/unit/test_yardstick.py -k stage_needs` runs
- **THEN** it fails and names `c0100`

#### Scenario: Steps of stage 1
- **WHEN** `steps_for(1)` is called
- **THEN** it returns the steps of stage 1 in the order of the table, `bom`, `pnp` and `manifest` after `render`, `heavy-read` and `heavy-rt1` once for each heavy board, and no `route` step

### Requirement: Yardstick runner
`tools/yardstick.py run` SHALL take the example through the steps of its stage with the command-line interface, measure each step, and judge the run. It MUST use the standard library only.
- Each step MUST run as one child process `python -m fenolite <args> --json` in the output folder; the writing steps MUST pass `--seed 250025 --timestamp 2026-10-04T00:00:00Z --no-backup --confirm`; `check` MUST pass `--format concise`; `bom` MUST run as `bom <dir> --source model --out fab/bom.csv --manifest`, `pnp` as `pnp <dir> --out fab/pnp.csv --manifest` and `manifest` as `manifest <dir> --artifacts fab --no-check`, after `export` and `render` wrote into `fab`; `inspect` and the heavy steps MUST name a board file; `heavy-read` and `heavy-rt1` MUST run once for each of the two corpus rows tagged `heavy` that are demo boards, as one recorded step each. `build-install` MUST run as a dry-run build with `FENOLITE_LIBS_CACHE` removed from its environment.
- For each step, the runner MUST record the arguments, the exit code, the wall seconds of a monotonic clock, `peak_mib` from the `ru_maxrss` that `os.wait4` returns for the step's process (kibibytes on Linux, bytes on macOS), the bytes of the reply and the issue counts by code.
- It MUST read the stage's measures from the replies and the files: parts, nets, pads, copper layers, the bytes of the board and of `.fenolite/`, zone fills, DRC errors and warnings by type, KiCad's unconnected count with the report-limit mark of `check` (`summary.limits`, change c0141) when the reply holds one, the number of artefacts per state from the `manifest` reply, and from stage 4 the open connections that `route` and `net` report.
- It MUST apply the stage's acceptance rules: every step exits with the code its stage expects (`check`, on the board before routing, exits 5; from stage 4 `check-routed`, on the routed board, exits 0, or 5 with counts within the ratchets); every stage of `check` that ran (on `dev`: `model.validate`, `erc.kicad`, `copper.clearance`, `zone.fill`, `parity`, `netlist.assignment_compare`, `roundtrip`) is `ok` except `drc.kicad`, whose only error type is `unconnected_items`; `copper.clearance` has no finding and `netlist.assignment_compare` no difference; `bom`, `pnp` and `manifest` exit 0, and the manifest lists every file that `export`, `render`, `bom` and `pnp` wrote; `rebuild-dry` plans no write and `rebuild` leaves the bytes of the board unchanged; from stage 4 every stage of `check-routed` is `ok` except `drc.kicad`, whose error types are counted, and `length.rules`, each of whose error codes (`length.out-of-range`, `length.skew-out-of-range`) MUST be reported by `drc.kicad` as often under KiCad's type (`length_out_of_range`, `skew_out_of_range`), which counts it once, and the ratchets of "Yardstick budgets" hold for KiCad's open connections and the other DRC errors of the routed board; at stage 5 `fab/fenolite-artifacts.json` lists every file that `export-package` and `testpoints` wrote.
- **Accepted findings.** A finding that the example cannot remove because the defect is Fenolite's (an `erc.kicad` or `parity` finding on the schematic that `build` writes, for instance) MAY be accepted for a stage by one entry of `[stage<n>.accepted]` in the budgets file: the `check` stage, the finding's type, the reason, and the change or issue that owns the repair. An accepted type MUST be recorded with its count and MUST NOT fail the run; any other type still fails it. `unconnected_items` before stage 4 is the one type accepted without an entry.
- A failed `build` or `fill` MUST mark every later step `skipped`; any other failed step MUST let the next steps run.
- It MUST exit 0 when every step, rule and budget passes; 1 when one fails; 2 for a usage error or a missing `kicad-cli`, library cache, corpus row, router or budget table, naming what is missing.
- `row RECORD [--url URL]` MUST print one row of the `Runs` table of `docs/evidence/yardstick.md` for a record.

#### Scenario: A passing run
- **GIVEN** a fake `fenolite` that answers every step of stage 1 with the expected exit code and a reply that meets every rule
- **WHEN** `uv run pytest tests/unit/test_yardstick.py -k passing` runs `run` with it
- **THEN** the exit code is 0, and the record holds every step of stage 1, each with `seconds`, `peak_mib`, `reply_bytes` and `exit`

#### Scenario: A DRC error other than unconnected items
- **GIVEN** the same fake, whose `check` reply holds one `clearance` error in `drc.kicad`
- **WHEN** `run` runs at stage 1
- **THEN** the exit code is 1, and the record and the summary name `check` and `clearance`

#### Scenario: A rebuild that changes the board
- **GIVEN** a fake whose `rebuild` rewrites the board with other bytes
- **WHEN** `run` runs
- **THEN** the exit code is 1 and the failed rule names the board file
- **AND** a rebuild that leaves the board's bytes unchanged passes the rule although a later step (`route`) rewrites the board: the board is hashed right after the `rebuild` step

#### Scenario: Length findings of the routed board
- **GIVEN** a fake whose `check-routed` reply holds two `length.out-of-range` and one `length.skew-out-of-range` in `length.rules`, and `drc.kicad` two `length_out_of_range` and one `skew_out_of_range`, with a `drc_errors` ratchet of 3
- **WHEN** `run` runs
- **THEN** `check-routed.length.rules` passes and `ratchet.drc_errors` counts 3
- **AND** when `drc.kicad` holds one `length_out_of_range`, `check-routed.length.rules` fails and its detail names both counts

#### Scenario: A failed build
- **GIVEN** a fake whose `build` exits 3
- **WHEN** `run` runs
- **THEN** the exit code is 1, `build` is recorded with exit 3, and `fill` and every later step except `build-install` and the heavy steps are `skipped`

#### Scenario: No kicad-cli
- **GIVEN** a fake whose `capabilities` reply names no `kicad-cli`
- **WHEN** `run` runs
- **THEN** the exit code is 2 and the message names `kicad-cli`

#### Scenario: Peak memory units
- **WHEN** `peak_mib` is given an `ru_maxrss` of 1048576 on `darwin` and of 1024 on `linux`
- **THEN** it returns 1.0 in both cases

#### Scenario: An accepted finding is counted, another fails
- **GIVEN** a budgets file whose `[stage1.accepted]` names the stage `erc.kicad`, the type `power_pin_not_driven`, a reason and an owner, and a fake whose `check` reply holds two findings of that type and, in a second run, one `pin_not_connected` as well
- **WHEN** `uv run pytest tests/unit/test_yardstick.py -k accepted` runs `run` at stage 1 on each
- **THEN** the first exits 0 with the count 2 in the record under the accepted type, and the second exits 1 naming `erc.kicad` and `pin_not_connected`

### Requirement: Yardstick budgets
`tools/yardstick_budgets.toml` SHALL hold the budgets of each stage, and `run` SHALL judge every measured step against them.
- Each stage MUST have a table `[stage<n>]` with a `source`: `provisional`, or the ids of the scheduled runs its values were read from. A step's budget MUST be a table `[stage<n>.steps.<step>]` with `seconds` and `mib`; from stage 4 a table `[stage<n>.ratchets]` MUST hold `open_connections` and `drc_errors`. A table `[stage<n>.accepted]` MAY hold the accepted findings of "Yardstick runner", each with `stage`, `type`, `reason` and `owner`; an entry without one of the four MUST make `run` exit 2.
- A step whose seconds or `peak_mib` exceed its budget, or a count above its ratchet, MUST fail the run; the record and the summary MUST name the step, the value and the budget. A step without a budget MUST be recorded with `budget` null and fail nothing. A stage without a table MUST make `run` exit 2.
- Budgets read from runs MUST follow one rule: seconds are the median of the first three scheduled runs of the stage times 1.5, rounded up to 10 s; MiB the largest of them times 1.25, rounded up to 50 MiB; a ratchet the largest count of the three. Provisional budgets MUST be the local measurement times 4 for seconds and times 2 for MiB, rounded the same way. `tools/yardstick.py rebase RECORD …` MUST print the budgets that this rule gives, as TOML.
- Stage 1 MUST start with provisional values read from one local run of the runner on the example itself, on `dev`, by the provisional rule; the `Budgets` section of the page MUST name that run's commit, machine and date. The measurements of 2026-10-05 in the design were taken on a stand-in before `check` had the stages `erc.kicad` and `parity` and before `build` wrote a schematic: they MUST NOT be the source of a committed budget.
- A commit that raises a budget, or adds an accepted finding, MUST add a row to `docs/evidence/yardstick.md` that names the step or the type and the reason.
- Time and memory are measures of one runner, not facts of KiCad: a budget that holds MUST NOT raise an evidence label, and a budget that fails MUST NOT lower one.

#### Scenario: A step over its budget
- **GIVEN** a budget of 30 s for `build` at stage 1 and a fake `build` that takes 31 s
- **WHEN** `run` runs
- **THEN** the exit code is 1, and the summary names `build`, 31 and 30

#### Scenario: Budgets from three runs
- **GIVEN** three records of stage 1 whose `build` took 20 s, 30 s and 25 s with peaks of 200, 220 and 210 MiB
- **WHEN** `uv run python tools/yardstick.py rebase` reads them
- **THEN** it prints `seconds = 40` and `mib = 300` for `build`

#### Scenario: No table for the stage
- **GIVEN** a budgets file without `[stage2]` and an example at stage 2
- **WHEN** `run` runs
- **THEN** the exit code is 2 and the message names `stage2`

#### Scenario: Provisional budgets of stage 1
- **WHEN** `uv run pytest tests/unit/test_yardstick.py -k budgets_file` reads the committed file
- **THEN** it passes only if `[stage1]` exists, its `source` is `provisional` or names three runs that the page lists, and every step of stage 1 except the heavy steps has `seconds` and `mib`

### Requirement: Yardstick record
Each run SHALL leave a record, and `docs/evidence/yardstick.md` SHALL keep the series of the yardstick.
- The record MUST be JSON with `schema` set to `fenolite.yardstick-record.v0` and the keys `date`, `commit`, `stage`, `runner` (system, CPU count, memory), `tools` (the versions of `fenolite`, `kicad-cli` and the routers, from `capabilities`), `board` (the measures), `steps`, `rules` (each rule with its result), `accepted` (each accepted type with its count), `budgets` and `verdict` (`passed` or `failed`). Paths in it MUST be relative to the output folder.
- The page MUST hold the sections `How to read` (with the statement of provenance of "Yardstick board"), `Stages` (each stage `reached` with its date and run, `waiting` with the changes it waits for, or `not reached` with the cut change), `Runs` (date, commit, stage, run, total seconds, largest `peak_mib`, open connections, DRC errors, verdict, note), `Budgets` (where the current values come from) and `Not measured`.
- A row MUST be added to `Runs` when a stage is reached and before each release. The release record of every release made after the job's first scheduled run MUST name the newest scheduled run of the yardstick, its stage and its verdict; the releases up to 0.3.0 were made without one, and the page says so under `Not measured`.

#### Scenario: Record shape
- **WHEN** the passing run of "Yardstick runner" writes its record
- **THEN** the file loads as JSON with every key above, `stage` 1 and `verdict` `passed`, and holds no absolute path

#### Scenario: Row from a record
- **GIVEN** that record and `--url https://example.invalid/run/1`
- **WHEN** `uv run python tools/yardstick.py row <record> --url https://example.invalid/run/1` runs
- **THEN** it prints one Markdown table row with the record's date, commit, stage 1, the URL, the total seconds and `passed`

#### Scenario: Page guard
- **WHEN** `uv run pytest tests/unit/test_yardstick.py -k page` reads `docs/evidence/yardstick.md`
- **THEN** it passes only if the five sections exist, every stage from 1 to 5 has one state, and every row of `Runs` has a stage from 1 to 5 and a verdict `passed` or `failed`

### Requirement: Release record of v0.4
`docs/release/v0.4.md` SHALL record, change by change, what `0.4.0` ships of v0.4, guarded by `tests/unit/test_release_record_v04.py`.
- `## Verdict per change` MUST hold the table `| change | what ships | proof | job | open tasks | result |`, a row per change.
- Proofs and jobs follow the record of v0.2; a result is `ships`, `ships with deferred tasks` or `pending`.
- The guard MUST refuse a verdict over a `pending` row or a `TODO(coordinator)` placeholder.

#### Scenario: Every change present
- **WHEN** `uv run pytest tests/unit/test_release_record_v04.py` reads the committed record
- **THEN** every change of v0.4 has one row, and every proof and every job exists

#### Scenario: Verdict over a placeholder
- **GIVEN** a copy of the record that holds `TODO(coordinator)` and the verdict `Released as v0.4.0.`
- **WHEN** the guard runs on it
- **THEN** it fails and names the placeholder

### Requirement: Open tasks in the record of v0.4
The column `open tasks` of `docs/release/v0.4.md` SHALL follow the change's own `tasks.md`.
- Every unchecked task of that list MUST be named, and every number named MUST be a task of it.
- A row that `ships` names no task; a row `ships with deferred tasks` MUST have an entry under `## Deferred to the next release`, and a `pending` row one under `## Pending on the release branch`.

#### Scenario: An open task not named
- **GIVEN** a copy of the record whose row of c0081 does not name task 4.2
- **WHEN** the guard runs on it
- **THEN** it fails and names `c0081` and `4.2`

### Requirement: Sections of the record of v0.4
`docs/release/v0.4.md` SHALL hold `## Altium write`, `## Not in 0.4.0`, `## Runs and versions`, `## Recorded limits`, `## Release build`, `## Archive order`, `## Deferred after v0.4` and `## Maintainer's steps`.
- The runs, the limits, the build and the steps MUST say what those of v0.3 say, for the tag `v0.4.0`, and the runs MUST name the `yardstick` job.

#### Scenario: The yardstick run not named
- **GIVEN** a copy of the record whose runs do not name the `yardstick` job
- **WHEN** the guard runs on it
- **THEN** it fails and names `yardstick`

### Requirement: Follow-ups of the record of v0.4
`## Follow-ups found on 2026-10-08` of `docs/release/v0.4.md` SHALL name c0110 with `route.escape-skipped`, c0105, c0108, c0109, c0112, c0081, c0091, c0148, X8, Part V, Part G, R2, the `.cmd` launcher of `agent_eval` and c0151.

#### Scenario: A follow-up missing
- **GIVEN** a copy of the record whose follow-ups do not name c0151
- **WHEN** the guard runs on it
- **THEN** it fails and names `c0151`

### Requirement: Version 0.4.0
The version SHALL become `0.4.0` in the commit of change c0154, in `src/fenolite/__init__.py`, in `packaging/phenolite/pyproject.toml` and in its pin `fenolite==0.4.0`; later commits keep the three equal.
- `CHANGELOG.md` MUST hold `## [0.4.0] - <date>` under an empty `## [Unreleased]`, followed by `## [0.3.0]`, clean by the rules of `[0.2.0]`.
- No task of this change creates a tag, a release page or an upload.

#### Scenario: Versions agree
- **WHEN** `uv run pytest tests/unit/test_release_record_v04.py -k "version or changelog" tests/unit/test_pyproject_invariants.py` runs after the version commit
- **THEN** the package version, the alias version and the alias pin are `0.4.0`, and the headings of `CHANGELOG.md` start `Unreleased`, `0.4.0` and `0.3.0`

### Requirement: History row and roadmap of 0.4.0
`docs/evidence/residue-history.md` SHALL hold a row `v0.4.0` with the private gate `not run` and `0` hits, and `docs/roadmap.md` SHALL name the release change.
- The guard MUST fail at `0.4.0` without the row, or when it claims the private gate `on`.
- The milestone row of v0.4 MUST name `0.4.0` and MUST NOT say that its changes are not on `dev`.

#### Scenario: History row required
- **GIVEN** `__version__ == "0.4.0"` and a copy of `docs/evidence/residue-history.md` without the `v0.4.0` row
- **WHEN** the guard runs on it
- **THEN** it fails and names `docs/evidence/residue-history.md`
