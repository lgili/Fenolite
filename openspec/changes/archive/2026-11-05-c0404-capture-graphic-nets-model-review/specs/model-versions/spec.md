## ADDED Requirements

### Requirement: Model review staleness check
`tools/model_review.py --check` SHALL exit 1 when a class, field, type, default, extension key or decision of the stored inventory differs from the current model, and SHALL exit 0 with a note when only reader locations differ. A unit test MUST run the check against the stored inventory.

#### Scenario: A renamed field
- **GIVEN** a stored inventory whose field name differs from the current model
- **WHEN** `tools/model_review.py --check` runs
- **THEN** the exit code is 1 and stderr says the inventory is stale

#### Scenario: Moved readers
- **GIVEN** a stored inventory that differs only in reader locations
- **WHEN** `tools/model_review.py --check` runs
- **THEN** the exit code is 0 and stdout says the reader locations moved
