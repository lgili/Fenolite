## ADDED Requirements

### Requirement: Selector of items without a net
`fenolite.dsl.select.no_net()` SHALL select the items that have no net; KiCad SHALL lower it to `A.NetName == ''` (change c0409, B7).

#### Scenario: A rule for netless items
- **WHEN** `uv run pytest tests/unit/dsl/test_select_no_net.py -q` lowers a clearance rule `where=select.no_net()`
- **THEN** the selector is `not(net "*")` of the frozen model ops, matches a track without a net and not one with a net, is written as the condition `A.NetName == ''` for targets 9 and 10, and is read back from it

#### Scenario: The condition on KiCad
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_conditions.py -k no_net -q` checks a 5 mm clearance rule with the condition on 9.0.9 and 10.0.6
- **THEN** a netless track 4 mm from a track of a net is flagged and two tracks of nets as far apart are not
