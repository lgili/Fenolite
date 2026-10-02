## ADDED Requirements

### Requirement: Round-trip verdict
`fenolite.backends.kicad.roundtrip.rt1(text, *, file="") -> RoundTrip` SHALL compute in `src` the RT1 of "Same-version rebuild" on a board text `t`, as c0009 Decision 3 defines it:
- `tree_equal`: `tree_equal(rebuild_board(read_board(t)), parse(t))`;
- `model_equal`: the canonical JSON of `read_board(dumps(rebuild_board(read_board(t))))` equals that of `read_board(t)` when every `provenance` is set to `None`;
- `opaque_equal`: `opaque_count` and `opaque_digests` are equal on both reads.

`passed` MUST be the conjunction of the three, and `opaque_count` the count of the first read. `rt1` MUST raise the reader's errors (`FormatError` and its subclasses) unchanged.
- `RoundTrip.difference` MUST be the locator that c0006's `sexpr.first_difference(rebuilt, parsed)` returns when `tree_equal` is false, otherwise `model` when `model_equal` is false, otherwise `opaque` when `opaque_equal` is false, and `""` when RT1 passes. No second locator function is added.
- `KicadBackend.validate(path, *, issues=None) -> Validation` MUST return `Validation(read, rt1(text, file=…))` for a `.kicad_pcb` file, `read` being what `KicadBackend.read(path)` returns. For any other kind it MUST raise `ValueError` naming the kind.
- RT1 runs on the board only; comparing the board with `.fenolite/` belongs to c0019.

#### Scenario: Authored board passes
- **GIVEN** `tests/data/kicad/board/two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_roundtrip.py -k passes` calls `rt1` on its text
- **THEN** `passed` is true, `difference` is `""`, and `opaque_count` equals `pcb.opaque_count(read_board(text))`

#### Scenario: Altered pad located
- **GIVEN** `rebuild_board` patched to change the size of one pad of the authored board
- **WHEN** `rt1` runs on the authored board text
- **THEN** `passed` and `tree_equal` are false, and `difference` names that pad's locator

#### Scenario: Board validated through the backend
- **WHEN** `KicadBackend().validate(Path("tests/data/kicad/board/two_layer.kicad_pcb"))` is called
- **THEN** `validation.read` equals `KicadBackend().read(path)` and `validation.roundtrip.passed` is true

#### Scenario: Footprint file refused
- **WHEN** `KicadBackend().validate(Path("tests/data/libs/Mini.pretty/Mini_R_0603.kicad_mod"))` is called
- **THEN** a `ValueError` naming `kicad_mod` is raised
