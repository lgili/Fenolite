## ADDED Requirements

### Requirement: Enclosure document
`fenolite.model.enclosure` SHALL define the box model `fenolite.enclosure.v0`: identity (`fits`), `licence`, `provenance`, `outer`, `cavity`, `lid`, `obstacles`, `mounts` (`bosses`, `guides` or `floor`, each with `usable` and `zones`), `faces`, `clearances`, `tolerances` and `fields`, all lengths integer nm in the frame whose origin is the inside floor centre with Z up.

#### Scenario: A fixture box loads
- **GIVEN** `tests/data/enclosure/corner-bosses.enclosure.json`
- **WHEN** `uv run pytest tests/unit/model/test_enclosure.py -k loads` calls `load_enclosure`
- **THEN** it returns an `Enclosure` with one mount `bosses` holding four bosses, two obstacles, six faces and `licence == "CC0-1.0"`

### Requirement: Enclosure canonical form
`dump_enclosure` SHALL write the canonical form (two-space indent, LF, field order, defaults omitted, named lists sorted by name), and `load_enclosure` SHALL validate against `schemas/fenolite.enclosure.v0.json` and the structural rules, raising `FormatError` with the JSON pointer of the first violation.

#### Scenario: Round trip
- **WHEN** each fixture is loaded and dumped
- **THEN** the text equals the file byte for byte

#### Scenario: A float refused
- **GIVEN** a fixture whose `outer.length` is `120.5`
- **WHEN** it is loaded
- **THEN** `FormatError` names `/outer/length`

#### Scenario: A boss outside the floor
- **GIVEN** a fixture whose boss `B1` has `x` beyond half the floor length
- **WHEN** it is loaded
- **THEN** `FormatError` names `/mounts/0/bosses/0/x`

### Requirement: Enclosure provenance and evidence
Every document SHALL carry `provenance` (`basis`, `source`, `revision`, `read`, `author`) and `fields` with a `default` entry. Each `fields` and `tolerances` pointer MUST name an existing field; each `evidence` MUST be a level name no higher than `INFERRED`; `basis` MUST be `datasheet`, `measured`, `local-step`, `derived` or `assumed`.

#### Scenario: A label above INFERRED refused
- **GIVEN** a fixture whose `fields["/outer/length"].evidence` is `KICAD-VERIFIED`
- **WHEN** it is loaded
- **THEN** `FormatError` names `/fields/~1outer~1length/evidence`

### Requirement: Enclosure derivation
`fenolite.enclosure.derive.derive(box)` SHALL fill `usable` and `zones` of each mount from the cavity at board level, the draft, the obstacles that meet the board's Z range, the guides and the clearances, in integers, never larger than the exact area, and SHALL give derived fields the weakest evidence of their inputs.

#### Scenario: Hand-computed areas
- **WHEN** `uv run pytest tests/unit/enclosure/test_derive.py` derives the three fixtures
- **THEN** each usable ring and zone equals the one written by hand in the test, and no usable point lies inside a grown obstacle

#### Scenario: Deterministic
- **WHEN** `derive` runs twice on one fixture
- **THEN** `dump_enclosure` of both results is byte-identical

### Requirement: Enclosure fixtures authored for Fenolite
Fixture and example boxes SHALL have invented dimensions, `licence: "CC0-1.0"` and a provenance note that they were authored for Fenolite and fit no product. No vendor drawing, photo, STEP or logo MAY be committed.

#### Scenario: Fixture provenance
- **WHEN** `uv run pytest tests/unit/model/test_enclosure.py -k provenance` reads every `*.enclosure.json` under `tests/data/` and `examples/`
- **THEN** each has `licence == "CC0-1.0"` and a note containing "authored for Fenolite", and no `.step`, `.stp` or `.pdf` is in those folders
