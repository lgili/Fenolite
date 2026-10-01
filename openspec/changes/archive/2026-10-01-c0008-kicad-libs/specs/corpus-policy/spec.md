## MODIFIED Requirements

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
