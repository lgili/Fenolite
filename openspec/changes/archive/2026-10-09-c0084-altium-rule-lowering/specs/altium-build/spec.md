## ADDED Requirements

### Requirement: Rules in an Altium build
`fenolite build --target altium` SHALL write every rule of the design that `rulemap.lower` lowers into `<name>.PcbDoc`, and SHALL report each rule that is not written with one `altium.not-lowered` (warning) whose `where` is `design-rules/<kind>` and whose message holds the rule's name, its selector and the reason.
- `result.rules` MUST hold `written` and `not_lowered`, each a list of `{kind, selector}`; an entry of `written` also holds `rule`, the name of the Altium rule, and an entry of `not_lowered` holds `reason`. `result.rules` is `null` only when the build is refused before the PCB document is planned.
- The reasons are those of `rulemap.NOT_LOWERED_REASONS` and, when the build plans no PCB document, `no-document` for every rule that would otherwise be written.
- No issue with `where` `design-rules` alone MAY be reported.
- A design without rules MUST get the rules the build wrote before this change (the rules of the net classes and the `All` defaults), byte for byte.
- The build's evidence MUST name the hypotheses of `rulemap.EVIDENCE` whenever it names those of the PCB writer.
- A script whose copper intents are resolved through the KiCad build in memory ("Script copper in an Altium build") is still judged by that build: a rule that the KiCad lowering refuses (for example a `via_drill` rule with `opt`) refuses the Altium build as before.

#### Scenario: Edge clearance reaches the board
- **GIVEN** the blink script with `design.rules.minimum(edge_clearance=mm(0.5))`
- **WHEN** it is built for Altium and the PCB document is read back
- **THEN** the board's rules hold that edge clearance, and `result.rules.written` lists the kind `edge_clearance` with the rule `BoardOutlineClearance`

#### Scenario: A kind without a counterpart
- **GIVEN** the same script with a `silk_clearance` rule and a `creepage` rule
- **WHEN** it is built
- **THEN** one `altium.not-lowered` warning per rule has `where` `design-rules/silk_clearance` and `design-rules/creepage`, and `result.rules.not_lowered` holds both with the reason `no-counterpart`

#### Scenario: Read back equal
- **WHEN** `uv run pytest tests/unit/lens/test_altium_rules.py -k readback` builds the blink with one rule of every `exact` kind, the example scripts and generated rule sets, and maps the rule records of each PCB document with `read.rules.map_rules`
- **THEN** every record maps, and the rules read under the names of `result.rules.written` equal the lowered rules of the design within 2 nm (`H-A-RULE-READBACK`)

## MODIFIED Requirements

### Requirement: Rule minimums in an Altium build
The Altium build SHALL write the rules of `design.rules` into the PCB document where Altium has an exact rule for them ("Rules in an Altium build"), and it SHALL report the others instead of dropping them silently.
- For each rule of `design.rules` that is not written, `lens.altium.build_altium` MUST add exactly one `altium.not-lowered` warning with `where` = `design-rules/<kind>`, whose message names the rule by `Rule.name` with its selector and the reason. A `clearance` or `edge_clearance` minimum is written; a `track_width`, `via_diameter`, `via_drill` or `hole_size` minimum gives `value-unsupported`, because Altium's record also holds a maximum (and a preferred value).
- The warnings MUST be given with and without a planned PCB document: the filter that removes the `board`, `placements` and `rules` kinds when the document is written ("Copper in an Altium build") MUST NOT remove them. Without a document every rule is reported, with the reason `no-document` where the rule would have been written.
- Every written file except `.fenolite/rules.json`, which holds the rules, the PCB document, whose `Rules6` holds the written ones, and `.fenolite/build.json`, which lists the document's hash, MUST be byte-identical with and without them.
- A design without rules MUST give no such issue.

#### Scenario: Minimums are written or reported
- **GIVEN** a design with a class `PWR`, `design.rules.minimum(clearance=mm(0.15))` and `design.rules.minimum(track_width=mm(0.5), netclass="PWR")`
- **WHEN** `uv run pytest tests/unit/lens/test_build_minimums.py -k altium` builds it for Altium as the blink with its PCB document
- **THEN** the build has one `altium.not-lowered` warning, with `where == "design-rules/track_width"`, naming `min_track_width_PWR` and `value-unsupported`, and only `blink.PcbDoc`, `.fenolite/build.json` and `.fenolite/rules.json` differ from the same build without the two `minimum()` calls

#### Scenario: Minimums are reported, not written
- **GIVEN** the same design without a PCB document
- **WHEN** `uv run pytest tests/unit/lens/test_build_minimums.py -k altium` builds it for Altium
- **THEN** the build has the warning of `min_track_width_PWR` and one with `where == "design-rules/clearance"` naming `min_clearance` and `no-document`, no rule is written, and only `.fenolite/rules.json` differs from the same build without the two `minimum()` calls

#### Scenario: No rules, no report
- **GIVEN** the blink design as committed
- **WHEN** it is built with `--target altium`
- **THEN** no issue has a `where` that starts with `design-rules`
