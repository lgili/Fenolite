# c0484: native bodies are kept through KiCad

## Why

KiCad has no extruded body. A conversion to KiCad writes each component's extruded, cylinder and sphere
bodies as one generated STEP model (c0423), and the way back writes that model as a model body (type 1)
with the STEP file embedded. The source's parametric bodies do not come back. On the maintainer's board
(private; codes and counts only), the source holds 196 body records: 175 model bodies, 18 extruded bodies
and 3 cylinders. F2 and F5 write 183: the 175 model bodies and 8 generated models in place of the 21
parametric bodies.

## What Changes

- A conversion to KiCad carries, in the board property `Fenolite.Altium.Bodies`, the records of the bodies
  that each generated model stands for, as read, each with its `ShapeBasedComponentBodies6` twin. The key is
  the generated model's SHA-256 and its footprint's place, turn and side in KiCad. A model is carried only
  when every body it stands for is an extruded body, a cylinder or a sphere of the source document.
- The way back writes those records, with the new component index, in place of the generated model body,
  under two conditions: the footprint holds the same model bytes, unmoved in its frame, and the footprint
  has the same place, turn and side. The generated STEP is then not embedded. Otherwise the model is
  written as before.
- The key is the model and the footprint pose, not the footprint's uuid, so `import --to python` and
  `build --target altium` (c0480) keep the bodies too.
- The report counts a kept model as written under `model`, as before; nothing is counted `changed`.

## Impact

- `backends/altium/models3d.py` (`body_records`), `convert/models.py`, `convert/to_kicad.py`,
  `convert/to_altium.py`, `backends/altium/lower.py`, `backends/altium/pcbdoc.py`.
- `docs/formats/altium/pcb-bodies.md`, `docs/conversion.md`, `docs/formats/kicad/board.md`.
- No change to a board that carries no bodies, or to a footprint whose model or pose changed.
