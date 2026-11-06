## ADDED Requirements

### Requirement: Short and antenna rules
`fenolite.model.rules.RuleKind` SHALL hold `short` and `antenna` (change c0465), added as a minor version of
the model approved by `tools/model_review.py`.
- A `short` rule MUST be binary: `selector_b` MUST be set, and it MUST hold no limit. Its `severity` is the
  severity of a short between an item of side A and an item of side B, in either order: `ignore` allows it.
- An `antenna` rule MUST be unary and MUST hold `max` ≥ 0 and no other limit. A stub of the selected copper
  passes when its length is at most `max`; a longer stub is reported at the rule's severity.
- Constructing a rule of either kind that breaks these limits MUST raise `ValueError`.
- `rulemap.KIND_SELECTORS` and `rulemap.KIND_SUPPORT` MUST hold both kinds. `KIND_SUPPORT` holds no major for
  `antenna`, and holds 10 for `short` only when probe `dru-short-allow` records `present` in `10.0.6.json`.
- A rule set without these kinds MUST write the bytes it wrote before, and
  `schemas/fenolite.model.v1/rules.json` MUST be regenerated. The kinds ride c0462's model version 1.1, with
  the coordinator's approval of the widened `RuleKind` in `model0-approved.json`.

#### Scenario: A short rule needs two sides and no limit
- **WHEN** `uv run pytest tests/unit/model/test_rule_allowances_c0465.py -q -n 0` builds a `short` rule without
  `selector_b`, one with `min`, and an `antenna` rule with `min`
- **THEN** each raises `ValueError`, and a `short` rule of nets `AGND` and `DGND` with severity `ignore` builds

### Requirement: Short and antenna rules lowered to KiCad
`lower_rules` and the project writer SHALL lower the two kinds as design D6 of change c0465 gives:
- a `short` rule of severity `error` and an `antenna` rule of `max` 0 MUST be written as nothing, with no
  issue: they are KiCad's default;
- a `short` rule of severity `ignore` or `warning` whose two sides are `all`, when the rule set holds no
  other `short` rule, MUST set `board.design_settings.rule_severities.shorting_items` to that severity;
- any other `short` rule of severity `ignore` or `warning` MUST be written for target 10 as a `clearance` rule
  with a negative `min` between its sides when `KIND_SUPPORT["short"]` holds 10, and MUST otherwise give
  `rules.kind-unchecked`;
- any other `antenna` rule MUST give `rules.kind-unchecked`;
- with `allow_lossy=True` a refused rule MUST be dropped with `rules.dropped-for-target`.

#### Scenario: A whole-board allowance and a net-pair one
- **GIVEN** rule set A holding one `short` rule `all`/`all` of severity `ignore`, and rule set B holding one
  `short` rule of nets `AGND` and `DGND` of severity `ignore`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_rule_allowances_c0465.py -q -n 0` lowers each for
  target 9
- **THEN** A writes `shorting_items: ignore` and no rule; B raises `RulesLossError` with one
  `rules.kind-unchecked`, and with `allow_lossy=True` gives `rules.dropped-for-target`
