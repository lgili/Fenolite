## ADDED Requirements

### Requirement: Kit cases for panels
`docs/evidence/altium-pcb.md` SHALL hold Part Q, cases Q1 to Q12 of the design of change c0173, each with its steps for Altium Designer and its expected outcome; the maintainer's reports SHALL be recorded in the form of the native acceptance inventory, and saved native files MUST stay out of the repository.

#### Scenario: Gate follows the report
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py -k part_q` runs
- **THEN** it passes only when `pcbdoc.EMBEDDED_ARRAYS` is false or Part Q records Q7, Q8 and Q9 as passed, and every case Q1 to Q12 has an expected outcome
