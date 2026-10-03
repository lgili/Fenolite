# kicad-token-inventory Specification

## Purpose
Record, from public sources, every KiCad board and footprint token or value introduced after 8.0, the tokens 10.0 no longer writes, value-form changes, and the worksheet and rules vocabularies, with their minimum versions; generate `docs/formats/kicad/tokens.md` and check what a writer may emit for a target major.
## Requirements
### Requirement: Inventory file and loading
The token inventory SHALL be the package data file `src/fenolite/backends/kicad/data/tokens.toml`, read with `tomllib` through `importlib.resources`. It SHALL contain `format = 1`, `collected_at` (the KiCad tags the facts were collected at), and arrays `[[token]]`, `[[form]]` and `[[note]]`. A `[[note]]` records one dated board-format version from S-0030 with only `version` and either `rows` (the row ids it introduced) or `no_row`, whose value MUST be `"no-token-change"` or `"superseded-in-cycle"`. Notes MUST NOT carry free text.

`load_inventory()` SHALL cache the packaged file. When given text, it SHALL validate that text and return an `Inventory`. It MUST raise `FormatError`, naming the file and the row id, for any of these:
- an unknown key;
- a missing required key (`id`, `kinds`, `path`, `since_major`, `sources` for tokens; `id`, `kinds`, `since_major`, `description`, `sources` for forms);
- a duplicate `id` across tokens and forms;
- a duplicate (kinds, path, value);
- `since_major` outside `READ_MAJORS`;
- `since_version` whose `major_for` differs from `since_major`;
- `since_version` on a rules row;
- `until_major` not greater than `since_major`;
- `older_readers` other than `reject` or `ignore`;
- an empty `sources`;
- a `[[note]]` with both or neither of `rows` and `no_row`, an unknown `no_row` value, or an unknown row id.

#### Scenario: Packaged inventory loads
- **GIVEN** `fenolite` installed from the built wheel in an isolated environment
- **WHEN** `load_inventory()` is called
- **THEN** it returns an `Inventory` with at least one `[[token]]` row per kind `kicad_pcb`, `kicad_mod`, `kicad_wks` and `kicad_dru`

#### Scenario: Inconsistent dated version rejected
- **GIVEN** a row with `since_major = 9` and `since_version = 20250222`
- **WHEN** `load_inventory(text)` is called
- **THEN** `FormatError` is raised naming the row id and stating that `20250222` belongs to major 10

#### Scenario: Row without source rejected
- **GIVEN** a row with `sources = []`
- **WHEN** `load_inventory(text)` is called
- **THEN** `FormatError` is raised naming the row id

#### Scenario: Duplicate path rejected
- **GIVEN** two rows with the same kinds, path and value
- **WHEN** `load_inventory(text)` is called
- **THEN** `FormatError` is raised naming both ids

#### Scenario: Free-text note rejected
- **GIVEN** a `[[note]]` with `version = 20240929`, `rows = ["pad-padstack"]` and a `summary` key
- **WHEN** `load_inventory(text)` is called
- **THEN** `FormatError` is raised naming the note's version and the key `summary`

### Requirement: Inventory scope
The inventory SHALL contain:
- a `[[token]]` row for every board/footprint token name or symbol value introduced after the 8.0 constant, according to the dated versions of the board format (S-0030);
- a row with `until_major = 9` for every token that 10.0 no longer writes and that the fuzz shows 10.0 still reads, including the plot parameters `hpglpennumber`, `hpglpenspeed`, `hpglpendiameter` and `plotinvisibletext`, zone `filled_areas_thickness`, zone `net_name`, and the numbered board net table `/kicad_pcb/net`;
- a `[[form]]` row for every value-form change that a path cannot express, including items that reference nets by name (`20251028`);
- the worksheet vocabulary: the names on the public worksheet page (S-0035), plus names absent from that page that are confirmed one by one at 9.0.0 and 10.0.6 (S-0036) and proved by the oracle, including the legacy roots `page_layout` and `drawing_sheet`;
- the custom-rules vocabulary: the 9.0 manual's constraint types and clauses (S-0010) at `since_major = 9`, and the constraint types and disallow kinds present only in the 10.0 manual (S-0038) at `since_major = 10`.

