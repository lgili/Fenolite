# corpus-policy Specification

## Purpose
Describe the public test corpus with licences and hashes, fetch it reproducibly, and allow only public-domain or authored files to be committed.
## Requirements
### Requirement: Corpus manifest schema
`tests/corpus/manifest.toml` SHALL describe every external test file as a `[[file]]` table with the keys `id`, `url`, `ref`, `sha256`, `license` (SPDX identifier), `license_variant`, `embeddable` (boolean), `uses` (list of strings) and `notes`, and `tests/corpus/test_manifest.py` SHALL validate the schema.

#### Scenario: Missing sha256 rejected
- **GIVEN** a `[[file]]` entry without `sha256`
- **WHEN** `pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the entry id

### Requirement: Fetch with verification
`tools/corpus_fetch.py` SHALL download every manifest item into `~/.cache/fenolite/corpus/<id>/`, verify the SHA-256, refuse to keep a file whose hash differs, and print a summary of fetched, cached and failed items.

#### Scenario: Hash mismatch
- **GIVEN** a manifest entry whose `sha256` does not match the downloaded bytes
- **WHEN** `uv run python tools/corpus_fetch.py` runs
- **THEN** the file is deleted from the cache and the exit code is non-zero

### Requirement: Embeddable rule
A file committed under `tests/data/` or `examples/` MUST either be authored for Fenolite (declared `origin = "authored"` in `tests/data/MANIFEST.toml`) or reference a manifest item with `embeddable = true`, and `embeddable = true` SHALL be allowed only when `license` is `CC0-1.0` or the item is dedicated to the public domain.

#### Scenario: Share-alike file committed
- **GIVEN** a file under `tests/data/` referencing a manifest item with `license = "CC-BY-SA-4.0"`
- **WHEN** `pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails stating the file is not embeddable

#### Scenario: Authored fixture accepted
- **GIVEN** `tests/data/blink.kicad_pcb` declared with `origin = "authored"`
- **WHEN** the test runs
- **THEN** the file is accepted

### Requirement: Skip markers
Tests marked `needs_corpus` SHALL be skipped with the message `run: uv run python tools/corpus_fetch.py` when the cache is absent, and tests marked `needs_libs` SHALL be skipped when no KiCad library source is configured.

A KiCad library source for `needs_libs` is one of:
- a folder named by a `KICAD9_*` or `KICAD10_*` footprint or symbol variable of the environment
- a local KiCad install at the per-OS default location, or at the path in `FENOLITE_KICAD_INSTALL_DIR` when that variable is set; a path that does not exist means that no install is available

The `needs_libs` skip message MUST name both ways to provide a source: setting `KICAD10_FOOTPRINT_DIR` and `KICAD10_SYMBOL_DIR`, or installing KiCad. The required-resource mode of `ci-baseline` applies to `needs_libs` with this message.

#### Scenario: Corpus absent
- **GIVEN** an empty `~/.cache/fenolite/corpus/`
- **WHEN** `pytest -m needs_corpus` runs
- **THEN** every such test is reported as skipped with that message and the run exits 0

#### Scenario: No library source
- **GIVEN** `FENOLITE_KICAD_INSTALL_DIR` set to a path that does not exist and no `KICAD9_*` or `KICAD10_*` library variable
- **WHEN** `uv run pytest tests/unit/test_conftest_libs.py` runs a pytester session with one `needs_libs` test
- **THEN** that test is skipped with the message naming the variables and the install, and the inner session exits 0

#### Scenario: Required libraries missing
- **GIVEN** the same environment and `FENOLITE_REQUIRE=libs`
- **WHEN** the pytester session runs
- **THEN** the `needs_libs` test fails with the same message

#### Scenario: Variables select the source
- **GIVEN** `FENOLITE_KICAD_INSTALL_DIR` set to a path that does not exist and `KICAD10_FOOTPRINT_DIR` naming an existing folder
- **WHEN** the pytester session runs
- **THEN** the `needs_libs` test runs

### Requirement: Measurement versus embedding
Files from reciprocal or share-alike sources (`embeddable = false`) MAY be used to measure formats and to run tests after fetching, and MUST NOT be copied, in whole or in part, into the repository, into seeds or into generated fixtures.

#### Scenario: Derived seed from a non-embeddable donor
- **GIVEN** a seed file under `src/fenolite/` whose bytes contain a stream copied from a manifest item with `embeddable = false`
- **WHEN** `pytest tests/residue` runs with the corpus cache present
- **THEN** the test fails naming the seed and the donor id

### Requirement: KiCad demo and third-party board rows
`tests/corpus/manifest.toml` SHALL contain the following rows:
- one row per distinct `.kicad_pcb` under `demos/` of the KiCad source repository at tags 10.0.6 and 9.0.9.1. A file whose SHA-256 is identical at both tags is listed once, and `notes` names the other tag and the tag commit.
- one schematic, one symbol library, one footprint, one footprint-library table and one worksheet from the demos at 10.0.6
- the Apache-2.0 third-party boards registered as sources S-0027 and S-0028

