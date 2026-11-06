# c0445: keep the mask opening of vias through a conversion

## Why

Flow B (an Altium PCB document converted to KiCad and back to Altium) opens the solder mask of every via
wider than the source did. On the public row `altium-third-party-pcbdoc-01`, Altium 24.5 counted 1655
Minimum Solder Mask Sliver violations where the source has 103, and 726 of them lie between two vias (S-2040,
reported by the session `altium-rounds-2`). The causes, measured with Fenolite's own reader (S-2041, S-2043):

- The source's vias are untented. They take their mask from a `SolderMaskExpansion` rule of scope
  `IsVia`: 1 mil, measured from the hole (`SOLDERMASKFROMHOLE=TRUE`). Each opening is the 10 mil hole plus
  2 mil, 12 mil across, smaller than the 20 mil via.
- The conversion to KiCad reads no via mask: `openings.rule_expansion` leaves an `IsVia` rule out, and a
  KiCad via holds no mask value. KiCad opens an untented via by the board's `pad_to_mask_clearance`
  (S-2042, KiCad 10.0.6), and the writer writes 0 there. So KiCad opens each via 20 mil across.
- The Altium writer writes every via with a mask expansion of 4 mil from the copper, in the mode "from the
  rules", and writes no mask rule. So Altium opens each via 28 mil across.

A `solder_mask_expansion` rule in a KiCad 10 rules file does not change a via's opening (S-2042). The
board's `pad_to_mask_clearance` is the only value KiCad holds for it.

## What Changes

- **Model.** `Board.mask_margin` is the board's mask margin: how far the mask opening of an untented via,
  and of a pad without its own margin, extends beyond the copper. It may be negative. `None` means the
  backend's default. The KiCad writer writes it as `(setup (pad_to_mask_clearance …))`.
- **Conversion to KiCad.** The mask of the untented vias becomes the board's mask margin. Each via's growth
  beyond its copper is computed from its own manual value or from the governing via rule. That rule is the
  first enabled `SolderMaskExpansion` record that selects vias, of scope `IsVia` or `All`. When the rule
  says so, the value is measured from the hole: `(hole − diameter) / 2 + expansion`.
  - The board takes the most frequent value (the smaller one on a tie). Each via with another value is
    counted `changed` under `via`.
  - A via that takes the rule while a rule of another scope comes first is counted `changed` too.
  - With a margin other than 0, a pad that holds a mask layer and no margin of its own gets a margin of 0.
    Its opening then stays as it was.
- **Conversion to Altium.** The board's `pad_to_mask_clearance` becomes `Board.mask_margin` of the written
  model.
- **Altium writer.** A write of a model with `Board.mask_margin` writes that expansion for every via at
  offsets 54 and 242, in the manual mask mode (state 2 at 66), so its opening is the one KiCad plots. A
  build, and a model without the field, write as before (4 mil, rule mode).

## Capabilities

- `design-model`: "Board mask margin in the model", added.
- `kicad-file-backend`: "Board mask margin in a written board", added.
- `design-conversion`: "Mask of imported vias", added. "Mask and paste of imported pads" is left to change
  c0440, which modifies it.
- `altium-pcb-writer`: "Via records", modified.

## Out of scope

- The tenting options of a mask rule (`ISTENTINGTOP`, `ISTENTINGBOTTOM`). Rows -02 and -06 set them false
  and tent their vias with the via flags, which the conversion keeps (c0112).
- A per-via-size mask in KiCad. KiCad holds one value for the board.
- The KiCad reader's projection of `pad_to_mask_clearance` into the field. The conversion to Altium reads
  the board text instead.
- An Altium run. The session that runs Altium is to confirm the sliver count; the opening of the written
  via stays `INFERRED` until then.