Every dated version after the 8.0 constant up to the 10.0 constant in S-0030 SHALL have a `[[note]]`, and every row with `since_version` SHALL be listed by the note of that version. A note that introduces no token name, and no value a released reader parses differently, MUST carry a `no_row` reason.

#### Scenario: Complex padstack row present
- **GIVEN** the packaged inventory
- **WHEN** the rows of kind `kicad_mod` are listed
- **THEN** a row with kinds `kicad_pcb` and `kicad_mod`, path `pad/padstack`, `since_major = 9` and `since_version = 20240929` exists

#### Scenario: Rules drift rows present
- **GIVEN** the packaged inventory
- **WHEN** rows of kind `kicad_dru` are listed
- **THEN** the constraint values `bridged_mask`, `solder_mask_expansion`, `solder_paste_abs_margin`, `solder_paste_rel_margin` and `via_dangling`, and the disallow values `through_via` and `blind_via`, each have `since_major = 10`

#### Scenario: Obsolete net table row present
- **GIVEN** the packaged inventory
- **WHEN** `match(FileKind.BOARD, ["kicad_pcb", "net"])` is called
- **THEN** it returns a row with `since_major = 8` and `until_major = 9`, and `match(FileKind.BOARD, ["kicad_pcb", "segment", "net"])` does not return that row

#### Scenario: Worksheet name missing from the public page
- **GIVEN** a KiCad-written worksheet containing `(generator_version "10.0")`
- **WHEN** `check_emittable(node, FileKind.WORKSHEET, 10)` is called
- **THEN** no `kicad.token.uninventoried` issue is returned, because the row for `generator_version` cites S-0036 and has a committed fuzz result

#### Scenario: Dated row without note
- **GIVEN** a row with `since_version = 20250914` and no `[[note]]` for `20250914` listing it
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_inventory.py` runs
- **THEN** the test fails naming the row and the version

#### Scenario: Note without rows or reason
- **GIVEN** a `[[note]]` for `20250401` with neither `rows` nor `no_row`
- **WHEN** `load_inventory(text)` is called
- **THEN** `FormatError` is raised naming the note's version

### Requirement: Public-source discipline
Every row SHALL cite at least one id registered in `docs/evidence/sources.md`, and every `hypothesis` SHALL be registered in `docs/hypotheses.md`. A row with `since_version` MUST cite S-0030. Rows MUST be authored by hand. Files under `tools/`, `src/` and `tests/` MUST NOT read, parse or convert a KiCad keyword or grammar file. A keyword list (S-0033, S-0034, S-0036) MAY be cited only to confirm that a single name exists at a tag. It MUST NOT be a row's only source unless a committed fuzz result exercises the row.

#### Scenario: Unregistered source rejected
- **GIVEN** a row citing `S-9999`, which is absent from `docs/evidence/sources.md`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_inventory.py` runs
- **THEN** the test fails naming the row and `S-9999`

#### Scenario: Dated row without the dated source
- **GIVEN** a row with `since_version = 20240929` whose only source is S-0033
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_inventory.py` runs
- **THEN** the test fails naming the row and stating that a dated row must cite S-0030

#### Scenario: Keyword file reader rejected
- **GIVEN** a script under `tools/` that opens a file named `pcb.keywords`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_inventory.py` runs
- **THEN** the test fails naming the script

### Requirement: Path matching
A row path SHALL be a list of heads separated by `/`:
- a leading `/` anchors the path: it matches only a head chain equal to it; otherwise the path matches a suffix of the node's head chain;
- `#` matches a numeric head;
- a row with `value` matches a symbol atom that is a direct child of the matched node.

`Inventory.match(kind, chain, value)` SHALL return the most specific `[[token]]` row among rows whose kinds include `kind`: the longest pattern wins, then an anchored pattern wins over an unanchored one. It SHALL return `None` when no row matches. Form rows MUST NOT take part in matching.

