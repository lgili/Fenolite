# c0449: embedded 3D models through Altium → KiCad → Altium

## Why

An Altium PCB document embeds the 3D model of each body that names one: a record of `Models/Data` and a
zlib stream `Models/<n>` holding the STEP text (`pcb-bodies.md`, "Embedded models and their placement").
Since c0223 and c0423 a conversion to KiCad extracts each one beside the derived library and names it in the
footprint with the source's pose. The way back drops them: the KiCad → Altium direction reads no `model`
child of a footprint, writes `Models` and `ModelsNoEmbed` empty and has no record for a body that names a
model. After a round trip every 3D body of the eight public rows (472 bodies, 201 models in the seven rows
measured so far) is gone, and the report does not say so.

## What Changes

- The KiCad → Altium conversion reads each `model` child of a board footprint. A STEP file that the path
  names beside the project (`${KIPRJMOD}/…` or a relative path) is embedded in the PCB document: one
  `Models/Data` record and one `Models/<n>` stream per distinct file, and one body record that names it per
  footprint model, in both body storages.
- The body's placement keys (`MODEL.2D.X/Y`, `MODEL.3D.DZ`, `MODEL.3D.ROTX/Y/Z`) are the inverse of the
  c0423 placement, so Altium puts the model where KiCad shows it. Its outline and its two heights are the box
  of the placed model, measured by a small STEP box reader of Fenolite's own (`backends.stepbox`), the rule
  that saved documents follow (`H-A-BODY-MODEL-PLACE`: the stored box is the model's box).
- Every other model child is a `model` loss with its reason (a file not found, a path under another
  variable, a KiCad embedded file, a file that is no STEP text, a scale other than 1, a STEP without
  geometry). The kind `model` enters the Altium write's accounts.
- `MODEL.CHECKSUM` stays a stand-in (0): no tested rule (CRC-32, Adler-32, byte sums) gives the saved value.

## Impact

- New `backends/stepbox.py`; `backends/kicad/_fpmap.py` (`read_placement`); `backends/altium/pcbrecords.py`
  (model body and `Models` records); `backends/altium/pcbdoc.py` (`Models` storage, placed model bodies);
  `backends/altium/lower.py` (accounting, placement); `convert/to_altium.py` (finding the files);
  `convert/models.py` (the inverse placement).
- Documents without a model child are written byte for byte as before; a KiCad board whose models lie
  outside the project now reports them as `model` losses instead of dropping them silently.
- Altium's acceptance of the written records (checksum 0, Fenolite's GUIDs) is `INFERRED` until a kit or
  VM run opens a round trip.
