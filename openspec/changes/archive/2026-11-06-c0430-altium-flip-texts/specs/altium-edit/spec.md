## ADDED Requirements

### Requirement: A flip moves every layer field of a primitive
A `flip` (and every other operation that moves a primitive to another layer) MUST change a primitive's
layer byte together with every other field that names its layer: a region's or body's `V7_LAYER`, and the
long layer id of a saved long track, arc, fill, text or pad. A flipped component's designator and comment
MUST end on the overlay of the new side with the mirror flag of that side.

#### Scenario: A saved part flipped to the bottom and back
- **GIVEN** the kit board with its texts in the saved 252-byte form and its pads in the saved 194-byte form,
  each holding the long layer id of its layer
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_flip_texts.py -k flip_to_the_bottom` flips `D1` and
  `R1` to the bottom and then back to the top
- **THEN** after the first flip both components read `BOTTOM`, their designators and comments read Bottom
  Overlay with the long id `0x01030007` and the mirror flag set, and `R1`'s pads read Bottom Layer with the
  long id `0x0100FFFF`; after the second flip every text and pad record of both equals the board's

### Requirement: A flip swaps only the mechanical pairs the board declares
A `flip` MUST move a component's primitive on a mechanical layer only when the board record declares that
layer in a pair (`MECHPAIR<i>L1`, `MECHPAIR<i>L2`), and then MUST put it on the other layer of the pair
by layer byte and long layer id. A primitive on a mechanical layer of no declared pair MUST keep its
layer.

#### Scenario: No pair declared
- **GIVEN** the kit board, which declares no mechanical pair
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_flip_texts.py -k no_declared_pair` flips `D1`
- **THEN** `D1`'s Mechanical 15 drawings keep their layer and its overlay drawings read Bottom Overlay

#### Scenario: Pairs declared, one above Mechanical 16
- **GIVEN** the kit board with Mechanical 13 paired with 14 and 15 with 19, its drawings in the saved long forms
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_flip_texts.py -k declared_mechanical_pairs` flips `D1` and back
- **THEN** the Mechanical 15 drawings hold the layer byte 72 and the long id `0x01020013`, the Mechanical 13
  ones Mechanical 14, and the flip back restores every layer field
