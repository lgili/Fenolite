# c0440: keep each pad's solder-mask expansion through a conversion

## Why

A board taken from Altium to KiCad and back to Altium gave 248 Minimum Solder Mask Sliver violations in
Altium's design rule check, all between pads, against 0 on the source. The pads' mask expansions changed on
the way. The public document `altium-third-party-pcbdoc-01` shows the causes (S-1990, S-1991):

- The conversion to KiCad empties every bag of the source (`_clean`) before it opens the pads, so
  `openings.open_pad` never saw a pad's mode: every pad took the expansion of the rule of scope `All`, the
  pads with a manual expansion included. A manual 0 was also left to the board's setting.
- The Altium writer wrote every pad with the solder mode "from the rules" and paste mode 0, so a pad's own
  margin (`Pad.mask_margin`, `Pad.paste_margin`) was left out, without a report.
- `equivalent` compared no mask expansion, so neither defect showed in a comparison.

Paste and mask were not mixed up, and tented vias were not opened by these paths.

## What changes

- **Conversion to KiCad.** Each pad's `mask` and `paste` entries are read from the source pad before the bags
  are emptied; a manual expansion of 0 is a margin of 0.
- **Altium writer.** A pad with its own solder-mask margin is written with mode 2 (manual) and the margin;
  the same for paste. A pad without one keeps mode 1 (from the rules), and a connector pad modes 0.
- **Equivalence.** Level 3 gains the kind `pad-mask` (`equiv.pad-mask`): the pad's own margin, else its
  Altium manual value or mode none, else the side's mask rule of scope `All` (the API reads it from the
  kept rule records). A KiCad pad without a margin agrees with any value.

A pad that followed a rule comes back manual with the rule's value: a KiCad board holds no rule-or-manual
mode, and the board-level mask setting is not in the model. Keeping the mode itself is a follow-up.

## Capabilities

- `design-conversion`: "Mask and paste of imported pads", modified.
- `altium-pcb-writer`: "Footprint pad records", modified.
- `design-equivalence`: "Differences are located", modified (kind `pad-mask`).

## Out of scope

- The rule-or-manual mode across KiCad (a board-level mask margin in the model and a written
  `SolderMaskExpansion` rule).
- The pads the conversion drops for other reasons (31 of the 143 pads of `-02`, free pads).
- The paste `Enabled` and solder `Tented` options (U1, U2 of `pcb-library.md`).
- An Altium run: the sliver count is to be confirmed in Altium by the Altium session.

## Impact

`convert/openings.py`, `convert/altium_to_kicad.py`, `backends/altium/pcblib.py`,
`checks/equivalence/{model,norm,levels}.py`, `api/equivalence.py`, `convert/report.py`, `cli/data/explain.toml`;
schemas regenerated (v0 re-frozen, additive kind); docs `conversion.md`, `equivalence.md`,
`cli-contract.md`, `formats/altium/pcb-library.md`, `evidence/sources.md` (S-1990, S-1991).
