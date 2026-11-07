## MODIFIED Requirements

### Requirement: Mask and paste of imported pads
A pad read from an Altium document SHALL be given mask and paste layers by its kind when it is converted to KiCad: a surface pad its side's paste and mask layers, a plated or unplated through-hole pad both mask layers and no paste.
- A manual expansion MUST become the pad's margin, an expansion of 0 included (change c0440: it MUST NOT be left to the board's setting); a rule expansion the margin of the record that governs the pad (change c0462, design D6): the first enabled record of its kind, by priority, whose scope, read with the full grammar and the document, selects the pad. The pad's subject is its net, every net class of the document that holds the net, its component's designator, its one copper layer (a surface pad only), its hole and its pad type. A pad that no record selects gets none.
- The modes and manual expansions MUST be read from each pad's Altium bag as the source holds it, before the conversion empties the bags of the target (change c0440).
- A pad before whose governing record comes a record that may select it and that the conversion cannot judge for it (a scope outside the grammar, a room, or a layer of a pad with a hole when the rest of the scope does not decide it) MUST be a `pad-margin` loss, and MUST take the governing record's expansion. A record whose scope selects no pad (`IsVia`) is not such a record.

#### Scenario: Openings after conversion
- **GIVEN** an imported design with a surface pad of manual mask expansion 2 mil, a plated through-hole pad and an unplated hole, all with the paste mode of a rule
- **WHEN** `uv run pytest tests/unit/convert/test_pad_layers.py` prepares it for KiCad
- **THEN** the surface pad holds `F.Cu`, `F.Paste` and `F.Mask` with a mask margin of 50 800 nm, the two holes hold both masks and no paste, and the written board loads in `kicad-cli`

#### Scenario: A scoped rule governs the pads it selects
- **GIVEN** records of scope `InNetClass('Ground')` (1 mil), `InComponent('R1')` (2 mil) and `All` (4 mil), in that order, a net `GND` in the classes `Power` and `Ground`, and a paste record of scope `InNet('VCC') and OnLayer('Layer 1')`
- **WHEN** `uv run pytest tests/unit/convert/test_expansion_scopes_c0462.py` reads the pads of the document
- **THEN** the pad of `U1` on `GND` takes 1 mil, the pad of `U1` on `VCC` 4 mil and paste -1 mil, the through-hole pad of `R1` 2 mil, and no pad is listed under `pad-margin`

#### Scenario: A record that cannot be judged is reported
- **GIVEN** a record whose scope is outside the grammar before the record of scope `All`
- **WHEN** a rule-mode pad is opened
- **THEN** it takes the `All` record's expansion and the ledger lists it under `pad-margin`

#### Scenario: A rule of vias is no pad's
- **GIVEN** the same design whose `SolderMaskExpansion` rule of scope `IsVia` comes before the one of scope `All`
- **WHEN** `uv run pytest tests/unit/convert/test_pad_layers.py -k no_pad` prepares it
- **THEN** the pads take the `All` rule's expansion and the ledger lists no `pad-margin` row

#### Scenario: A manual pad keeps its own expansion
- **GIVEN** `altium-third-party-pcbdoc-01`, whose pads hold a manual mask expansion of 0 (20 pads) or 3.1496 mil (16 pads) under a `SolderMaskExpansion` rule of 3 mil of scope `All`
- **WHEN** `uv run pytest tests/corpus/test_altium_pad_mask_c0440.py` converts it to KiCad and back to Altium
- **THEN** every pad common to both documents holds the mask it held, a pad that followed the rule holding the manual expansion of 3 mil, and level 3 of `equivalent` between the two documents gives no `pad-mask` difference

### Requirement: Mask of imported vias
A design read from an Altium document SHALL be given, when it is converted to KiCad, `Board.mask_margin` from its untented vias (S-2041, S-2043):
- Each via that is untented on a side MUST give how far its mask opening extends beyond its copper. In the manual state (2 at offset 66 of its record) that is its own expansion. Otherwise it is the value of the record that governs the via (change c0462, design D6): the first enabled `SolderMaskExpansion` record, by priority, whose scope, read with the full grammar and the document, selects the via (its net, the net classes that hold it, its hole). With `SOLDERMASKFROMHOLE=TRUE` the value is measured from the hole: `(drill − diameter) / 2 + expansion`. A via without a value gives none.
- The board MUST take the most frequent value, the smaller on a tie. Each via with another value MUST be counted `changed` under `via`. So MUST a via that takes the rule while an enabled record that the conversion cannot judge for it comes first.
- With a margin other than 0, a pad that holds a mask layer and no margin of its own MUST get a margin of 0.
- Converted to Altium, the board's `pad_to_mask_clearance` (0 when absent) MUST become `Board.mask_margin` of the written model.

#### Scenario: A via record of one net
- **GIVEN** records of scope `InNet('GND')` (2 mil), `IsVia` (1 mil from the hole) and `All` (4 mil), in that order
- **WHEN** `uv run pytest tests/unit/convert/test_expansion_scopes_c0462.py -k via` reads them
- **THEN** a via on `GND` takes 2 mil, a via on another net 1 mil from the hole, and a pad on another net 4 mil

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
