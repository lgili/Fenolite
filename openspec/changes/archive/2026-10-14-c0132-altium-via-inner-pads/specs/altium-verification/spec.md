## MODIFIED Requirements

### Requirement: Clearance rules of a PCB document
`AltiumBackend` SHALL satisfy `DesignRulesSource` (`backend-protocol`): `design_rules(design, project)` gives the clearance in force for the import `design` of the PCB document `project.board`.
- `DesignRules.design` MUST be `design` with the clearance of every zone at 0, with every `clearance` rule lowered by `UNIT_SLACK_NM` (`docs/formats/altium/import.md`, "Clearance of the copper check"). It MUST hold every track and every arc of `design`: the import makes no copper of an object on an internal plane (`altium-import`, "Objects on an internal plane"), so the rules source takes nothing out.
- **The slack is one file unit per item of the pair.** `FILE_UNIT_NM` MUST be 127/50 nm (1/10 000 mil), `SLACK_UNITS_PER_ITEM` 1, `PAIR_SLACK_NM` = `2 * SLACK_UNITS_PER_ITEM * FILE_UNIT_NM` (5.08 nm), and `UNIT_SLACK_NM` MUST be `PAIR_SLACK_NM` in whole nanometres rounded DOWN (5): a rule holds whole nanometres, the check compares strictly, and a slack rounded up would pass a gap that the stated rule reports. Every pair has two items, so each rule is lowered once. A rule at or below `UNIT_SLACK_NM` MUST be kept as it is. The slack MUST NOT depend on the kind of the items, and no finding MUST be allowed for by another means.
- **A via is judged with the copper it has on each layer (change c0132).** A via of `design` whose `altium` bag holds the pair `pad_removed` MUST be given in `DesignRules.design` as one via per run of consecutive copper layers of its span that are alike: a run of layers with a pad has the via's diameter, and a run of layers that the pair names has the via's DRILL as its diameter, the hole through which the via passes that layer. Every part MUST keep the via's id, provenance, net, position and drill, and MUST span exactly its run. A layer id of the pair that is no copper layer of the via's span MUST be ignored, and a pair that does not parse MUST leave the via as it is. A via without the pair MUST be the same object as in `design`. Nothing is taken out of the check: copper of another net inside the hole of such a via is a `copper.short`, and copper nearer to the hole than the clearance is a `copper.clearance`. `summary.items.via` of the stage therefore counts the parts.
- `opaque_clearance_rules` MUST count the `Clearance` records of `Rules6/Data` that `read.rules.map_rules`, called with the copper layers of `design` (`adapter.layers.copper_layers_of`), does not map; a record whose reason is in `read.rules.NOT_APPLYING` (`disabled`, `no-layer`) MUST NOT count. The count and the rules of `design` therefore come from one mapping of the same records. `min_clearance` MUST be `None`, `rules_over_classes` true and `floor_over_rules` false.
- `clearance_cells` MUST be the sums of `judged` and of `unjudged` over `RuleMapping.matrix_cells` of that mapping.
- `left_out` MUST hold one entry of kind `plane` with the number of internal plane layers when the board has any, and be empty otherwise. An internal plane layer is a copper layer whose `altium` bag holds a `layer_id` from 39 to 54. The entry's reason MUST hold the number of objects that the import left out on those layers, the sum of their `plane_cuts`.
- A document that cannot be read MUST be named in `unread` and MUST NOT raise.

#### Scenario: Rules of a built sample
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k rules_source` asks for the rules of `routed.PcbDoc`
- **THEN** both zones have the clearance 0, the two clearance rules are 199 995 nm, no rule is opaque, and a missing document is named in `unread`

#### Scenario: Planes of an imported board
- **GIVEN** an authored document whose chain is 1 → 39 → 32, with two free tracks without a net on layer 39 and one track on layer 1
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k plane` imports it and asks for its rules
- **THEN** `DesignRules.design` holds the one track of the import, `left_out` is one entry `plane` with the count 1 whose reason names 2 objects, and a board without a plane layer has an empty `left_out`

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

#### Scenario: A via without a pad on an inner layer
- **GIVEN** the import of a six-layer document with a through via of 16 mil with an 8 mil hole whose record names the layers 2, 4 and 5, and on the layer 2 a track of another net whose edge is 5 mil from the via's centre, with a `Clearance` of 0.5 mil
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k pad_removed` asks for the rules and runs the copper check
- **THEN** the design of the rules holds five vias with the id of the one: 16 mil on `F.Cu`, on `In2.Cu` and on `B.Cu`, 8 mil on `In1.Cu` and on `In3.Cu` to `In4.Cu`; the check has no finding; the same document without the bytes gives one `copper.short`; and with the track's edge 3 mil from the centre the document with the bytes gives one `copper.short` too