Every row MUST set `license` from the repository-level statement. It MUST record any per-folder licence in `license_variant`, and it MUST set `embeddable = false`. A demo folder whose licence carries a non-commercial clause MUST NOT be listed. Every row MUST carry exactly one of `origin:kicad-demos` and `origin:third-party` in `uses`, and either `rt0` or, for a file that its source publishes malformed so that the parser rejects it as fetched, `malformed` (never both); a `malformed` row's `notes` MUST name the rule the parser reports. Board rows that carry `rt0` MUST also carry `oracle`, and files larger than 20 MB MUST also carry `heavy`.

#### Scenario: Non-commercial folder excluded
- **GIVEN** a manifest row whose `license_variant` mentions a non-commercial licence
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the row id

#### Scenario: Missing origin
- **GIVEN** an `rt0` row whose `uses` has no `origin:` value
- **WHEN** the manifest test runs
- **THEN** it fails naming the row id

#### Scenario: Heavy file untagged
- **GIVEN** a row whose fetched file is larger than 20 MB and whose `uses` lacks `heavy`
- **WHEN** `uv run pytest tests/corpus/test_manifest.py -m needs_corpus` runs
- **THEN** the test fails naming the row id

#### Scenario: File published malformed
- **GIVEN** the demo board at tag 9.0.9.1 whose published bytes close the root list early (a spliced line), listed with `uses = ["malformed", "origin:kicad-demos"]`
- **WHEN** `uv run pytest tests/corpus/test_rt0.py::test_malformed_items_rejected` runs with the file cached
- **THEN** the parser raises `FormatError` with the rule named in the row's `notes` (`content after the root list`), and the RT0 tests do not include the row

#### Scenario: Share-alike demo is not embeddable (regression case)
- **GIVEN** a demo row with `license = "CC-BY-SA-4.0"` and `embeddable = true`
- **WHEN** the manifest test runs
- **THEN** the existing embeddable rule fails it, stating that only CC0 or public-domain items may be embeddable

### Requirement: Corpus rows carry no names outside URLs
Vendor, product and project names SHALL appear only inside the `url` field of manifest rows and in the URLs of `docs/evidence/sources.md`. The id of every row whose `uses` contains `rt0` MUST match `^(kicad-demo-\d+(-\d+){2,3}|third-party)-(pcb|sch|sym|mod|fplib|wks)-\d{2}$`. `notes`, `docs/formats/kicad/corpus.md` and test output MUST describe rows by id, tag, format version and licence only.

#### Scenario: Named id rejected
- **GIVEN** an `rt0` row whose id is built from its demo folder name
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the row and the expected pattern

### Requirement: Selective fetch by use
`tools/corpus_fetch.py` SHALL accept `--uses TAG` (repeatable; an item is kept if it has any of the tags) and `--exclude-uses TAG` (repeatable; an item with any of the tags is dropped). It SHALL store each file under `<cache>/<id>/<name>`, where `<name>` is the URL-decoded last path segment of the URL.

#### Scenario: Heavy files skipped
- **GIVEN** a manifest with one `rt0` item and one `rt0` + `heavy` item
- **WHEN** `uv run python tools/corpus_fetch.py --uses rt0 --exclude-uses heavy` runs
- **THEN** only the first item is fetched and the summary counts one item

#### Scenario: Encoded space in a URL
- **GIVEN** an item whose URL path ends in `demo%20board.kicad_pcb`
- **WHEN** it is fetched
- **THEN** the cached file is named `demo board.kicad_pcb`

### Requirement: Derived corpus files stay out of the repository
Files derived from non-embeddable corpus items, such as copies re-saved by `kicad-cli pcb upgrade`, re-dumped by Fenolite, or cut out of a corpus board, MUST be written only under pytest's temporary directory or the corpus cache. They MUST NOT be committed, and they MUST NOT be used as fixtures or seeds. A residue test SHALL flag every `.kicad_*` file under `tests/data/` or `examples/` that is tree-equal to a cached corpus item, or that shares at least three identifier values with one. Identifier values are the atoms of `uuid` and `tstamp` lists, compared after lowercasing and removing `-` and leading zeros, and counted only when at least 8 hex digits remain.

#### Scenario: Partial copy committed
- **GIVEN** a file planted in `tmp_path` that holds one footprint cut out of a cached corpus board, with its identifiers
- **WHEN** `uv run pytest tests/residue/test_derived_corpus.py` runs with the corpus cache present
- **THEN** the detector reports the file and the corpus id

#### Scenario: Upgraded copy committed
- **GIVEN** `kicad-cli` 10.0.x and a copy of a cached corpus board upgraded with `pcb upgrade --force` into `tmp_path`
- **WHEN** the same test runs
- **THEN** the detector reports the upgraded copy, although it is not tree-equal to the original

#### Scenario: Authored fixture passes
- **GIVEN** the authored CC0 fixtures under `tests/data/kicad/sexpr/`
- **WHEN** the same test runs
- **THEN** none of them is reported

