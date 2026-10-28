## ADDED Requirements

### Requirement: Published conformance matrix
`tools/gen_evidence_matrix.py` SHALL write, beside `docs/evidence/matrix.md`, the conformance matrix in two forms: `docs/evidence/conformance.json` (schema id `fenolite.conformance.v1`), one row per backend, file kind, operation and format version with the tool, the level and the source, and `docs/evidence/conformance.md`, one table per backend. A version's `source` MUST name a test file of the repository or a kit run recorded under `docs/evidence/altium-kit/`; `tools/gen_evidence_matrix.py --check` MUST exit 1 for a source that names neither, and for a committed page that differs from a fresh generation. The release workflow (`.github/workflows/release.yml`) MUST attach `docs/evidence/conformance.json` to the GitHub release it publishes.

#### Scenario: A source that does not exist
- **GIVEN** a `claims` module that lists a version whose `source` is `tests/kicad/test_missing.py`
- **WHEN** `uv run python tools/gen_evidence_matrix.py --check` runs
- **THEN** it exits 1 and names the row and the source

#### Scenario: The release attaches the matrix
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k conformance` reads `.github/workflows/release.yml`
- **THEN** the publish job uploads `docs/evidence/conformance.json` as a release asset
