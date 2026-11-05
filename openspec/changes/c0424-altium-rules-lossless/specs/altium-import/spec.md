## ADDED Requirements

### Requirement: Rule records the writer cannot rebuild are kept
`import_board` SHALL keep, on the board, every rule record that gives no rule which `rulemap.lower` writes again in its own form, so that an Altium write of the imported design writes the record back.
- A kept record MUST be a `kept_rule` pair of the board's `altium` bag. Its text MUST be the record's kind number, `|`, and its keys from `RULEKIND` on as `KEY=VALUE` joined by `|`. The pairs MUST be in record order.
- A record is kept when it gives no neutral rule (any reason, `disabled` included), when its kind is not a kind of `rulemap.KIND_ORDER`, or when it is a Hole To Hole Clearance with `ALLOWSTACKEDMICROVIAS=TRUE`.
- Polygon Connect Style records MUST NOT be kept twice: the board keeps them as `polygon_connect`.
- A rule mapped from a kept record MUST hold the pair `kept_record` with the value `1` in its bag. `rulemap.lower` MUST leave such a rule out without an issue.

#### Scenario: A disabled rule and a routing topology are kept
- **GIVEN** an authored PCB document whose rules hold an enabled clearance, a disabled width and a Routing Topology record
- **WHEN** `uv run pytest tests/unit/backends/altium/test_kept_rules.py` imports it
- **THEN** `design.rules` holds the clearance alone, and the board holds two `kept_rule` pairs, the width's then the topology's
