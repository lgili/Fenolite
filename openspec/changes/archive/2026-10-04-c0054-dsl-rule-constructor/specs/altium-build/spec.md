## ADDED Requirements

### Requirement: Rule minimums in an Altium build
The Altium build SHALL NOT write the rules of `design.rules` into any file, and it SHALL report them instead of dropping them silently.
- When `design.rules` holds at least one rule, `lens.altium.build_altium` MUST add exactly one `altium.not-lowered` info with `where` = `design-rules`, whose message names every rule by `Rule.name` in name order and says that the rules of the PCB document come from the net classes.
- The info MUST be given with and without a planned PCB document: the filter that removes the `board`, `placements` and `rules` kinds when the document is written ("Copper in an Altium build") MUST NOT remove it.
- Every written file except `.fenolite/rules.json`, which holds the rules, MUST be byte-identical with and without them: the `Rules6` records of the PCB document keep coming from the net classes and the `All` defaults (`altium-pcb-writer`).
- A design without rules MUST give no such info.

#### Scenario: Minimums are reported, not written
- **GIVEN** a design with a class `PWR`, `design.rules.minimum(clearance=mm(0.15))` and `design.rules.minimum(track_width=mm(0.5), netclass="PWR")`
- **WHEN** `uv run pytest tests/unit/lens/test_build_minimums.py -k altium` builds it for Altium, once as the blink with its PCB document and once as a design without one
- **THEN** each build has one `altium.not-lowered` info with `where == "design-rules"` naming `min_clearance` and `min_track_width_PWR`, and every written file except `.fenolite/rules.json` equals the file of the same build without the two `minimum()` calls

#### Scenario: No rules, no report
- **GIVEN** the blink design as committed
- **WHEN** it is built with `--target altium`
- **THEN** no issue has `where == "design-rules"`
