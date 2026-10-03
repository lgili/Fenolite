## MODIFIED Requirements

### Requirement: Skip markers
Tests marked `needs_corpus` SHALL be skipped with the message `run: uv run python tools/corpus_fetch.py` when the cache is absent, and tests marked `needs_libs` SHALL be skipped when no KiCad library source is configured.

A KiCad library source for `needs_libs` is one of:
- a folder named by a `KICAD9_*` or `KICAD10_*` footprint or symbol variable of the environment
- a local KiCad install at the per-OS default location, or at the path in `FENOLITE_KICAD_INSTALL_DIR` when that variable is set; a path that does not exist means that no install is available
- a verified library cache: a `kicad-footprints` or `kicad-symbols` folder under `<cache>/<tag>/` whose `.fenolite-verified` stamp equals its pin (`kicad-library-resolution`, "Library pins"), where `<cache>` is `FENOLITE_LIBS_CACHE` when set and `~/.cache/fenolite/libs` otherwise

The `needs_libs` skip message MUST name the three ways to provide a source: setting `KICAD10_FOOTPRINT_DIR` and `KICAD10_SYMBOL_DIR`, installing KiCad, or running `uv run python tools/kicad_libs_fetch.py`. The required-resource mode of `ci-baseline` applies to `needs_libs` with this message.

#### Scenario: Corpus absent
- **GIVEN** an empty `~/.cache/fenolite/corpus/`
- **WHEN** `pytest -m needs_corpus` runs
- **THEN** every such test is reported as skipped with that message and the run exits 0

#### Scenario: No library source
- **GIVEN** `FENOLITE_KICAD_INSTALL_DIR` set to a path that does not exist, `FENOLITE_LIBS_CACHE` naming an empty folder, and no `KICAD9_*` or `KICAD10_*` library variable
- **WHEN** `uv run pytest tests/unit/test_conftest_libs.py` runs a pytester session with one `needs_libs` test
- **THEN** that test is skipped with the message naming the variables, the install and `tools/kicad_libs_fetch.py`, and the inner session exits 0

#### Scenario: Required libraries missing
- **GIVEN** the same environment and `FENOLITE_REQUIRE=libs`
- **WHEN** the pytester session runs
- **THEN** the `needs_libs` test fails with the same message

#### Scenario: Variables select the source
- **GIVEN** `FENOLITE_KICAD_INSTALL_DIR` set to a path that does not exist, `FENOLITE_LIBS_CACHE` naming an empty folder, and `KICAD10_FOOTPRINT_DIR` naming an existing folder
- **WHEN** the pytester session runs
- **THEN** the `needs_libs` test runs

#### Scenario: Verified cache selects the source
- **GIVEN** `FENOLITE_KICAD_INSTALL_DIR` set to a path that does not exist, no library variable, and `FENOLITE_LIBS_CACHE` naming a folder whose `10.0.6/kicad-footprints/.fenolite-verified` equals the 10.0.6 footprint pin
- **WHEN** the pytester session runs
- **THEN** the `needs_libs` test runs

#### Scenario: Stale cache does not count
- **GIVEN** the same folder, whose stamp names another tree hash
- **WHEN** the pytester session runs
- **THEN** the `needs_libs` test is skipped with the message of "No library source"

## ADDED Requirements

### Requirement: Demo library corpus rows
`tests/corpus/manifest.toml` SHALL list, at tags 10.0.6 and 9.0.9.1, the `fp-lib-table` of every demo folder whose boards place a footprint through a `${KIPRJMOD}` row of that table, and every `.kicad_mod` file that such a board places through such a row. The files are found through S-0024.
- Every such row MUST carry `libs`, `rt0` and `origin:kicad-demos` in `uses`. It MUST set `license`, `license_variant` and `embeddable = false` as "KiCad demo and third-party board rows" requires, and its id MUST use the kind `fplib` or `mod` of "Corpus rows carry no names outside URLs". The existing rows `kicad-demo-10-0-6-fplib-01` and `kicad-demo-10-0-6-mod-01` gain `libs` when they qualify.
- A file identical at both tags MUST be listed once, under its 10.0.6 URL, with `notes` ending in `identical at tag 9.0.9.1 (commit <short id>).`, as the board rows do.
- A file that the parser rejects as fetched MUST NOT be listed. When more files qualify than two-digit ids allow (99 per kind and tag), demo folders MUST be taken in name order up to the limit, and `docs/formats/kicad/corpus.md` MUST record the cut.
- `tests/corpus/test_manifest.py` SHALL check that every row whose `uses` contains `libs` also contains `rt0` and `origin:kicad-demos`.
- `tests/corpus/test_demo_libs.py` (`needs_corpus`) SHALL rebuild each listed demo folder of each tag T in `tmp_path`. The rebuild places, at the path that the row's URL gives inside the demo folder, every `libs` row and every non-heavy `rt0` board row of that folder whose URL is at T or whose `notes` name T as identical. The test SHALL read each rebuilt board with c0009's board reader and resolve every footprint whose `lib_ref` nickname is a row of the rebuilt `fp-lib-table`. It SHALL resolve through a `LibraryResolver` whose `project_dir` is the rebuilt folder, whose `config_home` is an empty folder, whose `env` is empty and whose `install_dir` does not exist. Any failure MUST fail the test. Footprints of other nicknames MUST be counted by issue code, and the counts written only to the report file named by `FENOLITE_CENSUS_OUT`.

#### Scenario: Library row without rt0
- **GIVEN** a row `kicad-demo-10-0-6-mod-02` with `uses = ["libs", "origin:kicad-demos"]`
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the row and `rt0`

#### Scenario: Demo projects resolve their own footprints
- **GIVEN** the cached `libs` rows and board rows, with `FENOLITE_REQUIRE=corpus`
- **WHEN** `uv run pytest tests/corpus/test_demo_libs.py` runs
- **THEN** every footprint of a rebuilt board whose nickname is a row of its project table resolves at both tags, and `git status --porcelain` is unchanged afterwards

#### Scenario: Other nicknames are counted
- **GIVEN** a rebuilt demo board that also places footprints of an official library, and `FENOLITE_CENSUS_OUT` naming a file under a temporary folder
- **WHEN** the same test runs
- **THEN** those footprints are counted under `kicad.lib.unknown-nickname` in that file, and the test passes

#### Scenario: Rows fetched by use
- **GIVEN** the manifest with `libs` rows
- **WHEN** `uv run python tools/corpus_fetch.py --uses libs` runs
- **THEN** only rows whose `uses` contains `libs` are fetched, and the summary counts them
