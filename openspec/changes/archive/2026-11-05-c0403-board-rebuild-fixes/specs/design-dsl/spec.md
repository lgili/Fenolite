## ADDED Requirements

### Requirement: The precedence of class minimums is stated
The docstring of `design.rules.minimum()` SHALL say that a class minimum is written last and governs every `rule()` of its class without `priority=`, and that `design.rules.precedence("specificity")` lets the more specific rule govern (change c0403, F2).

#### Scenario: A lower rule between the nets of one class
- **GIVEN** `minimum(clearance=mm(3), netclass="MAINS")` and a two-sided `MAINS`/`MAINS` clearance rule of 1 mm without `priority=`
- **WHEN** `uv run pytest tests/unit/checks/test_specificity.py -k class_minimum` builds the model with and without `precedence("specificity")`
- **THEN** without it the class minimum governs and `rules.shadowed` names the custom rule; with it the custom rule governs and nothing is shadowed
