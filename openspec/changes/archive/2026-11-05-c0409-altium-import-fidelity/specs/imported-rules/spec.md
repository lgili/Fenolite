## ADDED Requirements

### Requirement: Imported rules keep the source's rank
The importer SHALL write custom rules in the source's order of precedence (change c0409, B4).
- A custom rule MUST become `design.rules.minimum()` only where the minimum keeps its rank: a board-wide rule that is the first of its kind with no other of priority 0, or a class rule that is the last of its kind with no other of priority 1.
- Any other one-sided rule MUST be `design.rules.rule()` with `where=` and no `between`, and its priority.
- A rule whose name Fenolite wrote (`fenolite_<p>_<name>`) MUST get the priority `p` when the numbers of all rules give the file's order within each kind; otherwise it MUST get the reader's priority.

#### Scenario: A class x All rule ranked below a pairwise rule
- **GIVEN** an authored design with a pairwise clearance `PWR` to `LED_A` of priority 1 and a one-sided clearance of class `PWR` of priority 2, built for Altium
- **WHEN** `uv run pytest tests/unit/importer/test_altium_rule_rank.py -q` imports it to Python and builds the code for KiCad
- **THEN** no `minimum()` names a class, the one-sided rule is `rule(where=select.netclass("PWR"), priority=2)`, the pairwise one has `priority=1`, and in the `.kicad_dru` the pairwise rule comes after the class rule

#### Scenario: Written numbers that disagree with the file order
- **WHEN** the rules' written numbers do not give their order in the file
- **THEN** the reader's priorities are kept

### Requirement: Rules scoped to items without a net
An Altium rule scope `InNet('No Net')` SHALL import as the selector of items without a net, `not(net "*")`, not as a net named "No Net" (change c0409, B7).

#### Scenario: A clearance between netless items and a class
- **GIVEN** an authored Altium clearance record `InNet('No Net')` x `All`, and a KiCad project built from a script with `design.rules.rule("netless", "clearance", where=select.no_net(), min=mm(0.3))`
- **WHEN** `uv run pytest tests/unit/importer/test_no_net_rule.py -q` maps the record and imports the project to Python
- **THEN** the record maps, with no unmapped record, to a rule on `not(net "*")` that the code writes as `select.no_net()`, and the imported code holds `where=select.no_net()` with nothing unexpressed about the rule
