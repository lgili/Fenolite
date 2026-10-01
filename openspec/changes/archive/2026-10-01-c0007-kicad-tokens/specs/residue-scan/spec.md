## ADDED Requirements

### Requirement: Public format inventories are not token lists
The name check behind "No token list in the repository" (`tests/residue/test_no_token_list.py`) SHALL allow exactly one path whose name looks like a token list: `src/fenolite/backends/kicad/data/tokens.toml`, the public KiCad format inventory. Every other path matching the name check MUST still fail. The same test module SHALL check that the allowed file parses with `tomllib` and holds only the top-level keys `format` (equal to `1`), `collected_at`, `token`, `form` and `note`, and that every `token` and `form` row cites at least one id registered in `docs/evidence/sources.md`. A file at that path that fails the content check MUST fail the test.

#### Scenario: Allowed inventory passes
- **GIVEN** `src/fenolite/backends/kicad/data/tokens.toml` with `format = 1` and rows citing registered sources
- **WHEN** `uv run pytest tests/residue/test_no_token_list.py` runs
- **THEN** the test passes and the file is not reported

#### Scenario: Private list still rejected
- **GIVEN** a pull request adds `tools/residue/tokens.sha256`, or `src/fenolite/backends/kicad/data/tokens.txt`
- **WHEN** `uv run pytest tests/residue/test_no_token_list.py` runs
- **THEN** the test fails naming the file

#### Scenario: Inventory with foreign content rejected
- **GIVEN** `tokens.toml` gains a top-level `[[denylist]]` table
- **WHEN** `uv run pytest tests/residue/test_no_token_list.py` runs
- **THEN** the test fails naming the file and the key `denylist`
