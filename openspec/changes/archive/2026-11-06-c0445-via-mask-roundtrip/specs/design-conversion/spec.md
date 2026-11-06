## ADDED Requirements

### Requirement: Mask of imported vias
A design read from an Altium document SHALL be given, when it is converted to KiCad, `Board.mask_margin` from its untented vias (S-2041, S-2043):
- Each via that is untented on a side MUST give how far its mask opening extends beyond its copper. In the manual state (2 at offset 66 of its record) that is its own expansion. Otherwise it is the value of the governing via rule: the first enabled `SolderMaskExpansion` record, by priority, of scope `IsVia` or `All`. A record whose scope selects no via is left out. With `SOLDERMASKFROMHOLE=TRUE` the value is measured from the hole: `(drill − diameter) / 2 + expansion`. A via without a value gives none.
- The board MUST take the most frequent value, the smaller on a tie. Each via with another value MUST be counted `changed` under `via`. So MUST a via that takes the rule while an enabled record of another scope that may select vias comes first.
- With a margin other than 0, a pad that holds a mask layer and no margin of its own MUST get a margin of 0.
- Converted to Altium, the board's `pad_to_mask_clearance` (0 when absent) MUST become `Board.mask_margin` of the written model.

#### Scenario: A rule measured from the hole
- **GIVEN** 20 mil vias with a 10 mil hole in the rule state, under a rule of scope `IsVia` of 1 mil from the hole that comes before one of scope `All` of 3 mil
- **WHEN** `uv run pytest tests/unit/convert/test_via_mask_c0445.py` computes their margins
- **THEN** each via gives -4 mil, and a via in the manual state gives its own expansion

#### Scenario: The most frequent margin
- **GIVEN** two vias of -4 mil and one of 1 mil, and a board whose pads hold `F.Mask` with no margin, with 3 mil, and no mask layer
- **WHEN** the board is given its mask
- **THEN** its `mask_margin` is -4 mil, the ledger lists the third via `changed` under `via`, and the pads hold 0, 3 mil and no margin

#### Scenario: Row -01 back to Altium
- **GIVEN** the public row `altium-third-party-pcbdoc-01`, whose 646 vias are 20 mil with a 10 mil hole and take a rule of scope `IsVia` of 1 mil from the hole
- **WHEN** `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_via_mask_c0445.py` converts it to KiCad and back to Altium
- **THEN** the KiCad board holds `(pad_to_mask_clearance -0.1016)` and every via written back opens 12 mil, as in the source
