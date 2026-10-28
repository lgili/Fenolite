## ADDED Requirements

### Requirement: Generated copper passes the oracle
A board built from a script with every generated-copper call SHALL give no `kicad-cli` DRC violation type more entries than the same board built without those calls, unconnected items aside. On KiCad 10 the zones MUST be refilled first and no via may dangle; KiCad 9, which cannot refill from the command line, checks the unfilled board, where `via_dangling` is left aside. `H-K-GEN-DRC` MUST record the outcome per major.

#### Scenario: Fill and DRC of the bench
- **WHEN** `uv run pytest tests/kicad/dsl/test_generate_fill.py -rA` builds the bench for the running major, refills it on KiCad 10 and runs DRC
- **THEN** no violation type grows, and on KiCad 10 no `via_dangling` is reported
