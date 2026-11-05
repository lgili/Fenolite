## ADDED Requirements

### Requirement: Kit cases for Draftsman documents
`docs/evidence/altium-draftsman.md` SHALL hold Part F: the observation files F0.1 to F0.14, the probes FP1 to FP5 and the cases F1 to F8 of change c0172's design, each with its expected outcome, and the maintainer's reports in the form of the native acceptance inventory. No Draftsman row MUST be `ALTIUM-VERIFIED` before its report is recorded.

#### Scenario: Every case has an outcome to check
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py -k part_f` runs
- **THEN** F0.1 to F0.14, FP1 to FP5 and F1 to F8 each appear with an expected outcome, and no `H-A-DWF-*` row is `ALTIUM-VERIFIED` without a recorded report
