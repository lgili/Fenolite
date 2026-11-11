## ADDED Requirements

### Requirement: Inner layers of a converted four-layer board
The Altium writer SHALL hold every inner copper layer of the board in the layer stack of the document that
`fenolite convert --to altium` and `fenolite build --target altium` write, and a through-hole pad on every
copper layer SHALL read back on every copper layer of the written document (change c0488).
- The stack of the written document MUST hold one Altium layer per copper layer of the model, in order, as
  "Layer stacks of any even count" gives it. The stack falls back to the two outer layers only for a stack
  that rule excludes, and then with its `altium.not-lowered` row.
- A pad on every copper layer MUST be written on Multi-Layer, and the reader MUST give it the copper layers
  of the written stack.
- The conversion's own verification MUST give no `convert.unexplained` for such a pad.

#### Scenario: Four-layer board through convert
- **GIVEN** an authored KiCad board with copper layers `F.Cu, In1.Cu, In2.Cu, B.Cu` and two through-hole
  pads on `*.Cu`, once with both inner layers as signal layers and once with `In1.Cu` as a `GND` plane
- **WHEN** `fenolite convert --to altium` writes it and the document is read back
- **THEN** the board has the copper layers `F.Cu, In1.Cu, In2.Cu, B.Cu`, each pad has those four layers,
  and the command reports no `convert.unexplained`

#### Scenario: Four-layer board through build
- **GIVEN** an authored design script with four copper layers and one through-hole connector
- **WHEN** `fenolite build --target altium` writes it and the document is read back
- **THEN** the stack holds `Mid-Layer 1` and `Mid-Layer 2` (or their planes), and no `convert.unexplained`
  is reported