#### Scenario: Suffix match under two parents
- **GIVEN** a row with path `tenting/front`
- **WHEN** `match(FileKind.BOARD, ["kicad_pcb", "setup", "tenting", "front"])` and `match(FileKind.BOARD, ["kicad_pcb", "via", "tenting", "front"])` are called
- **THEN** both return that row

#### Scenario: Most specific row wins
- **GIVEN** rows with paths `layer` and `pad/padstack/layer`
- **WHEN** `match(FileKind.FOOTPRINT, ["footprint", "pad", "padstack", "layer"])` is called
- **THEN** the row `pad/padstack/layer` is returned

#### Scenario: Other kind never matches
- **GIVEN** a row whose kinds are only `kicad_wks`
- **WHEN** `match(FileKind.BOARD, …)` is called with a chain the path would match
- **THEN** it returns `None`

#### Scenario: Form row never matched by path
- **GIVEN** the form row `net-by-name` with `applies_to = "net"` and no token row for `net` inside items
- **WHEN** `match(FileKind.BOARD, ["kicad_pcb", "segment", "net"])` is called
- **THEN** it returns `None`

### Requirement: Examples and controls
`tests/data/kicad/tokens/examples.toml` SHALL hold authored CC0 examples, ASCII only. Each example SHALL have `id`, `kinds`, and either `host` (a path in the skeleton), `mode` (`append` or `replace`) and `fragment`, or `file` (a whole authored file in the folder). An optional `exercises` SHALL list form-row ids; an unknown id MUST fail example loading. The skeletons and control files under `tests/data/kicad/tokens/` SHALL be declared `origin = "authored"` in `tests/data/MANIFEST.toml`.

The token rows an example exercises SHALL be the rows matched by every node of its fragment in its host context, or of its whole file; for `positive-baseline`, the rows matched in the skeleton. Form rows SHALL count only when listed in `exercises`.

These rows MUST be exercised by at least one example:
- every board, footprint and rules row whose `since_major` is above the kind's floor major (8 for board and footprint, 9 for rules);
- every row with `until_major`;
- every worksheet row;
- every form row.

Rules rows at the rules floor major MAY be exercised; those that are not SHALL cite `H-K-TOK-RULES-FLOOR`.

Control examples SHALL carry an explicit `expect` per major, MAY carry a fixed `header`, and SHALL include:
- a positive baseline per kind (for rules, the canary alone);
- invented-token negatives at top level and in `setup`, `segment`, `footprint` and `pad`;
- the lenient `general` case;
- a far-future board header, and the development header `20241030` (`dev-header-9`);
- the worksheet future-version and unknown-token pair;
- the rules canary with one invented constraint.

