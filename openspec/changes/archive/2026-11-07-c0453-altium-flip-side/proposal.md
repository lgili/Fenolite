# Altium flip writes the side convention Altium rebuilds from

## Why

The maintainer flipped parts with Fenolite's Altium edit session, then opened and saved the board in Altium
(owner-board evidence, generic, S-2120). After the save the flipped parts had their pads and designator back
on the old side. The component's `LAYER` and its silk stayed flipped. `BODYPROJECTION` was unchanged, so the
3D body stayed on the old side, mirrored.

Altium places a bottom part as its footprint mirrored in Y, then turned by `ROTATION` about the origin. The
eight public documents hold 235 bottom parts with asymmetric pads whose pattern is also placed on the top.
Every one of them reads that way, and none reads mirrored in X (S-2121). A pad's rotation relative to its
part changes sign on the bottom. Every body of a bottom part holds `BODYPROJECTION=1`, and every body of a
top part holds 0.

Fenolite's flip mirrors the primitives in X about the component's origin. It writes `ROTATION` as `−R`,
keeps each pad's rotation as `−r`, and leaves the body's keys alone. The primitives are right on the board.
The component's frame, however, says the footprint is turned by 180° against its library (S-2122). Altium's
own flip of the same part (case J9) writes `ROTATION` 180 and each pad's rotation 180, from 0 and 0. When
Altium rebuilds a part from its frame, the pads and the designator land where that frame puts them: on the
old side.

## What Changes

- `edit.ops.flip` writes `ROTATION` as `(180 − R) mod 360` and turns each pad of the part to `(180 − r) mod
  360`. A flip back restores both. Arcs, tracks, texts and fills keep the transform they have.
- A flipped body toggles `BODYPROJECTION` (0 top, 1 bottom). Its `MODEL.3D.ROTZ` and `MODEL.2D.ROTATION`
  keep their rotation relative to the component. `MODEL.3D.ROTX`, `ROTY` and `DZ` stay unchanged.
- Kit files for the VM agent (Part J case J9 and a body variant): Fenolite's flip of `J01-resave.PcbDoc`,
  then opened, saved and read again in Altium.
- Docs: rows in `pcb-document.md`, sources S-2120 to S-2122 (S-2123 for the kit run), and the status of
  `H-A-EDIT-FLIP`.

## Impact

- `src/fenolite/backends/altium/edit/ops.py` (`flip`, `move_primitives`, `_body_model_keys`) and
  `edit/records.py` (`transform`'s pad angle under a mirror).
- Tests in `tests/unit/backends/altium/edit/`.
- No change to the writers. `lower` writes a bottom footprint's model rotation as `ROTATION`, and the
  model's bottom footprint holds local coordinates mirrored in Y, which is Altium's convention. The reader
  inverts that frame.
