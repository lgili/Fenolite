## ADDED Requirements

### Requirement: Zone, hole and pad-type selectors
`fenolite.model.rules.SelectorOp` SHALL hold the leaves `zone`, `hole` and `pad_type` (change c0462), added as a minor version of the model approved by `tools/model_review.py`.

- `zone` MUST hold a glob over a zone's name, compared with letter case.
- `hole` MUST hold `lo..hi` in nanometres, either side open, and MUST match a subject whose finished hole diameter lies in the closed interval.
- `pad_type` MUST be `smd`, `th` or `npth`.
- `RuleSubject` MUST gain `zone`, `hole` and `pad_type`, each `None` by default.
- A selector of the old ops MUST give the same result on every subject as before.
- `selector_rank` MUST rank each new leaf 1.
- `fenolite.dsl.select` MUST give `zone()`, `hole(lo=…, hi=…)` and `pad_type()`.

#### Scenario: A hole interval
- **GIVEN** `Selector("hole", "1000001..")`
- **WHEN** `uv run pytest tests/unit/model/test_selector_leaves_c0462.py -q -n 0` evaluates it on pads with holes of 1.0 mm and 1.2 mm and on a track
- **THEN** only the 1.2 mm pad matches
