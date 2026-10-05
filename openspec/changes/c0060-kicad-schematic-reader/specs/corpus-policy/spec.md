## ADDED Requirements

### Requirement: Schematic corpus rows
`tests/corpus/manifest.toml` SHALL contain one row per distinct `.kicad_sch` under `demos/` of the KiCad source repository at tags 10.0.6 and 9.0.9.1, and one row for each of the two S-expression schematics that the third-party repositories of S-0027 and S-0028 hold at their pinned commits. A file whose SHA-256 is identical at both tags is listed once, and `notes` names the other tag and the tag commit.
- **Ids.** New demo rows MUST have ids `kicad-demo-<tag>-sch-NNN` with three digits, and the third-party rows `third-party-sch-01` and `third-party-sch-02`. The row `kicad-demo-10-0-6-sch-01` keeps its id.
- **Uses.** Every row MUST carry `rt0`, `sch` and exactly one origin, and these content tags, computed from the file and its project:
  - `sch-root`: a project file of the same stem exists beside it at the same tag;
  - `sch-bus`: the file holds a `bus`, `bus_entry` or `bus_alias` child, or a label whose text is a bus (a vector `NAME[m..n]` or a group in braces);
  - `sch-multi`: the file holds a symbol with more than one use under one project, or more than one sheet reference of its project names it;
  - `sch-old`: its format version is below `READ_FLOOR[FileKind.SCHEMATIC]`;
  - `sch-9`: the file is in the demos at tag 9.0.9.1 (every row of that tag, and every row of tag 10.0.6 that is identical there). This tag is not recomputed from the file: it follows from the two tree listings (S-0024).
- **Licence.** Every row MUST set `license`, `license_variant` and `embeddable = false` as "KiCad demo and third-party board rows" requires, and a demo folder whose licence carries a non-commercial clause MUST NOT be listed.
- **Census.** `tests/corpus/test_schematic_census.py` (marker `needs_corpus`) MUST recompute the four content tags of every `sch` row from the cached files and MUST fail naming the row id when a tag is missing or wrong. It MUST write, through `tests/_boards.py::census`, the number of rows per tag, per format version and per origin, the root heads with their counts, and the number of rows that carry none of `sch-bus`, `sch-multi` and `sch-old`; the numbers are copied into `docs/evidence/kicad-schematic.md`.
- **Acceptance list.** The rows that carry `sch` and none of `sch-bus`, `sch-multi` and `sch-old` are the "schematics without bus and without multi-instance" of the project plan's v0.2a acceptance; no second list is kept.
- **Round trips.** `tests/corpus/test_schematic_rt.py` (marker `needs_corpus`) MUST run RT0 (`tree_equal(parse(dumps(parse(t))), parse(t))`) and RT1 (`sch.roundtrip_schematic`) on every demo row without `sch-old`, bus or not, and MUST record `opaque_count` per row. A row with `sch-old` MUST be counted as not read, with its format version.
- **Fetch.** The `kicad-10` job fetches the `sch` rows through its existing `--uses rt0` selection. The `kicad-9` job fetches only `--uses rt2-9` (`ci-baseline`, "KiCad 9.0 oracle job") and therefore no schematic row; `tools/corpus_fetch.py --uses sch-9` fetches the rows a run in the pinned 9.0.9 image needs.

#### Scenario: Tags recomputed
- **GIVEN** the `sch` rows cached, and a manifest in which one row with bus entries lacks `sch-bus`
- **WHEN** `uv run pytest tests/corpus/test_schematic_census.py` runs
- **THEN** it fails naming that row id and `sch-bus`

#### Scenario: Round trips over the demo rows
- **GIVEN** the `sch` rows cached
- **WHEN** `uv run pytest tests/corpus/test_schematic_rt.py -rA` runs with `FENOLITE_CENSUS_OUT` set
- **THEN** every demo row without `sch-old` passes RT0 and RT1, rows with `sch-old` are counted with their format version, and the census file holds one `opaque_count` per row read

#### Scenario: Acceptance list is a query
- **WHEN** the manifest rows with `sch` and without `sch-bus`, `sch-multi` and `sch-old` are selected
- **THEN** the selection is not empty, and each selected row passed RT0 and RT1 in the census

#### Scenario: Nothing derived is committed
- **WHEN** the two corpus tests have run
- **THEN** `git status --porcelain` and the SHA-256 of every cached file are unchanged

### Requirement: Upgraded schematic copies keep their origin
A copy of a `sch` row that `kicad-cli` 10.0.6 makes with `sch upgrade --force` SHALL count as that row's origin when an evidence rule needs files from two or more origins, under the conditions of "Upgraded copies keep their origin": made through the package runner (`KicadCli.upgrade_schematic`) from the cached file, kept only in memory or under `tmp_path`, never committed, used only by tests that carry `needs_corpus` and `kicad_min_major(10)`, and named as such in the result of the hypothesis row that relies on it.

#### Scenario: Third-party origin through upgraded copies
- **GIVEN** the cached rows `third-party-sch-01` and `-02`, below the read floor, and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/schematic/test_schematic_upgraded.py -q` runs with `FENOLITE_REQUIRE=kicad,corpus`
- **THEN** each upgraded copy is read and checked as origin `third-party`, and `git status --porcelain` is unchanged afterwards

## MODIFIED Requirements

### Requirement: Corpus rows carry no names outside URLs
Vendor, product and project names SHALL appear only inside the `url` field of manifest rows and in the URLs of `docs/evidence/sources.md`. The id of every row whose `uses` contains `rt0` MUST match `^(kicad-demo-\d+(-\d+){2,3}|third-party)-(pcb|sch|sym|mod|fplib|wks)-\d{2,3}$`. `notes`, `docs/formats/kicad/corpus.md` and test output MUST describe rows by id, tag, format version and licence only.

#### Scenario: Named id rejected
- **GIVEN** an `rt0` row whose id is built from its demo folder name
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the row and the expected pattern

#### Scenario: Three-digit id accepted
- **GIVEN** an `rt0` row with the id `kicad-demo-10-0-6-sch-104`
- **WHEN** the manifest test runs
- **THEN** it reports no id problem for that row
