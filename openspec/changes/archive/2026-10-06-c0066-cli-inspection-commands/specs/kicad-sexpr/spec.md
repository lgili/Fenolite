## ADDED Requirements

### Requirement: Canonical print check
`fenolite.backends.kicad.sexpr.canonical(text, *, file="") -> str` SHALL return the canonical print of a KiCad S-expression text, `dumps(parse(text, file=file))`, and `sexpr.first_line_difference(a, b) -> int | None` SHALL return the number of the first line, from 1, at which two texts differ, or `None` when they are equal.
- `canonical` MUST raise the parser's `FormatError` for a text that does not parse and the printer's `ValueError` for a tree with comments below the root; it MUST change no atom, so `tree_equal(parse(canonical(t)), parse(t))` holds for every text it accepts.
- `canonical(canonical(t))` MUST equal `canonical(t)` byte for byte.
- `tests/corpus/test_fmt_idempotent.py` (marker `needs_corpus`) MUST prove both properties on every `rt0` row of the corpus, schematic rows included, and on every authored KiCad file under `tests/data/`, and MUST count by reason the rows that `canonical` refuses (`H-K-FMT-IDEMPOTENT`). The counts are written through `tests/_boards.py::census` and copied into `docs/evidence/kicad-fmt-identity.md`.
- The canonical print is Fenolite's layout ("KiCad-style serialisation"), not KiCad's: whether KiCad writes the same bytes is measured by the `H-K-FMT-*` rows and is not claimed here.

#### Scenario: Fixed point on an authored board
- **WHEN** `canonical` is applied twice to the text of `tests/data/kicad/board/two_layer.kicad_pcb`
- **THEN** the two results are equal, and each parses tree-equal to the file

#### Scenario: First differing line
- **GIVEN** a canonical text and the same text with two blanks added at the end of line 3
- **WHEN** `first_line_difference` compares them
- **THEN** it returns 3, and `None` for the text against itself

#### Scenario: Corpus is a fixed point
- **GIVEN** the `rt0` corpus cached
- **WHEN** `uv run pytest tests/corpus/test_fmt_idempotent.py -rA` runs with `FENOLITE_CENSUS_OUT` set
- **THEN** every row that `canonical` accepts passes both properties, and the census holds the number of rows refused, by reason

#### Scenario: Authored files without the corpus
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_sexpr_dumps.py -k canonical` runs on the authored `.kicad_*` S-expression files under `tests/data/`
- **THEN** each accepted file passes both properties
