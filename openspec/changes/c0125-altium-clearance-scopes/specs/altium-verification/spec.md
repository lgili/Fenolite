## MODIFIED Requirements

### Requirement: Copper check on Altium boards
On document input that holds a PCB document, the stage `copper.clearance` SHALL run `checks.copper.copper_stage` on the PCB reading with the rules that the backend gives for that document (`DesignRulesSource`) and its pads (`BoardFrame`), built and native input alike, through `checks.documents.document_copper`. The copper check judges shorts, clearance and zone-outline overlaps; it judges no board-edge clearance on any backend.
- The stage MUST be skipped with `single-source` when the documents hold no PCB document, and with `read-refused` when it could not be read.
- The findings MUST use the codes and severities of "Copper stage issue codes" of `verification-loop`, unchanged, and `summary` MUST hold the keys of that stage and two more counts, `unpoured` and `zones_unjudged`.
- **Rules.** `Clearance` records of the document that the rule table does not map and that apply to something (a reason outside `read.rules.NOT_APPLYING`: not disabled, and not scoped to a kind of layer the board lacks) MUST be counted in `summary.rules.opaque_clearance_rules` and MUST give `copper.rules-incomplete` (warning). Rule kinds that the copper check does not read (every kind but `Clearance`) MUST NOT give an issue of this stage: the import reports them.
- **Polygons.** A polygon with poured regions MUST be checked as a filled zone. A zone without a fill MUST be counted in `summary.unpoured`; when the count is not zero the stage MUST add one `copper.item-unsupported` (warning) with the count.
- **No invented clearance.** A polygon holds no clearance of its own, so the model's default zone clearance MUST NOT be judged. A filled zone for which no clearance is in force whatever the other item is (no rule, class or board minimum applies to copper of its net on a layer of its fills) MUST be counted in `summary.zones_unjudged`; when the count is not zero the stage MUST add one `copper.rules-incomplete` (warning, `where` = `zone`) with the count. Such a zone is still judged for shorts.
- **Planes.** What the rules source left out (`DesignRules.left_out`) MUST give one `copper.item-unsupported` (warning) per kind, `where` = the kind.
- The stage's evidence MUST be `UNVERIFIED` when it reports `copper.rules-incomplete` or `copper.item-unsupported`.

#### Scenario: A short on an Altium board
- **GIVEN** the routed blink whose script holds one more track of `LED_A` that crosses the track of `LED_DRV` on `F.Cu`, built for Altium with `--copper-check warn`
- **WHEN** `fenolite check <dir> --stages copper.clearance --json` runs
- **THEN** the exit code is 5 and one `copper.short` names the two nets

#### Scenario: Unpoured polygons are said
- **WHEN** `fenolite check tests/data/altium/routed --stages copper.clearance --json` runs (a built board with two unpoured polygons and no other fault)
- **THEN** the exit code is 0, it reports one `copper.item-unsupported` with the count 2, `summary.unpoured` is 2, and its evidence level is `UNVERIFIED`

#### Scenario: A pour without a clearance rule
- **GIVEN** a board model with one filled zone, no clearance rule, and a track of another net 0.3 mm from the fill
- **WHEN** `uv run pytest tests/unit/checks/test_document_copper.py -k default` runs the stage
- **THEN** it reports no `copper.clearance`, one `copper.rules-incomplete` that counts 1 zone, `summary.zones_unjudged` is 1, and the level is `UNVERIFIED`

#### Scenario: Same board, two backends
- **WHEN** `uv run pytest tests/kicad/altium/test_copper_same.py` checks the routed blink built for KiCad and for Altium, as built and with a planted short, a planted clearance fault and both
- **THEN** the copper findings of the two readings are equal by kind, net pair and place within 2 nm

#### Scenario: Public documents
- **WHEN** `uv run pytest tests/corpus/test_altium_copper.py -k copper` runs the stage on every public PCB document
- **THEN** no finding has the source `zone`, a document without a mapped `Clearance` rule has no clearance finding, and every finding that the 5 nm slack removes is short by 5 nm at most

### Requirement: Clearance rules of a PCB document
`AltiumBackend` SHALL satisfy `DesignRulesSource` (`backend-protocol`): `design_rules(design, project)` gives the clearance in force for the import `design` of the PCB document `project.board`.
- `DesignRules.design` MUST be `design` with the clearance of every zone at 0, with every `clearance` rule lowered by `UNIT_SLACK_NM` = 5 nm (`docs/formats/altium/import.md`, "Clearance of the copper check"), and without the tracks and arcs that have no net and lie on the layer of an internal plane.
- `opaque_clearance_rules` MUST count the `Clearance` records of `Rules6/Data` that `read.rules.map_rules`, called with the copper layers of `design` (`adapter.layers.copper_layers_of`), does not map; a record whose reason is in `read.rules.NOT_APPLYING` (`disabled`, `no-layer`) MUST NOT count. The count and the rules of `design` therefore come from one mapping of the same records. `min_clearance` MUST be `None`, `rules_over_classes` true and `floor_over_rules` false.
- `left_out` MUST hold one entry of kind `plane` with the number of internal plane layers when the board has any, and be empty otherwise.
- A document that cannot be read MUST be named in `unread` and MUST NOT raise.

#### Scenario: Rules of a built sample
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k rules_source` asks for the rules of `routed.PcbDoc`
- **THEN** both zones have the clearance 0, the two clearance rules are 199 995 nm, no rule is opaque, and a missing document is named in `unread`

#### Scenario: A record that applies to nothing is no unread rule
- **GIVEN** the import of a document whose `Rules6` holds the three records of "A clearance matrix on a two-layer board" (`altium-project-reader`)
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_rules.py -k counts_what_stays_unread` asks for the rules of the document
- **THEN** on two copper layers `opaque_clearance_rules` is 0 and the design holds both clearance rules; on four copper layers it is 2
