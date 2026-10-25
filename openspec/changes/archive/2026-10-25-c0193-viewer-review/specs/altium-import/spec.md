## ADDED Requirements

### Requirement: Embedded body models
`fenolite.backends.altium.models3d.body_models(path)` SHALL give the embedded model of each component body of a PCB document that names one (`MODEL.MODELTYPE=1` and a `MODELID` that is an entry of `Models`). `AltiumBackend.body_models` SHALL delegate to it.
- `Models/Data` MUST be read as a run of records, each a 32-bit length and a property text. Record `n` names the stream `Models/<n>`, whose bytes MUST be inflated with `zlib`. A record whose stream is missing or does not inflate MUST be skipped with one issue.
- `position` MUST be `MODEL.2D.X` and `MODEL.2D.Y` as the units module turns a point, `z` MUST be `MODEL.3D.DZ`, and `rotation` MUST be `MODEL.3D.ROTX`, `ROTY` and `ROTZ` in microdegrees. The rotation keys of the `Models/Data` record MUST NOT be applied.
- `locator` MUST be the body's locator as the adapter gives it (`ComponentBodies6/Data#<index>`).
- The facts MUST be rows of `docs/formats/altium/pcb-bodies.md` with the hypothesis `H-A-BODY-MODEL-PLACE`, measured on the corpus.

#### Scenario: Models of a corpus document
- **WHEN** `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_bodies.py -k body_models` reads the fetched PCB documents
- **THEN** every body with `MODEL.MODELTYPE=1` and a `MODELID` in `Models` yields one `BodyModel` whose data starts with the STEP header `ISO-10303-21`, and its locator names a body of the imported design

#### Scenario: An authored document without models
- **WHEN** `uv run pytest tests/unit/backends/altium/test_models3d.py` reads `tests/data/altium/body2/body2.PcbDoc`
- **THEN** `body_models` returns an empty tuple and raises nothing
