## ADDED Requirements

### Requirement: Verify-source command
`fenolite verify-source SCRIPT --against ORIGINAL` SHALL be registered by `src/fenolite/cli/cmd_verify_source.py` with `mutates=True`, and SHALL build `SCRIPT` in a temporary folder, read the build and `ORIGINAL`, and compare them at every level. It MUST write nothing outside the temporary folder, which it removes, unless `--record` is given ("Recording the proof").

#### Scenario: Authored board proves itself
- **GIVEN** the authored fixture `tests/data/fidelity/sensor/` and its converted script `tests/data/fidelity/sensor_code/design.py`
- **WHEN** `fenolite verify-source tests/data/fidelity/sensor_code/design.py --against tests/data/fidelity/sensor --json` runs
- **THEN** the exit code is 0, `result.equivalent` is `true`, and both folders are unchanged

#### Scenario: Discoverable
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** `result.commands` holds `verify-source` with `mutates` `true` and `schema` `fenolite.verify-source.v0`

### Requirement: Verify-source inputs
`ORIGINAL` SHALL be a KiCad project folder or `.kicad_pro` file, read as a board with its schematic tree, or an Altium `.PrjPcb`, read by the Altium backend. `SCRIPT` MUST be a design script. A missing path MUST exit 3 with `FEN-3001`; an input no backend reads MUST exit 2 with `FEN-2001`. A KiCad file older than 9.0 MUST be refused with a hint, or upgraded on a copy with `--upgrade`.

#### Scenario: Old file refused
- **GIVEN** a project whose board header is older than the 9.0 format
- **WHEN** `fenolite verify-source design.py --against <it>` runs without `--upgrade`
- **THEN** the exit code is 3, and the hint names `--upgrade` and `kicad-cli pcb upgrade`

#### Scenario: Upgrade without the tool
- **GIVEN** the same project and no `kicad-cli`
- **WHEN** it runs with `--upgrade`
- **THEN** the exit code is 6 with `FEN-6001`

### Requirement: Build in a temporary folder
The command SHALL run `SCRIPT` as `fenolite build` runs it, with the drawn schematic it loads, for the KiCad major of `ORIGINAL` (9 or 10) or `--target`, into a fresh temporary folder, writing the planned files there without the confirmation step. No temporary path MUST appear in the output, and the folder MUST be removed on every exit, a signal included.

#### Scenario: No residue
- **WHEN** `uv run pytest tests/unit/cli/test_verify_source.py -k temp` runs the command and then lists the system temporary folder
- **THEN** no folder of the command remains, and the reply holds no temporary path

#### Scenario: Build failure
- **GIVEN** a script whose build gives `build.schematic-netlist-differs`
- **WHEN** the command runs
- **THEN** the exit code is 5, `issues` holds `fidelity.build-failed` and the build's error, and no level runs

### Requirement: Verify-source levels
The command SHALL run levels 1 to 7 with the strict rule of level 5, level S when both sides have a schematic that extraction reads, and level 8, unless `--levels` names a subset. A level a side cannot reach MUST be skipped with `fidelity.level-skipped` (info) and its reason, never passed silently. It MUST run no subprocess unless `--upgrade` is given.

#### Scenario: Altium original
- **GIVEN** the committed `tests/data/altium/blink/blink.PrjPcb` and the blink script
- **WHEN** the command runs with `--frame relative`
- **THEN** level S is skipped with the reason `altium-drawing-unread`, and the other levels run

#### Scenario: Hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** the command runs on the authored fixture
- **THEN** every level runs and the exit code is 0

### Requirement: Verify-source tolerances
Tolerances SHALL default to 0 nm, 0 µdeg, 0 ppm, the frame `absolute`, `--pixel-ppm` 1000 and `--render-pitch-um` 50, and MAY come from the `fidelity.tolerances` member of the provenance file; an option given on the command line overrides it. The tolerances used MUST be in the result.

#### Scenario: Provenance tolerance
- **GIVEN** a provenance file whose `fidelity.tolerances.length_nm` is 100
- **WHEN** the command runs without `--tolerance-nm`, and again with `--tolerance-nm 0`
- **THEN** `result.tolerances.length_nm` is 100 and then 0

