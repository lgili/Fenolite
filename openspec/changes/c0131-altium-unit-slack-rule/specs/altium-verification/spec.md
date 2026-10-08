## MODIFIED Requirements

### Requirement: Clearance rules of a PCB document
`AltiumBackend` SHALL satisfy `DesignRulesSource` (`backend-protocol`): `design_rules(design, project)` gives the clearance in force for the import `design` of the PCB document `project.board`.
- `DesignRules.design` MUST be `design` with the clearance of every zone at 0, with every `clearance` rule lowered by `UNIT_SLACK_NM` (`docs/formats/altium/import.md`, "Clearance of the copper check"), and without the tracks and arcs that have no net and lie on the layer of an internal plane.
- **The slack is one file unit per item of the pair.** `FILE_UNIT_NM` MUST be 127/50 nm (1/10 000 mil), `SLACK_UNITS_PER_ITEM` 1, `PAIR_SLACK_NM` = `2 * SLACK_UNITS_PER_ITEM * FILE_UNIT_NM` (5.08 nm), and `UNIT_SLACK_NM` MUST be `PAIR_SLACK_NM` in whole nanometres rounded DOWN (5): a rule holds whole nanometres, the check compares strictly, and a slack rounded up would pass a gap that the stated rule reports. Every pair has two items, so each rule is lowered once. A rule at or below `UNIT_SLACK_NM` MUST be kept as it is. The slack MUST NOT depend on the kind of the items, and no finding MUST be allowed for by another means.
- `opaque_clearance_rules` MUST count the `Clearance` records of `Rules6/Data` that `read.rules.map_rules`, called with the copper layers of `design` (`adapter.layers.copper_layers_of`), does not map; a record whose reason is in `read.rules.NOT_APPLYING` (`disabled`, `no-layer`) MUST NOT count. The count and the rules of `design` therefore come from one mapping of the same records. `min_clearance` MUST be `None`, `rules_over_classes` true and `floor_over_rules` false.
- `clearance_cells` MUST be the sums of `judged` and of `unjudged` over `RuleMapping.matrix_cells` of that mapping.
- `left_out` MUST hold one entry of kind `plane` with the number of internal plane layers when the board has any, and be empty otherwise.
- A document that cannot be read MUST be named in `unread` and MUST NOT raise.

#### Scenario: Rules of a built sample
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k rules_source` asks for the rules of `routed.PcbDoc`
- **THEN** both zones have the clearance 0, the two clearance rules are 199 995 nm, no rule is opaque, and a missing document is named in `unread`

#### Scenario: A record that applies to nothing is no unread rule
- **GIVEN** the import of a document whose `Rules6` holds the three records of "A clearance matrix on a two-layer board" (`altium-project-reader`)
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_rules.py -k counts_what_stays_unread` asks for the rules of the document
- **THEN** on two copper layers `opaque_clearance_rules` is 0 and the design holds both clearance rules; on four copper layers it is 2

#### Scenario: Cells are counted
- **GIVEN** the import of a document with one record that maps with a via-to-via cell and an entry for a hole, and one record whose matrix tells a through-hole pad from a surface pad
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_rules.py tests/unit/checks/test_document_copper.py -k "counts_the_cells or cells_of_the_clearance"` asks for the rules and runs the stage
- **THEN** `clearance_cells == (1, 2)`, one rule is opaque, and the stage's summary holds `clearance_cells` as `{judged, unjudged}`

#### Scenario: At the bound, on records
- **GIVEN** a document of authored records with a `Clearance` of 10 mil and two parallel tracks of two nets whose edges are 10 mil apart, 10 mil less 2 file units, or 10 mil less 3 file units
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_rules.py -k one_file_unit` imports each and runs the copper check with the rules of the document
- **THEN** the gaps are 254 000, 253 995 and 253 992 nm, and only the third is a `copper.clearance`, against 253 995 nm

#### Scenario: One nanometre inside the bound
- **GIVEN** the import of the second document with one track moved by 1 nm towards the other in the model
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_rules.py -k one_nanometre` runs the copper check
- **THEN** the gap of 253 994 nm is one `copper.clearance`, and without the move there is none

#### Scenario: KiCad boards are judged strictly
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k strict_comparison` judges a KiCad-side board at exactly its clearance and 1 nm inside
- **THEN** the first has no finding and the second has one, with the gap 199 999 nm against 200 000 nm: no slack applies outside the Altium rules source
