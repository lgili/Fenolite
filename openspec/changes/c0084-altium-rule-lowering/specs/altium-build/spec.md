## ADDED Requirements

### Requirement: Rules in an Altium build
`fenolite build --target altium` SHALL write every rule of the design that `rulemap.lower` lowers into `<name>.PcbDoc`, and SHALL report each rule that is not written with one `altium.not-lowered` (warning) whose `where` is `design-rules/<kind>` and whose message holds the selector and the reason.
- `result.rules` MUST hold `written` and `not_lowered`, each a list of `{kind, selector}`, `not_lowered` also with `reason`.
- No issue with `where` `design-rules` alone MAY be reported.
- A design without rules MUST get the rules the build wrote before this change (the defaults of the net classes).

#### Scenario: Edge clearance reaches the board
- **GIVEN** the blink script with `rules.edge_clearance = 0.5 * mm`
- **WHEN** it is built for Altium and the PCB document is read back
- **THEN** the board's rules hold that edge clearance, and `result.rules.written` lists the kind `edge_clearance`

#### Scenario: A kind without a counterpart
- **GIVEN** the same script with a rule of a kind whose row is `no-counterpart`
- **WHEN** it is built
- **THEN** one `altium.not-lowered` has `where` `design-rules/<kind>`, and `result.rules.not_lowered` holds it with the reason
