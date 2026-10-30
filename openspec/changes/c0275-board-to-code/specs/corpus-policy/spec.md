## ADDED Requirements

### Requirement: Converted code stays out of the tool repository
Code that `fenolite import` writes from a corpus item or any third-party board SHALL be written only under pytest's temporary directory or the corpus cache, and MUST NOT be committed to the tool repository; converted boards live in the separate `fenolite-library` repository. A residue test MUST flag every tracked file that holds the line `Converted from` followed by a URL, unless the file also holds `Authored for Fenolite`.

#### Scenario: Converted corpus board planted
- **GIVEN** the code of a corpus board imported into a tracked folder in the test
- **WHEN** `uv run pytest tests/residue/test_converted_code.py -q` runs
- **THEN** the detector reports every emitted `.py` and its conversion line

#### Scenario: Authored import example passes
- **GIVEN** `examples/import_python/`, imported from a board authored for Fenolite and marked `Authored for Fenolite`
- **WHEN** the same test runs
- **THEN** no file of it is reported
