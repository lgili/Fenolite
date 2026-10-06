## ADDED Requirements

### Requirement: Repeated-sheet projects in the corpus run
The corpus run of `fenolite check` on Altium project sets SHALL be measured again with channels instantiated, and `docs/evidence/altium-roundtrip.md` SHALL hold the new counts of every set with, for each remaining difference of `altium-set:02`, its cause.
- The page MUST NOT name the pin-to-pad map as the only cause of that set's counts.
- A set whose counts change other than `altium-set:02` MUST be explained on the page.

#### Scenario: Page states the causes
- **WHEN** `uv run pytest tests/unit/test_provenance.py -k roundtrip` reads the page
- **THEN** a note under the table lists the remaining differences of `altium-set:02` by cause, and says that its remaining `model.duplicate-ref` comes from components without a designator, not from channels
