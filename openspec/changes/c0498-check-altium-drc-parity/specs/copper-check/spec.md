## ADDED Requirements

### Requirement: Unjudged edge items are reported
The copper stage SHALL add one `copper.rules-incomplete` warning with `where` `edge` when the board has an
edge clearance in force (an `edge_clearance` rule or a board minimum) and the edge limit of an item is
unset. The warning SHALL give the number of such items and up to three of their `where` texts, and the
stage's evidence SHALL become `UNVERIFIED` (change c0498). The count in `summary.edge.unset_items` stays.

#### Scenario: An edge rule that selects nothing
- **GIVEN** an authored board whose one `edge_clearance` rule of 0.5 mm selects the net `HV`, with no board
  minimum, and a pour of `GND` 0.03 mm from a board cut-out
- **WHEN** `uv run pytest tests/unit/checks/test_copper_edges.py -k unset` runs the copper stage
- **THEN** it reports one `copper.rules-incomplete` with `where` `edge` that names the pour, and the
  evidence level is `UNVERIFIED`

### Requirement: Copper beside a board cut-out
Copper closer to a board cut-out than its edge clearance SHALL give `copper.edge-clearance` for a free board
cut-out and for a component's board cut-out alike. This holds whether the governing rule is one value,
a matrix or scoped to the copper's net (change c0498).

#### Scenario: A pour beside a slot
- **GIVEN** each authored board of change c0498 task 1.3: a pour 0.03 mm from a slot made as a free board
  cut-out, as a component's board cut-out, or as a free cut-out under a matrix rule or a rule of the pour's
  net, each with a 0.5 mm `BoardOutlineClearance`
- **WHEN** `uv run pytest tests/unit/checks/test_copper_cutouts_c0498.py -k slot` runs `fenolite check
  --stages copper.clearance` on each
- **THEN** each reports one `copper.edge-clearance` naming the pour, 0.03 mm and 0.5 mm

### Requirement: Clearance to keep-out objects
A `clearance` rule whose side selects `item_kind keepout` SHALL be judged between each copper item and each
keep-out area on a shared copper layer (change c0498).
- A gap below the rule MUST give `copper.keepout-clearance` (error) with the area's name, the gap, the
  rule's value and its name.
- An item that a keep-out forbids by overlap MUST keep its `copper.keepout` and MUST NOT get a
  `copper.keepout-clearance` for the same area.
- The Altium rules view MUST give this rule for a `Clearance` record whose one scope is only keep-out terms
  and whose other is `All`. It MUST use the same function the pour uses (`read.rules.keepout_clearance_rule`).
- A board cut-out term is no keep-out area: the edge clearance judges it.

#### Scenario: A pour beside a keep-out
- **GIVEN** an authored PCB document with a keep-out region on Top, a `Clearance` rule `IsKeepOut` against
  `All` of 0.3 mm, and a pour on Top 0.1 mm from the region
- **WHEN** `fenolite check <doc> --stages copper.clearance --json` runs
- **THEN** it reports one `copper.keepout-clearance` naming the pour, 0.1 mm and 0.3 mm, and no
  `copper.keepout`
