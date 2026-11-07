## ADDED Requirements

### Requirement: Findings resolved by subject
`fenolite view --check FILE` SHALL resolve a finding that has an entry in the reply's `result.subjects` by its subjects first: a component or pad by its id or name in the scene's parts and pads, a net by its name, and SHALL fall back to the forms of `where` only for a finding without subjects or whose subjects are not in the scene. The Messages panel SHALL list each subject's name under its finding.

#### Scenario: A finding with an empty where
- **GIVEN** an authored `check` reply with one `circuit.rating-voltage` finding whose `where` is empty and whose subjects name the component `C1` and the net `V12`
- **WHEN** `uv run pytest tests/unit/view/test_check_overlay.py -k subjects` builds the overlay on the matching scene
- **THEN** the finding gets a box around `C1`, the panel lists `C1` and `V12` under it, and a reply without `result.subjects` resolves as before
