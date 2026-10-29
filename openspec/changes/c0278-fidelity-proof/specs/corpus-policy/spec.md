## ADDED Requirements

### Requirement: Round-trip fidelity use
`tests/corpus/manifest.toml` SHALL tag with the use `rtf` the KiCad demo project rows whose upstream licence is on the board library's allow-list (Apache-2.0, CERN-OHL, CC BY, CC BY-SA, GPL-2.0-or-later and the others of `docs/research/board-library.md`, section 3) and never a row under an NC or ND licence. Files derived from `rtf` rows MUST stay under pytest's temporary directory.

#### Scenario: Excluded licence
- **GIVEN** a manifest in which a row under CC BY-NC-SA carries `rtf`
- **WHEN** `uv run pytest tests/corpus/test_manifest.py -k rtf` checks it
- **THEN** it fails naming the row and its licence

#### Scenario: Fetch by use
- **WHEN** `uv run python tools/corpus_fetch.py --uses rtf` runs
- **THEN** it fetches exactly the rows tagged `rtf`

#### Scenario: Emitted code is derived
- **GIVEN** a `design.py` emitted from an `rtf` row and planted under `tests/data/`
- **WHEN** `uv run pytest tests/residue -q` runs with the corpus cache present
- **THEN** the residue test reports the file and the row id
