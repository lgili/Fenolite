# Design

## The field

The census of the eight public documents (S-1891) finds the 32-bit long layer id of the text's layer at
offset 226 of every text record of 232 or 252 bytes. The only exceptions are the texts on byte 72 (Mechanical 16) that
are on Mechanical 19, the same pattern as a long track on Mechanical 17 to 32. For pads, the value at 114 of
the fifth subrecord equals the long id of the layer byte on all 3 784 pads.

## The rule

`long_layer_offset` gains two rows. The rule stays as it was: a length at or above the shortest saved
form holds the id, the short form Fenolite writes holds none, and any other length is refused when strict.
`flip` relayers with `strict=False`, so a form no row records keeps its other bytes, as before.

## Proof against Altium's own flip

Fenolite's flip of `J01-resave.PcbDoc` and Altium's J9 save of the same part (S-1892) hold the same layer
byte (34), long id (`0x01030007`) and mirror flag for both texts. Each text also sits at the same offset
from the component origin, mirrored (−501 969 units). The PcbDocs for the VM agent's check are in
`~/fenolite-altium-checks/claude-2026-11-05/c0430-flip/`, outside the repository.

## Mechanical pairs

`flip_layers(state)` maps long layer ids. It takes `FLIP_PAIRS` without its mechanical rows, and adds both
directions of each pair that `mechanical_pairs(state)` reads from `MECHPAIR<i>L1` and `L2` (any case, i
from 0; a pair without its other half is none). `move_primitives` reads a primitive's layer by its long
id when its form holds one, else by its byte. `relayer_long` puts it on the target: the byte of Mechanical 17
to 32 is 72, with the long id and a region's or body's `V7_LAYER` of the layer itself. A short form cannot
name Mechanical 17 to 32, so it is refused when strict and left unchanged otherwise.

After the change, Fenolite's flip of `J01-resave.PcbDoc` matches Altium's J09 save on every layer of `D1`:
overlay texts and arcs on Bottom Overlay, Mechanical 13 and 15 drawings unchanged.
