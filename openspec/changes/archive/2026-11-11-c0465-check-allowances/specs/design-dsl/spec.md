## ADDED Requirements

### Requirement: Short and antenna rules in the DSL
`design.rules.rule()` ("Rule constructor in the DSL") SHALL take the kinds `short` and `antenna` (change
c0465).
- A `short` rule MUST take `between` and no limit: a limit MUST raise `DslError`, and so MUST a missing
  `between`. Its `severity` says what a short between the two sides is (`ignore` allows it).
- An `antenna` rule MUST take `max` alone, 0 or more: another limit or a `between` MUST raise `DslError`.
- The agent guide MUST teach both with a tested line (`tests/unit/agent/test_pages.py`).

#### Scenario: Declaring an allowance
- **WHEN** `uv run pytest tests/unit/dsl/test_rule_allowances_c0465.py -q -n 0` declares
  `rule("GND_JOIN", "short", where=select.net("AGND"), between=select.net("DGND"), severity="ignore")` and
  `rule("SIG_STUB", "antenna", where=select.net("SIG"), max=mm(1.5))`
- **THEN** the built rule set holds both rules, and `rule("X", "short", where=select.ALL, between=select.ALL,
  min=mm(0.1))` raises `DslError`
