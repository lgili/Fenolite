## ADDED Requirements

### Requirement: Printer layout measured on 10.0 writes
`tests/kicad/test_fmt_identity_10.py::test_byte_identity_kicad10` (markers `needs_kicad`, `needs_corpus`, `kicad_min_major(10)`, `slow`) SHALL measure how far `dumps(parse(f))` is from the layout that `kicad-cli` 10.0.6 writes, and SHALL never fail because of a difference, since byte identity with KiCad's printer is not a goal.
- **Files.** The test MUST use `pcb upgrade --force` copies, made in memory on 10.0.6, of every non-heavy `oracle` board of the corpus, and of `tests/data/kicad/board/two_layer.kicad_pcb` and the target-10 triad written by `write_board`.
- **Classes.** Each original line of a differing block MUST be counted once: as `xy-packing` when it holds `(xy `, otherwise in the class that `tests/corpus/test_fmt_identity_9.py::line_class` gives (`atom-list-wrap`, `atom-after-list`, `glued-lists` or `other`).
- **Record.** The files compared, the files byte-identical and the count per class MUST be written through `tests/_boards.py::census` and copied into a "10.0 writes" section of `docs/evidence/kicad-fmt-identity.md`. The test MUST fail only when no file could be compared.
- The outcome settles the 10.0 parts of `H-K-FMT-INDENT`, `H-K-FMT-XYWRAP`, `H-K-FMT-ATOMWRAP` and `H-K-FMT-MIXED`. The printer MUST NOT be changed because of it.

#### Scenario: Counts recorded
- **GIVEN** the `rt0` corpus cached and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/test_fmt_identity_10.py -rA` runs with `FENOLITE_CENSUS_OUT` set
- **THEN** it passes and the census file holds the files compared, the identical files and one count per class

#### Scenario: Differences never fail
- **GIVEN** `dumps` patched to add a space at the end of every line
- **WHEN** the test runs
- **THEN** it passes, no file is identical, and every original line is counted

#### Scenario: Skipped on KiCad 9
- **GIVEN** the `kicad-9` job with `kicad-cli` 9.0.9
- **WHEN** `uv run pytest tests/kicad/test_fmt_identity_10.py` runs
- **THEN** the test is skipped and nothing fails
