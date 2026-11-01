## ADDED Requirements

### Requirement: Portable byte-fidelity proofs

Portability tests SHALL compare canonical UTF-8 bytes using binary output, interpret native paths as paths and parse shell-quoted commands as argument sequences. They MUST retain exact payload equality assertions.

#### Scenario: A Windows path needs quoting
- **WHEN** a conflict hint quotes an output path
- **THEN** the test verifies its parsed output argument against the expected path

### Requirement: Container-local corpus temporary files

The KiCad 10 CI job SHALL place pytest temporary files in a directory available inside its container and collect import-census artifacts from the same directory.

#### Scenario: Host temporary paths differ from container paths
- **WHEN** the oracle and corpus test step starts
- **THEN** pytest can create its base directory and the artifact step searches that directory

### Requirement: Import census covers selected corpus rows

The recorded import census SHALL include every licence-eligible KiCad 10.0.6 demo-board row selected by the corpus test, including heavy rows. A unit preflight MUST check coverage without fetching or importing boards. Measurements MUST identify their source pins and CI commit/version; the corpus test MUST still require exit 0, exact equivalence and matching omitted-kind counts.

#### Scenario: Heavy imports pass before the missing record fails
- **GIVEN** CI emits exit 0 and equivalent=true for rows 06 and 18 but their census rows are absent
- **WHEN** the aggregate measurements are recorded
- **THEN** the preflight finds all selected rows, and the existing heavy import assertions remain active
