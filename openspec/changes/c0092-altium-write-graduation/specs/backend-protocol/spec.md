## ADDED Requirements

### Requirement: Graduation of a write kind
`fenolite.backends.base.graduated(row, register, runs)` SHALL say whether the write of a matrix row may leave `experimental`, and what is missing when it may not. The write graduates when all of these hold:
- the kind names an own-readback test in its claims and that test is part of the suite;
- for a kind that carries a model (a PCB document, a schematic document, a project file), the row of the round-trip level RT-A3 for it is release-verified;
- every hypothesis id of the write cell is release-verified (`verification-evidence`, "Release-verified levels");
- at least one hypothesis id of the cell is `ALTIUM-VERIFIED(kit)` from a committed run that is not stale.

A write cell that graduates MUST NOT be listed in the row's `experimental`, and a write cell that does not MUST be listed. This holds for every backend; for the KiCad rows the fourth condition is replaced by a `KICAD-VERIFIED` hypothesis.
- The evidence matrix page MUST show, for each write cell that is experimental, the conditions that are missing.

#### Scenario: Evidence short by one row
- **GIVEN** a matrix row whose write cell names three hypotheses, one of them `INFERRED`
- **WHEN** `graduated` runs
- **THEN** it returns false and names that hypothesis

#### Scenario: Both directions are enforced
- **WHEN** `uv run pytest tests/unit/backends/test_graduation.py -k matrix` checks every row of every backend
- **THEN** each write cell is experimental exactly when `graduated` is false

#### Scenario: A stale run undoes graduation
- **GIVEN** a graduated kind whose only kit row is returned by `stale_rows`
- **WHEN** `graduated` runs
- **THEN** it returns false and names the stale run
