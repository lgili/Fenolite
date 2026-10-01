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

