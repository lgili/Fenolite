## ADDED Requirements

### Requirement: Gated and three-way differences
`fenolite diff A B --allow KINDS` SHALL exit 5 when the difference holds a change of a kind outside `KINDS`, naming each such change; and `fenolite diff BASE OURS --three-way THEIRS --out FILE` SHALL write `THEIRS` with the changes from `BASE` to `OURS` applied, under the mutation protocol, refusing with `diff.conflict` (exit 5, nothing written) when a changed item was also changed in `THEIRS`.
- For Altium documents, differences of bytes that decode to equal values within the format's units MUST be classified as `resave` and left out of the semantic difference.

#### Scenario: A change outside the allowed set
- **GIVEN** two boards that differ by a moved track and a changed rule
- **WHEN** `fenolite diff a.kicad_pcb b.kicad_pcb --allow track --json` runs
- **THEN** the exit code is 5 and the issues name the rule change
