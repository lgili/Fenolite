## ADDED Requirements

### Requirement: Return paths
`fenolite.analysis.returns.analyze_returns(design, *, pads, nets)` SHALL report, per selected net, the parts of its tracks with no reference copper under them.
- The reference layers MUST be the neighbours in the copper layer order; the reference copper is the stored fill of the `reference` nets there, else of every other net.
- A span is a part of a centre line over no reference copper. It MUST be `split` when it lies inside its track, else `edge`.

#### Scenario: A track across a split plane
- **GIVEN** the authored bench of `tests/_returnbench.py`: a `GND` plane on `B.Cu` in two halves 4 mm apart, and `SIG1` on `F.Cu` across the gap
- **WHEN** `uv run pytest tests/unit/analysis/test_returns.py -k gap` runs the analysis for `SIG*`
- **THEN** `SIG1` has one `split` span of 4 mm between x 28 mm and x 32 mm, and the issues hold one `analysis.return-split`

#### Scenario: A track that leaves the plane
- **GIVEN** the same bench, where `SIG2` ends 1.5 mm beyond the plane
- **WHEN** `uv run pytest tests/unit/analysis/test_returns.py -k edge` runs the analysis
- **THEN** `SIG2` has one `edge` span of 1.5 mm and no finding

### Requirement: Via returns
`analyze_returns` SHALL pair each via of a selected net with the nearest via of a reference net, with the distance between their centres; with `via_distance`, a farther or missing one MUST be `analysis.return-via` (warning).

#### Scenario: A signal via and its ground via
- **GIVEN** the bench, where the via of `SIG4` lies 1 mm from a via of `GND`
- **WHEN** `uv run pytest tests/unit/analysis/test_returns.py -k vias` runs the analysis without a distance, with 2 mm and with 0.5 mm
- **THEN** the distance is 1 mm, and only the run with 0.5 mm holds one `analysis.return-via`

### Requirement: Returns kind in the analyze command
`fenolite analyze` SHALL accept `returns` in `--kinds` as a kind that is not in the default set.
- It needs `--net GLOB` (repeatable, shared with `length`); `--reference NET[,NET...]` and `--via-distance LENGTH` are optional and need the kind.
- `result.returns` MUST hold the rows, `result.summary.returns` the counts of nets, split and edge spans, and `result.inputs` its options. A violation of the option rules MUST be `FEN-2001` (exit 2).

#### Scenario: Returns through the command
- **GIVEN** the bench written as a KiCad board in `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_returns.py` runs `fenolite analyze <board> --kinds returns --net SIG1 --json`, and the same for `SIG4` with `--via-distance 0.5mm`
- **THEN** the first exits 0 with one split span and the folder unchanged, and the second holds one `analysis.return-via`

### Requirement: Return path codes
The table of analysis issue codes SHALL hold `analysis.return-split` and `analysis.return-via`, both with severity `warning`.

#### Scenario: Return codes in the table
- **WHEN** `uv run pytest tests/unit/analysis/test_findings.py -k return_codes` runs
- **THEN** each code has the severity `warning`
