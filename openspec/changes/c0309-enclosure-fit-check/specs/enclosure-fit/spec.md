## ADDED Requirements

### Requirement: Enclosure judge
`fenolite.enclosure.judge.judge` SHALL judge a board against a fit record in the board frame: outline against usable area, holes against bosses, courtyards against boss and screw-head envelopes, zones present, board thickness, part heights per zone, face distances, apertures inside the flat rectangle and the minimum web. It MUST be pure, integer and deterministic.

#### Scenario: Seeded fixtures
- **WHEN** `uv run pytest tests/unit/enclosure/test_judge.py` judges the good board and each seeded bad board of `tests/data/enclosure/fit/`
- **THEN** the good board gives no error and no warning but `enclosure.model-unverified` (its box is assumed), and each bad board gives exactly its seeded code (`H-G-ENCL-FIT-CHECK`)

#### Scenario: Smaller outline reported
- **GIVEN** the good board with its outline inset by 3 mm on the front side
- **WHEN** it is judged
- **THEN** the issues hold one `enclosure.outline-inside` info and `summary.outline.margins.front` is `3_000_000`

### Requirement: Heights for the enclosure judge
A part's height SHALL be `outward_height` when known, else its conservative model top, else unknown. A body above the zone limit MUST give `enclosure.too-tall`; a model top above it `enclosure.height-unproved`; a model top at or below it a pass with `enclosure.height-from-model`; no height `enclosure.height-unknown`, never a pass.

#### Scenario: Three sources
- **GIVEN** a zone limit of 10 mm over `R1` with a 12 mm body, `U1` with no body and a model top of 8 mm, and `J1` with neither
- **WHEN** `uv run pytest tests/unit/enclosure/test_judge.py -k heights` judges it
- **THEN** the issues hold `enclosure.too-tall` for `R1`, `enclosure.height-from-model` for `U1` and `enclosure.height-unknown` for `J1`, and `summary.heights` is `{judged: 3, failed: 1, from_model: 1, unproved: 0, unknown: 1}`

### Requirement: Conservative model top
`fenolite.enclosure.bounds.model_top` SHALL return the top in nm of a millimetre ISO 10303-21 model from its `CARTESIAN_POINT`s and the centre-plus-radius boxes of its circles, spheres and tori, after the footprint's model scale, rotation and offset, and `None` for other units or an assembly with placement transforms. It MUST NOT be below the model's true top.

#### Scenario: Never below KiCad's mesh
- **WHEN** `uv run pytest tests/kicad/enclosure/test_model_top.py` compares `model_top` with the highest vertex of each part in `kicad-cli pcb export vrml` 10.0.x of one-part boards of the examples' official models
- **THEN** no model top is below the VRML top (`H-K-ENCL-MODEL-TOP`)

#### Scenario: Inch file refused
- **GIVEN** a model authored for Fenolite whose unit is `SI_UNIT($,.METRE.)` scaled to inches
- **WHEN** `model_top` reads it
- **THEN** it returns `None`

### Requirement: Enclosure judge in the build guard
With a fit, `fenolite build`'s placement guard SHALL run the enclosure judge on the planned board read back, report each finding with a severity no higher than `warning`, and add the family `enclosure` to `result.placement.rules`. A build MUST NOT refuse for a fit.

#### Scenario: A too tall part warns
- **GIVEN** `examples/enclosure/fit_box.py` with a part given `height=mm(40)` under `enc.top.lid`
- **WHEN** `uv run pytest tests/unit/cli/test_build_fit.py -k guard` builds it with `--dry-run --json`
- **THEN** the exit code is 0 and the issues hold `enclosure.too-tall` as a warning