### Requirement: Verify-source result
`result` SHALL validate against `schemas/fenolite.verify-source.v0.json` and hold `script` (name and SHA-256), `against` (name, backend and the SHA-256 of each read file), `build` (target and file count), `tolerances`, `levels` (one object per level with `level`, `name`, `status` of `equal`, `accepted`, `differs` or `skipped`, and counts), `equivalent`, `differences`, `accepted`, `notices` and `provenance`.

#### Scenario: Schema
- **WHEN** `uv run pytest tests/consistency -k verify_source` runs the command's `example_args`
- **THEN** `result` validates against the schema, and a reply with an extra key fails naming it

#### Scenario: Deterministic
- **WHEN** the command runs twice on the same inputs
- **THEN** the replies are equal except `elapsed_ms`

### Requirement: Verify-source exit codes
The exit code SHALL be 0 when every level run is `equal` or `accepted`, and 5 when any difference is neither excluded nor accepted. Issues MUST be the equivalence issues of every level ("Differences are located"), then the `fidelity.*` issues, then the readers' and the build's warnings. Evidence MUST combine the reads, the build and `INFERRED` for level 8.

#### Scenario: One planted difference
- **GIVEN** the authored script with one via moved by 0.1 mm
- **WHEN** the command runs
- **THEN** the exit code is 5 and `issues` holds one `equiv.via-missing` per side at level 5

### Requirement: Accepted differences in the provenance file
The command SHALL read `fidelity.accepted` of `PROVENANCE.json` beside `SCRIPT`, or of `--provenance FILE`: entries with `id`, `level`, `kind`, `where` (a glob), optional `field`, `reason`, `attribution` (`fenolite`, `upstream`, `tool` or `undecided`) and `decided`. Each entry MUST become an exclusion rule (`accepted_rules`), so a matched difference is `accepted`. A malformed entry MUST exit 3 with `FEN-3004`.

#### Scenario: A Fenolite limit accepted
- **GIVEN** the planted via difference and an entry of level 5, kind `via-missing`, `where` `GND:via:*`, attribution `fenolite`
- **WHEN** the command runs
- **THEN** the exit code is 0, the level status is `accepted`, and `result.accepted` names the entry

#### Scenario: Kind of another level
- **GIVEN** an entry of level 6 with kind `via-missing`
- **WHEN** the command runs
- **THEN** the exit code is 3 with `FEN-3004` naming the entry id

### Requirement: Unused accepted differences
An accepted entry that matches no difference in a run of its level SHALL give `fidelity.accepted-unused` (warning) naming its id, so an acceptance that a newer Fenolite no longer needs is removed. An entry of a level that the run skipped MUST give nothing.

#### Scenario: Fixed since
- **GIVEN** the accepted via entry and the unplanted script
- **WHEN** the command runs
- **THEN** the exit code is 0 and `issues` holds one `fidelity.accepted-unused` naming the entry

### Requirement: Recording the proof
With `--record`, the command SHALL plan one write of the provenance file whose `fidelity.proof` holds the Fenolite version, the date (`--timestamp`), the SHA-256 of the script and of the read originals, the tolerances and each level's status, and `--accept KEY --reason TEXT` (repeatable) SHALL add accepted entries for the named differences. It writes through `--dry-run` and `--confirm --plan`, keeping every other member's value.

#### Scenario: Record a passing proof
- **WHEN** the command runs on the authored fixture with `--record --timestamp 2026-11-01T00:00:00Z --dry-run`, then `--confirm --plan <id>`
- **THEN** the receipt lists `PROVENANCE.json`, whose `fidelity.proof.levels` holds every level as `equal`, and a second run plans the same bytes

#### Scenario: Accept needs a reason
- **WHEN** it runs with `--record --accept 5:via-missing:GND:via:top-bottom:1000,2000` and no `--reason`
- **THEN** the exit code is 2 with `FEN-2001`

### Requirement: Rendered layer masks
`fenolite.view.fidelity.render_masks(scene, *, pitch_nm, origin, size)` SHALL rasterise each layer of a board scene, or one schematic scene, into a run-length mask on a grid shared by both sides, with integer arithmetic only, zone outlines but no fills, and pixel-centre sampling. `compare_masks(a, b, *, pixel_ppm)` SHALL count the differing pixels farther than one pixel from the other mask and locate the largest region.

