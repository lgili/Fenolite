## ADDED Requirements

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
