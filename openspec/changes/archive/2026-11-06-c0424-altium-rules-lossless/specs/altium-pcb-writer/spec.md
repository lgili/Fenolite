## ADDED Requirements

### Requirement: Kept rule records written back
The PCB document of a board that was read SHALL hold its kept rule records again.
- `pcbdoc.rule_records` MUST write each `kept_rule` record after the records it writes itself, with the record's kind number and keys.
- A kept record of a kind that the document already writes MUST take the next priorities of that kind, in its original priority order. Otherwise it MUST keep its own priority.
- A kept record whose name is already written MUST get the suffix `_kept`.
- A kept Plane Connect or Plane Clearance record MUST replace the default plane rule of its kind.

#### Scenario: Kept records survive a write
- **GIVEN** the imported document of "Rule records the writer cannot rebuild are kept"
- **WHEN** `uv run pytest tests/unit/backends/altium/test_kept_rules.py -k written` writes it and reads the written document back
- **THEN** the read-back holds the disabled width with `ENABLED=FALSE` and the Routing Topology record with its keys
