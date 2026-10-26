## ADDED Requirements

### Requirement: Copper locks in the DSL
`Design.track`, `Design.via` and `Design.stitch` SHALL take the keyword `locked: bool = False`, and the intents `TrackIntent`, `ViaIntent` and `StitchIntent` SHALL gain `locked: bool = False` as their last field, so that intents built without it compare equal to those of earlier scripts. A value that is not a `bool` MUST raise `DslError` naming the key. A locked intent asks that its copper be written locked (`manual-copper`, "Locked script copper"); script copper is never removed by `route --rip`, locked or not (`cli-contract`, "Route command"). `docs/dsl.md`, "Copper", MUST say both.

#### Scenario: A locked via is recorded
- **WHEN** a script calls `design.via("tie", 10, 5, net=gnd, locked=True)` and `uv run pytest tests/unit/dsl/test_copper_dsl.py -k locked` converts it
- **THEN** the intent `tie` is a `ViaIntent` with `locked == True`, and an intent recorded without `locked` has `locked == False`

#### Scenario: Not a bool
- **WHEN** a script calls `design.track("t", r1.pad(1), (5, 0), locked="yes")`
- **THEN** `DslError` is raised naming `t`
