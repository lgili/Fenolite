## ADDED Requirements

### Requirement: Third-party material only in fenolite-library
`AGENTS.md` SHALL state under "Hard rules" that third-party material lives only in `fenolite-library` (github.com/lgili/fenolite-library), each item with its upstream licence, NOTICE and `PROVENANCE.json`, never in the tool repository. ADR-0003 SHALL carry a dated line saying the same. Private and employer material MUST stay forbidden in both repositories.

#### Scenario: Sentence present
- **WHEN** `uv run pytest tests/unit/test_legal_docs.py -k fenolite_library` runs
- **THEN** it finds the sentence in `AGENTS.md` naming `fenolite-library`, licence, NOTICE and `PROVENANCE.json`, and the dated line in ADR-0003

#### Scenario: Sentence removed
- **GIVEN** a copy of `AGENTS.md` without that sentence
- **WHEN** the same test runs on it
- **THEN** it fails naming the missing rule