#### Scenario: Grid shared
- **WHEN** `uv run pytest tests/unit/view/test_fidelity_masks.py -k grid` renders a board and a copy moved by half a pixel
- **THEN** both masks have the same origin and size, and the comparison reports no difference at the default tolerance

#### Scenario: Located change
- **GIVEN** a copy with one silkscreen line removed
- **WHEN** the masks are compared
- **THEN** the result names the silkscreen layer and a box around the line, and `view.compare.compare` of the two scenes names the removed primitive in the hint

### Requirement: Fidelity issue codes
`fenolite.cli.cmd_verify_source.ISSUE_CODES` SHALL be the closed set `fidelity.build-failed` (error), `fidelity.accepted-unused` (warning), `fidelity.level-skipped` (info) and `fidelity.input-upgraded` (info), each with an `explain.toml` entry. There is no new `FEN-` code.

#### Scenario: Closed and explained
- **WHEN** `uv run pytest tests/unit/cli/test_verify_source.py -k codes` collects the codes the command emits
- **THEN** they equal `ISSUE_CODES`, and `fenolite explain fidelity.accepted-unused` exits 0

### Requirement: Round-trip test category
`tests/fidelity/` SHALL hold the round-trip tests: each reads an authored KiCad project, emits its code with `fenolite import --to python` (c0275) into a temporary folder, builds it and runs `verify-source` against the original, and passes only when every level is `equal` or accepted. The tests MUST run without `kicad-cli`, corpus or KiCad libraries.

#### Scenario: Authored fixtures
- **WHEN** `uv run pytest tests/fidelity -q` runs
- **THEN** every authored fixture passes every level, and no file is written outside `tmp_path`

#### Scenario: A regression shows
- **GIVEN** the KiCad writer patched in the test to drop junctions
- **WHEN** the same tests run
- **THEN** they fail with `item-missing` at level S naming the junctions

### Requirement: Round-trip corpus runs
`tests/kicad/fidelity/test_corpus_roundtrip.py` SHALL run the round trip on every corpus row of use `rtf`, in temporary folders only, and compare the counts of differences per level and kind with `tests/kicad/fidelity/accepted.toml`, which holds per row id only counts and a reason, never an upstream name or value. A count above its entry MUST fail; a count below MUST fail with a hint to lower the entry.

#### Scenario: Demo rows
- **WHEN** the test runs in the KiCad job with the corpus cached
- **THEN** each `rtf` row meets its entry, and the probe `fidelity-demos` records the counts per row

#### Scenario: Ratchet
- **GIVEN** an entry that allows two `text-field` differences for a row that now has none
- **WHEN** the test runs
- **THEN** it fails naming the row and the kind, with a hint to lower the entry

### Requirement: Fidelity evidence
`docs/evidence/fidelity.md` SHALL list, per `rtf` row, its id, licence, the levels that are `equal`, the accepted counts per kind with their attribution, and the Fenolite version and date of the run, naming rows by id only. Level 8 MUST be labelled `INFERRED`, because one renderer draws both sides.

#### Scenario: Page matches the run
- **WHEN** `uv run pytest tests/unit/test_fidelity_docs.py` reads the page and `tests/kicad/fidelity/accepted.toml`
- **THEN** every row of the file has a line on the page and the counts are equal

### Requirement: Fidelity documentation
`docs/fidelity.md` SHALL describe `verify-source`, its levels, tolerances, the provenance members `fidelity.accepted` and `fidelity.proof`, recording, the round-trip test category and how to read a failed level, and `docs/cli-contract.md` SHALL gain a section `verify-source`. The agent guide page `checks` MUST hold a tested line for the command and its codes.

#### Scenario: Codes documented
- **WHEN** `uv run pytest tests/unit/cli/test_verify_source.py -k docs tests/unit/agent/test_pages.py` runs
- **THEN** every code of `ISSUE_CODES` appears in `docs/cli-contract.md`, and the guide test passes