#### Scenario: Unexercised row
- **GIVEN** a row with `since_major = 10` that no example exercises
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_token_examples.py` runs
- **THEN** the test fails naming the row

#### Scenario: Example host missing from skeleton
- **GIVEN** an example whose `host` path does not exist in the board skeleton
- **WHEN** the harness builds cases
- **THEN** case building fails naming the example and the host

#### Scenario: Form row exercised explicitly
- **GIVEN** example `net-by-name` with a segment fragment containing `(net "A")` and `exercises = ["net-by-name"]`
- **WHEN** the harness computes the rows it exercises
- **THEN** they are exactly `["net-by-name"]`, and an example without `exercises` whose fragment contains `(net 1)` exercises no form row

#### Scenario: Unknown form id
- **GIVEN** an example with `exercises = ["net-by-number"]`, which is no form row
- **WHEN** the examples are loaded
- **THEN** loading fails naming the example and `net-by-number`

### Requirement: Expected outcomes
The harness SHALL derive each case's header and expected outcome from the inventory. For an image of major `M` and an example whose exercised rows (token and form) have highest `since_major` `S` (the kind's floor major when there are none):
- the case file SHALL carry header `FORMAT_VERSIONS[kind][min(M, S)]` for boards and footprints, the worksheet constant for worksheets, and the canary header for rules, unless the control fixes `header`;
- when an exercised row has `until_major < M`, the harness SHALL build a second case with header `FORMAT_VERSIONS[kind][M]` and expected outcome `load`;
- the expected outcome SHALL be `load` when `S ≤ M`, or when every exercised row with `since_major > M` has `older_readers = "ignore"`, and `reject` otherwise;
- `positive-baseline` SHALL run once per (kind, header) used by any case on that major, and a case whose header baseline did not load SHALL be `inconclusive`.

Controls use their explicit `expect`.

#### Scenario: 10.0 token on 9.0
- **GIVEN** an example exercising only rows with `since_major = 10`
- **WHEN** cases are built for major 9
- **THEN** the board case has header `20241229` and expected outcome `reject`

#### Scenario: 9.0 token on 10.0
- **GIVEN** an example exercising only rows with `since_major = 9`
- **WHEN** cases are built for major 10
- **THEN** the case has header `20241229` and expected outcome `load`

#### Scenario: Form example on 9.0
- **GIVEN** example `net-by-name` with `exercises = ["net-by-name"]` (form row `since_major = 10`)
- **WHEN** cases are built for major 9
- **THEN** the case has header `20241229` and expected outcome `reject`

#### Scenario: Obsolete token under the newer header
- **GIVEN** an example exercising only a row with `since_major = 8` and `until_major = 9`
- **WHEN** cases are built for major 10
- **THEN** there are two cases, with headers `20240108` and `20260206`, both expected to `load`

#### Scenario: Failing baseline makes cases inconclusive
- **GIVEN** a run on major 9 in which `positive-baseline` at header `20240108` did not load
- **WHEN** the results are recorded
- **THEN** every other board case with header `20240108` on that run has outcome `inconclusive`

### Requirement: Committed fuzz results
Results SHALL be committed as `docs/evidence/kicad/token-fuzz/<version>.json`, where `<version>` is the first line of `kicad-cli version` restricted to `[0-9A-Za-z.+-]`, for the pinned 9.0.9 image and for 10.0.6. They SHALL be sorted by (example, kind, header_version) and carry no timestamp. The header SHALL record the `kicad-cli` version, image, platform and the environment variables of the run. Each case records `example`, `kind`, `header_version`, `example_sha256`, `rows`, `expected`, `outcome` (`load`, `reject`, `timeout` or `inconclusive`), `exit_code` and a sanitised `detail`.

A row's evidence level on major `M` SHALL be `KICAD-VERIFIED` when no case exercising it on `M` mismatches its expectation and:
- if `M ≥ since_major`, at least one case on `M` exercising it has outcome `load`, and, when `until_major < M`, one such case has header `FORMAT_VERSIONS[kind][M]`;
- if `M < since_major`, at least one case on `M` in which it is the only exercised row with `since_major > M` has its expected outcome.

It SHALL be `INFERRED` otherwise; `inconclusive` cases never count.

`tests/unit/backends/kicad/test_token_results.py` MUST fail when:
- a case's `example_sha256` no longer matches the example;
- a case's recorded `rows` or recomputed `expected` differ from the current inventory;
- an `outcome` differs from `expected`;
- a row that must be exercised is not `KICAD-VERIFIED` on both committed majors and names no hypothesis.

#### Scenario: Stale result after editing an example
- **GIVEN** an example whose fragment changed after the results were committed
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_token_results.py` runs
- **THEN** the test fails naming the example and asking for a new fuzz run

#### Scenario: Unexpected acceptance
- **GIVEN** a committed 9.0.9 case with expected outcome `reject` and outcome `load`
- **WHEN** the test runs
- **THEN** it fails naming the example and the rows it exercises

#### Scenario: Rejection credited to the newest row only
- **GIVEN** an example `(tenting (front yes) (back yes))` exercising `tenting` (`since_major = 9`) and `tenting/front` (`since_major = 10`), rejected on 9.0.9 as expected
- **WHEN** row levels are computed
- **THEN** `tenting/front` is `KICAD-VERIFIED` on 9.0 through this case, and `tenting` gains nothing on 9.0 from it

