## MODIFIED Requirements

### Requirement: Mask and paste of imported pads
A pad read from an Altium document SHALL be given mask and paste layers by its kind when it is converted to KiCad: a surface pad its side's paste and mask layers, a plated or unplated through-hole pad both mask layers and no paste.
- A manual expansion MUST become the pad's margin, an expansion of 0 included (change c0440: it MUST NOT be left to the board's setting); a rule expansion the margin of the first enabled rule of scope `All`.
- The modes and manual expansions MUST be read from each pad's Altium bag as the source holds it, before the conversion empties the bags of the target (change c0440).
- A pad that a rule of another scope may govern MUST be a `pad-margin` loss; a rule selecting no pad (`IsVia`) is left out.

#### Scenario: Openings after conversion
- **GIVEN** an imported design with a surface pad of manual mask expansion 2 mil, a plated through-hole pad and an unplated hole, all with the paste mode of a rule
- **WHEN** `uv run pytest tests/unit/convert/test_pad_layers.py` prepares it for KiCad
- **THEN** the surface pad holds `F.Cu`, `F.Paste` and `F.Mask` with a mask margin of 50 800 nm, the two holes hold both masks and no paste, and the written board loads in `kicad-cli`

#### Scenario: A scoped rule is reported
- **GIVEN** the same design whose document holds a `SolderMaskExpansion` rule of scope `All` and one of scope `IsPad` that comes first
- **WHEN** it is prepared
- **THEN** the rule-mode pads take the `All` rule's expansion and the ledger lists them under `pad-margin`

#### Scenario: A rule of vias is no pad's
- **GIVEN** the same design whose `SolderMaskExpansion` rule of scope `IsVia` comes before the one of scope `All`
- **WHEN** `uv run pytest tests/unit/convert/test_pad_layers.py -k no_pad` prepares it
- **THEN** the pads take the `All` rule's expansion and the ledger lists no `pad-margin` row

#### Scenario: A manual pad keeps its own expansion
- **GIVEN** `altium-third-party-pcbdoc-01`, whose pads hold a manual mask expansion of 0 (20 pads) or 3.1496 mil (16 pads) under a `SolderMaskExpansion` rule of 3 mil of scope `All`
- **WHEN** `uv run pytest tests/corpus/test_altium_pad_mask_c0440.py` converts it to KiCad and back to Altium
- **THEN** every pad common to both documents holds the mask it held, a pad that followed the rule holding the manual expansion of 3 mil, and level 3 of `equivalent` between the two documents gives no `pad-mask` difference
