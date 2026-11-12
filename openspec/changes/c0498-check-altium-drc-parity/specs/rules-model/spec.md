## ADDED Requirements

### Requirement: Silkscreen to mask and to edge rule kinds
`RuleKind` SHALL hold `silk_mask_clearance` and `silk_edge_clearance`. Both are unary and take `min`
(change c0498). `silk_mask_clearance` is the least distance from silkscreen to a solder-mask opening.
`silk_edge_clearance` is the least distance from silkscreen to the board's edge rings.
- The Altium rule table MUST map `SilkToSolderMaskClearance` to `silk_mask_clearance` and
  `SilkToBoardRegionClearance` to `silk_edge_clearance`, with the keys `rule-file.md` records. Neither MUST
  stay a carried-only kind.
- The KiCad backend MUST NOT lower either kind. A conversion to KiCad MUST report them as carried, with the
  reason it gives today.
- Adding the kinds MUST raise the model's minor version.

#### Scenario: A rule file with both kinds
- **GIVEN** an authored PCB document whose rules hold one `SilkToSolderMaskClearance` of 0.1 mm and one
  `SilkToBoardRegionClearance` of 0.2 mm
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k silk` imports it
- **THEN** the design holds one `silk_mask_clearance` rule with `min` 100 000 and one `silk_edge_clearance`
  rule with `min` 200 000, and the import reports neither as unmapped
