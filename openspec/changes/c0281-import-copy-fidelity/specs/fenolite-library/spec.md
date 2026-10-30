## ADDED Requirements

### Requirement: Skipped levels in the proof gate
The proof gate SHALL accept a level `skipped` only when `fidelity.proof.skipped` gives its reason and the reason is not `build-failed`; the derived result is unchanged by a skipped level and MUST list the skipped levels with their reasons. Until c0278's level S runs on drawn imports, `S` skipped with `drawn-unavailable` passes.

#### Scenario: Level S skipped with a reason
- **GIVEN** a fixture proof whose levels are `equal` and whose `S` is `skipped` with `fidelity.proof.skipped.S` `drawn-unavailable`
- **WHEN** `uv run pytest tests/unit/library/test_proof_gate.py -k skipped` runs
- **THEN** the gate result is `pass` and lists `S: drawn-unavailable`; without the reason, or with `build-failed`, it is `fail`

### Requirement: Replayable conversion steps
A step of `conversion.steps` SHALL NOT hold `--plan`: a plan id hashes its working folder and cannot replay elsewhere. A writing step MUST be recorded with `--confirm` alone. `library audit` MUST give `library.provenance-invalid` for a step with `--plan`; `replay` runs each step as recorded.

#### Scenario: Step with a plan id
- **GIVEN** a fixture board item whose second step ends with `--confirm --plan 0123456789abcdef`
- **WHEN** `uv run pytest tests/unit/library/test_audit.py -k plan_step` runs
- **THEN** the audit reports `library.provenance-invalid` naming the step; with `--confirm` alone it passes, and its replay in a fresh folder gives the recorded `outputs_tree`