#### Scenario: Undecided row with hypothesis
- **GIVEN** a form row whose cases are `inconclusive` on 9.0.9 and that names `H-K-TOK-NETNAME`
- **WHEN** the test runs
- **THEN** it passes and the row's level on 9.0 is reported as `INFERRED`

### Requirement: Generated token page
`tools/gen_token_docs.py` SHALL render `docs/formats/kicad/tokens.md` from the inventory and the committed results. The page SHALL have one line per row with id, kinds, path, value, since, until, sources, hypothesis, and the level on 9.0 and on 10.0, followed by the table of dated versions with their row ids or `no_row` reasons. `--check` MUST exit non-zero when the committed page differs from a fresh rendering.

#### Scenario: Drift detected
- **GIVEN** a row added to `tokens.toml` without regenerating the page
- **WHEN** `uv run python tools/gen_token_docs.py --check` runs
- **THEN** it exits non-zero naming `docs/formats/kicad/tokens.md`

### Requirement: Observed board paths are inventoried
`tests/kicad/test_token_census.py::test_observed_paths` (markers `needs_kicad`, `needs_corpus`, `kicad_min_major(10)`) SHALL compare the head chains of boards that `kicad-cli` 10.0.6 writes with those of boards that 9.0 wrote, and SHALL fail when a chain that only 10.0 writes is neither an inventory row nor proved readable by 9.0.9.
- **Sets.** The 10.0-written set MUST be the `pcb upgrade --force` copies, made in memory on 10.0.6, of the 21 readable non-heavy demo boards and of the three third-party boards, plus every cached native board whose header maps to major 10. The 9.0-written set MUST be every cached native non-heavy demo board with header `20241229` and `generator_version "9.0"`.
- **Chains.** A chain is the list of heads from the root to a node, with numeric heads read as `#`, as `Inventory.match` reads them ("Path matching").
- **Suspects.** A chain of the 10.0-written set that occurs in no board of the 9.0-written set is a suspect. Each suspect MUST be accounted for in one of three ways: it matches a token row (`load_inventory().match(FileKind.BOARD, chain)` is not `None`); one of its ancestor chains matches a token row whose `since_major` is 10 or later, because the writer gates that parent for target 9 with its children; or it is named in the test's mapping `FLOOR_CHAINS`, each entry of which cites an inventory example whose committed fuzz results load on 9.0.9.
- **Pending.** Suspects of the first run that cannot get a row or an example within this change MAY be listed in the explicit mapping `PENDING_CHAINS`, each with the change that will resolve it. An entry that is no longer a suspect MUST fail the test, so the list cannot go stale. `H-K-TOK-CENSUS` MUST stay `INFERRED` while `PENDING_CHAINS` is not empty.
- **Record.** The counts (chains of each set, suspects, suspects matched by a row, suspects accounted for by an ancestor's row, floor chains, pending chains) MUST be written through `tests/_boards.py::census` and copied into `docs/evidence/kicad-board-read.md`, as counts and head names only.

#### Scenario: Census on 10.0.6
- **GIVEN** the `rt0` corpus cached and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/test_token_census.py -rA` runs with `FENOLITE_CENSUS_OUT` set
- **THEN** every suspect matches a token row, has an ancestor with a 10.0 row, or is in `FLOOR_CHAINS` or `PENDING_CHAINS`, and the counts are written to the census file

#### Scenario: Uninventoried chain detected
- **GIVEN** a synthetic 10.0-written tree holding the chain `kicad_pcb/fenolite_probe`, which no 9.0-written tree, inventory row or floor entry holds
- **WHEN** `uv run pytest tests/kicad/test_token_census.py -k suspects_detected` runs the census function on it
- **THEN** the function returns `kicad_pcb/fenolite_probe` as an unresolved suspect

#### Scenario: Skipped on KiCad 9
- **GIVEN** the `kicad-9` job with `kicad-cli` 9.0.9
- **WHEN** `uv run pytest tests/kicad/test_token_census.py` runs
- **THEN** `test_observed_paths` is skipped and nothing fails

