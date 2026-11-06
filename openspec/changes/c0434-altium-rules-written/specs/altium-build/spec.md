## MODIFIED Requirements

### Requirement: Rule minimums in an Altium build
The Altium build SHALL write the rules of `design.rules` into the PCB document where Altium has an exact rule for them ("Rules in an Altium build"), and it SHALL report the others instead of dropping them silently.
- For each rule of `design.rules` that is not written, `lens.altium.build_altium` MUST add exactly one `altium.not-lowered` warning with `where` = `design-rules/<kind>`, whose message names the rule by `Rule.name` with its selector and the reason. A `clearance` or `edge_clearance` minimum is written; since change c0434 a `track_width` or `hole_size` minimum is written too, with the limits it does not give written open ("Rule lowering table" of `altium-pcb-writer`), and `result.rules.changed` lists it with its kind, selector and a detail that names the open limits.
- The warnings MUST be given with and without a planned PCB document: the filter that removes the `board`, `placements` and `rules` kinds when the document is written ("Copper in an Altium build") MUST NOT remove them. Without a document every rule is reported, with the reason `no-document` where the rule would have been written.
- Every written file except `.fenolite/rules.json`, which holds the rules, the PCB document, whose `Rules6` holds the written ones, and `.fenolite/build.json`, which lists the document's hash, MUST be byte-identical with and without them.
- A design without rules MUST give no such issue.

#### Scenario: Minimums are written or reported
- **GIVEN** a design with a class `PWR`, `design.rules.minimum(clearance=mm(0.15))` and `design.rules.minimum(track_width=mm(0.5), netclass="PWR")`
- **WHEN** `uv run pytest tests/unit/lens/test_build_minimums.py -k altium` builds it for Altium as the blink with its PCB document
- **THEN** the build has no `altium.not-lowered` warning at `design-rules/…`, both minimums are written, and only `blink.PcbDoc`, `.fenolite/build.json` and `.fenolite/rules.json` differ from the same build without the two `minimum()` calls

#### Scenario: Minimums are reported, not written
- **GIVEN** the same design without a PCB document
- **WHEN** `uv run pytest tests/unit/lens/test_build_minimums.py -k altium` builds it for Altium
- **THEN** the build has one warning with `where == "design-rules/clearance"` naming `min_clearance` and one with `where == "design-rules/track_width"` naming `min_track_width_PWR`, both `no-document`, no rule is written, and only `.fenolite/rules.json` differs from the same build without the two `minimum()` calls

#### Scenario: No rules, no report
- **GIVEN** the blink design as committed
- **WHEN** it is built with `--target altium`
- **THEN** no issue has a `where` that starts with `design-rules`
