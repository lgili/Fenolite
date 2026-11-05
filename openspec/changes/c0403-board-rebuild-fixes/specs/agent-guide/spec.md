## ADDED Requirements

### Requirement: Scoped insulation exceptions in the guide
The guide page `board-insulation` SHALL say that a class minimum governs the rules of its class, that a part-wide pad rule is a minimum for every pad pair of the part, how to write one exception per pair of domains inside one part, and that a no-connect pin's net is in `Default` and is reached by its part, not by a class (change c0403, F2, F3, F4).

#### Scenario: The page's scopes resolve as written
- **WHEN** `uv run pytest tests/unit/checks/test_insulation_rule_scopes.py` resolves the page's selectors on an authored design
- **THEN** the part-wide rule holds between two logic pins of the part, the per-domain rule leaves them at their class value and holds between the domains, and a no-connect pad in `Default` is reached by the part-wide rule only
