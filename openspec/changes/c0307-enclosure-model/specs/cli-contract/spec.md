## ADDED Requirements

### Requirement: Enclosure show and derive
`fenolite enclosure show BOX [--mount NAME]` SHALL validate and derive a box model read-only, answering with `id`, `fits`, `licence`, `provenance`, `mounts`, `faces`, `weakest` and `drift`. `fenolite enclosure derive BOX` SHALL plan the document with fresh derived fields through the mutation protocol. A refused document MUST exit 3 with `FEN-3009`.

#### Scenario: Drift reported
- **GIVEN** a copy of a fixture whose stored `usable` ring has one point moved by 1 mm
- **WHEN** `uv run pytest tests/unit/cli/test_enclosure_show.py -k drift` runs `fenolite enclosure show <copy> --json`
- **THEN** the exit code is 5, the issues hold one `enclosure.model-drift` naming `/mounts/0/usable`, and `result.weakest` is `UNKNOWN` for the assumed fixture

#### Scenario: Derive writes only derived fields
- **WHEN** `fenolite enclosure derive <copy> --confirm` runs and then `show`
- **THEN** the written document differs from the input only under `/mounts/0/usable` and `/mounts/0/zones`, and `show` gives no drift

#### Scenario: Refused document
- **GIVEN** a document whose `schema` is `fenolite.enclosure.v9`
- **WHEN** `fenolite enclosure show <it> --json` runs
- **THEN** the exit code is 3 and stderr carries `FEN-3009` with `where == "/schema"`
